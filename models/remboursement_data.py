import os
import shutil
import sqlite3
import datetime
import stat
import errno
import logging
from typing import List, Tuple, Optional
from collections import OrderedDict

from config.settings import (
    REMBOURSEMENTS_ATTACHMENTS_DIR, REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR,
    STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO
)
from models.schemas import Remboursement, HistoriqueStatut
from utils.database_manager import db_connection, execute_in_queue, handle_db_locks
from utils.archive_utils import create_archive_for_demande

_log = logging.getLogger(__name__)


@handle_db_locks
def _construct_remboursement_from_row(row: sqlite3.Row) -> Remboursement:
    data = dict(row)

    remboursement_data = {
        'id_demande': data['id_demande'],
        'nom': data['nom'],
        'prenom': data['prenom'],
        'reference_facture': data['reference_facture'],
        'reference_facture_dossier': data['reference_facture_dossier'],
        'description': data['description'],
        'montant_demande': data['montant_demande'],
        'statut': data['statut'],
        'cree_par': data['cree_par'],
        'derniere_modification_par': data['derniere_modification_par'],
        'is_archived': data['is_archived'],
        'historique_statuts': [],
        'chemins_factures_stockees': [],
        'chemins_rib_stockes': [],
        'chemins_trop_percu_stockees': []
    }

    if isinstance(data['date_creation'], str):
        remboursement_data['date_creation'] = datetime.datetime.fromisoformat(data['date_creation'])
    if isinstance(data['date_derniere_modification'], str):
        remboursement_data['date_derniere_modification'] = datetime.datetime.fromisoformat(
            data['date_derniere_modification'])
    if data['date_paiement_effectue'] and isinstance(data['date_paiement_effectue'], str):
        remboursement_data['date_paiement_effectue'] = datetime.datetime.fromisoformat(data['date_paiement_effectue'])
    else:
        remboursement_data['date_paiement_effectue'] = None

    return Remboursement(**remboursement_data)


@handle_db_locks
def charger_demandes_data(
        statut_filter: Optional[List[str]] = None,
        search_term: Optional[str] = None,
        sort_field: str = 'date_derniere_modification',
        sort_order: str = 'DESC',
        is_archived: Optional[bool] = None,
        date_range: Optional[Tuple[datetime.datetime, datetime.datetime]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        active_for_user: Optional[Tuple[list, str]] = None
) -> Tuple[List[Remboursement], int]:
    with db_connection() as conn:
        cursor = conn.cursor()

        where_clauses = []
        params = []

        if is_archived is not None:
            where_clauses.append("r.is_archived = ?")
            params.append(1 if is_archived else 0)

        if search_term:
            where_clauses.append("(r.nom LIKE ? OR r.prenom LIKE ? OR r.reference_facture LIKE ?)")
            term = f"%{search_term}%"
            params.extend([term, term, term])

        if active_for_user:
            user_roles, user_login = active_for_user
            action_conditions = []

            if 'comptable_tresorerie' in user_roles:
                action_conditions.append("r.statut IN (?, ?)")
                params.extend([STATUT_CREEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO])

            if 'demandeur' in user_roles:
                action_conditions.append("(r.statut = ? AND r.cree_par = ?)")
                params.extend([STATUT_REFUSEE_CONSTAT_TP, user_login])

            if 'validateur_chef' in user_roles:
                action_conditions.append("r.statut = ?")
                params.append(STATUT_TROP_PERCU_CONSTATE)

            if 'comptable_fournisseur' in user_roles:
                action_conditions.append("r.statut = ?")
                params.append(STATUT_VALIDEE)

            if 'admin' in user_roles:
                admin_statuses = [
                    STATUT_CREEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
                    STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE, STATUT_VALIDEE
                ]
                placeholders = ', '.join(['?'] * len(admin_statuses))
                action_conditions.append(f"r.statut IN ({placeholders})")
                params.extend(admin_statuses)

            if action_conditions:
                where_clauses.append(f"({' OR '.join(action_conditions)})")

        elif statut_filter:
            placeholders = ', '.join('?' for _ in statut_filter)
            where_clauses.append(f"r.statut IN ({placeholders})")
            params.extend(statut_filter)

        if date_range:
            start_date, end_date = date_range
            where_clauses.append("r.date_derniere_modification BETWEEN ? AND ?")
            params.extend([start_date, end_date])

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        count_query = f"SELECT COUNT(DISTINCT r.id_demande) FROM remboursements r{where_sql}"
        cursor.execute(count_query, tuple(params))
        total_count = cursor.fetchone()[0]

        if total_count == 0:
            return [], 0

        order_clause = ""
        valid_sort_fields = ['nom', 'montant_demande', 'date_derniere_modification', 'date_creation']
        if sort_field in valid_sort_fields:
            order = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'
            order_clause = f" ORDER BY r.{sort_field} {order}"

        limit_offset_clause = ""
        if limit is not None:
            limit_offset_clause = " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        id_query = f"SELECT r.id_demande FROM remboursements r {where_sql} {order_clause} {limit_offset_clause}"
        cursor.execute(id_query, tuple(params))
        paginated_ids = [row['id_demande'] for row in cursor.fetchall()]

        if not paginated_ids:
            return [], total_count

        id_placeholders = ', '.join('?' for _ in paginated_ids)
        main_query = f"""
            SELECT
                r.*,
                h.historique_id, h.statut as hist_statut, h.date as hist_date, h.par_utilisateur as hist_user, h.commentaire as hist_comment,
                pj.pj_id, pj.type_pj, pj.chemin_relatif
            FROM remboursements r
            LEFT JOIN historique h ON r.id_demande = h.id_demande
            LEFT JOIN pieces_jointes pj ON r.id_demande = pj.id_demande
            WHERE r.id_demande IN ({id_placeholders})
        """

        cursor.execute(main_query, tuple(paginated_ids))
        rows = cursor.fetchall()

    demandes_map = OrderedDict()
    for row in rows:
        demande_id = row['id_demande']
        if demande_id not in demandes_map:
            demandes_map[demande_id] = _construct_remboursement_from_row(row)

        demande_obj = demandes_map[demande_id]

        # --- CORRECTION DE LA LOGIQUE DE DÉDUPLICATION ---
        historique_id = row['historique_id']
        if historique_id is not None and not any(
                h.historique_id == historique_id for h in demande_obj.historique_statuts):
            demande_obj.historique_statuts.append(HistoriqueStatut(
                historique_id=historique_id,
                statut=row['hist_statut'],
                date=datetime.datetime.fromisoformat(row['hist_date']),
                par_utilisateur=row['hist_user'],
                commentaire=row['hist_comment']
            ))

        if row['pj_id'] and not any(pj == row['chemin_relatif'] for pj in (
                demande_obj.chemins_factures_stockees + demande_obj.chemins_rib_stockes + demande_obj.chemins_trop_percu_stockees)):
            type_pj = row['type_pj']
            chemin = row['chemin_relatif']
            if type_pj == 'facture':
                demande_obj.chemins_factures_stockees.append(chemin)
            elif type_pj == 'rib':
                demande_obj.chemins_rib_stockes.append(chemin)
            elif type_pj == 'trop_percu':
                demande_obj.chemins_trop_percu_stockees.append(chemin)

    final_list = list(demandes_map.values())
    # Trier la liste finale selon les critères de l'utilisateur
    final_list.sort(
        key=lambda d: getattr(d, sort_field) if hasattr(d, sort_field) else d.date_derniere_modification,
        reverse=(sort_order.upper() == 'DESC')
    )

    # Trier l'historique de chaque demande par date
    for demande in final_list:
        demande.historique_statuts.sort(key=lambda h: h.date)

    return final_list, total_count


@handle_db_locks
def obtenir_demande_par_id_data(id_demande: str) -> Optional[Remboursement]:
    with db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT r.* FROM remboursements r WHERE r.id_demande = ?"
        cursor.execute(query, (id_demande,))
        row = cursor.fetchone()

        if not row:
            return None

        demande = _construct_remboursement_from_row(row)

        cursor.execute(
            "SELECT historique_id, statut, date, par_utilisateur, commentaire FROM historique WHERE id_demande = ? ORDER BY date",
            (id_demande,))

        demande.historique_statuts = [
            HistoriqueStatut(
                historique_id=h['historique_id'],
                date=datetime.datetime.fromisoformat(h['date']),
                statut=h['statut'],
                par_utilisateur=h['par_utilisateur'],
                commentaire=h['commentaire']
            ) for h in cursor.fetchall()
        ]

        cursor.execute("SELECT type_pj, chemin_relatif FROM pieces_jointes WHERE id_demande = ? ORDER BY date_ajout",
                       (id_demande,))
        for pj_row in cursor.fetchall():
            if pj_row['type_pj'] == 'facture':
                demande.chemins_factures_stockees.append(pj_row['chemin_relatif'])
            elif pj_row['type_pj'] == 'rib':
                demande.chemins_rib_stockes.append(pj_row['chemin_relatif'])
            elif pj_row['type_pj'] == 'trop_percu':
                demande.chemins_trop_percu_stockees.append(pj_row['chemin_relatif'])

    return demande


@execute_in_queue
def creer_demande_data(demande: Remboursement) -> Tuple[bool, str]:
    with db_connection() as conn:
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO remboursements (id_demande, nom, prenom, reference_facture, reference_facture_dossier, description, montant_demande, statut, cree_par, date_creation, derniere_modification_par, date_derniere_modification, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (demande.id_demande, demande.nom, demande.prenom, demande.reference_facture,
                     demande.reference_facture_dossier, demande.description, demande.montant_demande, demande.statut,
                     demande.cree_par, demande.date_creation, demande.derniere_modification_par,
                     demande.date_derniere_modification, 1 if demande.is_archived else 0))

                _log.debug(
                    f"CREATION DEMANDE {demande.id_demande}: Ajout de {len(demande.historique_statuts)} entrées d'historique.")
                for hist in demande.historique_statuts:
                    _log.debug(
                        f" -> Ajout historique: {hist.statut} par {hist.par_utilisateur} avec commentaire '{hist.commentaire}'")
                    cursor.execute(
                        "INSERT INTO historique (id_demande, statut, date, par_utilisateur, commentaire) VALUES (?, ?, ?, ?, ?)",
                        (demande.id_demande, hist.statut, hist.date, hist.par_utilisateur, hist.commentaire))

                for path in demande.chemins_factures_stockees:
                    cursor.execute(
                        "INSERT INTO pieces_jointes (id_demande, type_pj, chemin_relatif, date_ajout) VALUES (?, ?, ?, ?)",
                        (demande.id_demande, 'facture', path, demande.date_creation))
                for path in demande.chemins_rib_stockes:
                    cursor.execute(
                        "INSERT INTO pieces_jointes (id_demande, type_pj, chemin_relatif, date_ajout) VALUES (?, ?, ?, ?)",
                        (demande.id_demande, 'rib', path, demande.date_creation))
            return True, "Demande créée avec succès dans la BDD."
        except sqlite3.Error as e:
            _log.error(f"Erreur de base de données lors de la création de la demande {demande.id_demande}",
                       exc_info=True)
            return False, f"Erreur de base de données : {e}"


@execute_in_queue
def mettre_a_jour_demande_data(demande: Remboursement, nouveau_pj_relatif: Optional[str] = None,
                               type_pj: Optional[str] = None) -> Tuple[bool, str]:
    with db_connection() as conn:
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""UPDATE remboursements
                                  SET nom                        = ?,
                                      prenom                     = ?,
                                      reference_facture          = ?,
                                      description                = ?,
                                      montant_demande            = ?,
                                      statut                     = ?,
                                      derniere_modification_par  = ?,
                                      date_derniere_modification = ?,
                                      date_paiement_effectue     = ?
                                  WHERE id_demande = ?""",
                               (demande.nom, demande.prenom, demande.reference_facture, demande.description,
                                demande.montant_demande, demande.statut, demande.derniere_modification_par,
                                demande.date_derniere_modification, demande.date_paiement_effectue, demande.id_demande))

                if demande.historique_statuts:
                    dernier_historique = demande.historique_statuts[-1]
                    _log.debug(
                        f"MISE A JOUR DEMANDE {demande.id_demande}: Ajout de la dernière entrée d'historique: {dernier_historique.statut} par {dernier_historique.par_utilisateur} avec commentaire '{dernier_historique.commentaire}'")
                    cursor.execute(
                        "INSERT INTO historique (id_demande, statut, date, par_utilisateur, commentaire) VALUES (?, ?, ?, ?, ?)",
                        (demande.id_demande, dernier_historique.statut, dernier_historique.date,
                         dernier_historique.par_utilisateur, dernier_historique.commentaire))

                if nouveau_pj_relatif and type_pj:
                    cursor.execute(
                        "INSERT INTO pieces_jointes (id_demande, type_pj, chemin_relatif, date_ajout) VALUES (?, ?, ?, ?)",
                        (demande.id_demande, type_pj, nouveau_pj_relatif, demande.date_derniere_modification))
            return True, "Demande mise à jour avec succès."
        except sqlite3.Error as e:
            _log.error(f"Erreur de base de données lors de la mise à jour de la demande {demande.id_demande}",
                       exc_info=True)
            return False, f"Erreur de base de données : {e}"


@execute_in_queue
def ajouter_piece_jointe_data(id_demande: str, chemin_relatif: str, type_pj: str) -> Tuple[bool, str]:
    with db_connection() as conn:
        try:
            with conn:
                cursor = conn.cursor()
                now = datetime.datetime.now()
                cursor.execute(
                    "INSERT INTO pieces_jointes (id_demande, type_pj, chemin_relatif, date_ajout) VALUES (?, ?, ?, ?)",
                    (id_demande, type_pj, chemin_relatif, now)
                )
                cursor.execute(
                    "UPDATE remboursements SET date_derniere_modification = ? WHERE id_demande = ?",
                    (now, id_demande)
                )
            return True, "Pièce jointe ajoutée."
        except sqlite3.Error as e:
            _log.error(f"Erreur BDD lors de l'ajout de la PJ pour la demande {id_demande}", exc_info=True)
            return False, f"Erreur BDD lors de l'ajout de la PJ: {e}"


@execute_in_queue
def archiver_demande_par_id_data(id_demande: str) -> Tuple[bool, str]:
    demande = obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.is_archived: return True, "La demande est déjà archivée."

    dossier_source = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, demande.reference_facture_dossier)
    if os.path.isdir(dossier_source):
        archive_success, archive_message = create_archive_for_demande(
            dossier_source=dossier_source,
            dossier_archive=REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR,
            nom_dossier_demande=demande.reference_facture_dossier
        )
        if not archive_success: return False, archive_message

    with db_connection() as conn:
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE remboursements SET is_archived = 1 WHERE id_demande = ?", (id_demande,))
                if cursor.rowcount == 0: raise sqlite3.OperationalError("Aucune ligne mise à jour pour l'archivage.")
            return True, f"La demande {id_demande} a été archivée."
        except sqlite3.Error as e:
            _log.error(f"Erreur de BDD lors de l'archivage de la demande {id_demande}", exc_info=True)
            return False, f"Erreur de BDD lors de l'archivage : {e}"


@execute_in_queue
def supprimer_demande_par_id_data(id_demande: str) -> Tuple[bool, str]:
    demande = obtenir_demande_par_id_data(id_demande)
    if not demande:
        demandes_archivees, _ = charger_demandes_data(is_archived=True)
        demande = next((d for d in demandes_archivees if d.id_demande == id_demande), None)
        if not demande: return False, "Demande non trouvée."

    with db_connection() as conn:
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM remboursements WHERE id_demande = ?", (id_demande,))
                if cursor.rowcount == 0: raise sqlite3.OperationalError("La suppression n'a affecté aucune ligne.")

            def handle_remove_readonly(func, path, exc):
                excvalue = exc[1]
                if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == errno.EACCES:
                    os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
                    func(path)
                else:
                    raise

            if demande.is_archived:
                chemin_archive = os.path.join(REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR,
                                              f"{demande.reference_facture_dossier}.zip")
                if os.path.exists(chemin_archive): os.remove(chemin_archive)
            else:
                dossier_a_supprimer = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, demande.reference_facture_dossier)
                if os.path.isdir(dossier_a_supprimer):
                    try:
                        shutil.rmtree(dossier_a_supprimer, onerror=handle_remove_readonly)
                    except OSError as e:
                        _log.error(f"Erreur système lors de la suppression du dossier {dossier_a_supprimer}",
                                   exc_info=True)
                        return False, f"Erreur système lors de la suppression du dossier {dossier_a_supprimer}: {e}"

            return True, f"La demande {id_demande} et ses fichiers ont été supprimés."
        except sqlite3.Error as e:
            _log.error(f"Erreur de BDD lors de la suppression de la demande {id_demande}", exc_info=True)
            return False, f"Erreur de BDD lors de la suppression : {e}"


@execute_in_queue
def optimiser_base_de_donnees_data() -> Tuple[bool, str]:
    """Exécute la commande VACUUM pour réorganiser la BDD et récupérer l'espace disque."""
    with db_connection() as conn:
        try:
            _log.info("Lancement de l'opération VACUUM sur la base de données...")
            conn.execute("VACUUM")
            _log.info("Opération VACUUM terminée avec succès.")
            return True, "La base de données a été optimisée."
        except sqlite3.Error as e:
            _log.error("Erreur lors de l'optimisation (VACUUM) de la base de données.", exc_info=True)
            return False, f"Erreur lors de l'optimisation de la base de données : {e}"