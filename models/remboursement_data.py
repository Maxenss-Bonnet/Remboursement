import os
import shutil
import sqlite3
from typing import List, Tuple, Optional

from config.settings import REMBOURSEMENTS_ATTACHMENTS_DIR, REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR
from models.schemas import Remboursement
from utils.database_manager import get_db_connection
from utils.archive_utils import create_archive_for_demande


def _construct_remboursement_from_row(row: sqlite3.Row) -> Remboursement:
    data = dict(row)
    historique_list = []
    if data.get('all_history'):
        for item in data['all_history'].split(';'):
            parts = item.split('|', 3)
            if len(parts) == 4:
                historique_list.append({
                    "statut": parts[0], "date": parts[1],
                    "par_utilisateur": parts[2] if parts[2] != 'None' else None,
                    "commentaire": parts[3] if parts[3] != 'None' else None
                })
    data['historique_statuts'] = historique_list

    factures, ribs, trop_percus = [], [], []
    if data.get('all_attachments'):
        for item in data['all_attachments'].split(';'):
            parts = item.split('|', 1)
            if len(parts) == 2:
                pj_type, pj_path = parts
                if pj_type == 'facture':
                    factures.append(pj_path)
                elif pj_type == 'rib':
                    ribs.append(pj_path)
                elif pj_type == 'trop_percu' or pj_type == 'chemins_trop_percu_stockes':
                    trop_percus.append(pj_path)

    data['chemins_factures_stockees'] = factures
    data['chemins_rib_stockes'] = ribs
    data['chemins_trop_percu_stockees'] = trop_percus

    data.pop('all_history', None)
    data.pop('all_attachments', None)
    return Remboursement(**data)


def charger_toutes_les_demandes_data(archived: bool = False) -> List[Remboursement]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
            SELECT r.*,
                   (SELECT GROUP_CONCAT(h.statut || '|' || h.date || '|' || IFNULL(h.par_utilisateur, 'None') || '|' ||
                                        IFNULL(h.commentaire, 'None'), ';')
                    FROM (SELECT * FROM historique WHERE id_demande = r.id_demande ORDER BY date) h
                   ) AS all_history,
                   (SELECT GROUP_CONCAT(pj.type_pj || '|' || pj.chemin_relatif, ';')
                    FROM (SELECT * FROM pieces_jointes WHERE id_demande = r.id_demande ORDER BY date_ajout) pj
                   ) AS all_attachments
            FROM remboursements r
            WHERE r.is_archived = ?
            """
    cursor.execute(query, (1 if archived else 0,))
    rows = cursor.fetchall()
    conn.close()
    demandes = [_construct_remboursement_from_row(row) for row in rows]
    return sorted(demandes, key=lambda d: d.date_derniere_modification, reverse=True)


def obtenir_demande_par_id_data(id_demande: str) -> Optional[Remboursement]:
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
            SELECT r.*,
                   (SELECT GROUP_CONCAT(h.statut || '|' || h.date || '|' || IFNULL(h.par_utilisateur, 'None') || '|' ||
                                        IFNULL(h.commentaire, 'None'), ';')
                    FROM (SELECT * FROM historique WHERE id_demande = r.id_demande ORDER BY date) h
                   ) AS all_history,
                   (SELECT GROUP_CONCAT(pj.type_pj || '|' || pj.chemin_relatif, ';')
                    FROM (SELECT * FROM pieces_jointes WHERE id_demande = r.id_demande ORDER BY date_ajout) pj
                   ) AS all_attachments
            FROM remboursements r
            WHERE r.id_demande = ?
            """
    cursor.execute(query, (id_demande,))
    row = cursor.fetchone()
    conn.close()
    return _construct_remboursement_from_row(row) if row else None


def creer_demande_data(demande: Remboursement) -> Tuple[bool, str]:
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO remboursements (id_demande, nom, prenom, reference_facture, reference_facture_dossier, description, montant_demande, statut, cree_par, date_creation, derniere_modification_par, date_derniere_modification, is_archived) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (demande.id_demande, demande.nom, demande.prenom, demande.reference_facture,
                 demande.reference_facture_dossier, demande.description, demande.montant_demande, demande.statut,
                 demande.cree_par, demande.date_creation, demande.derniere_modification_par,
                 demande.date_derniere_modification, 0))

            for hist in demande.historique_statuts:
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
        return False, f"Erreur de base de données : {e}"
    finally:
        conn.close()


def mettre_a_jour_demande_data(demande: Remboursement, nouveau_pj_relatif: Optional[str] = None,
                               type_pj: Optional[str] = None) -> Tuple[bool, str]:
    conn = get_db_connection()
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
        return False, f"Erreur de base de données : {e}"
    finally:
        conn.close()


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

    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE remboursements SET is_archived = 1 WHERE id_demande = ?", (id_demande,))
            if cursor.rowcount == 0: raise sqlite3.OperationalError("Aucune ligne mise à jour.")
        return True, f"La demande {id_demande} a été archivée."
    except sqlite3.Error as e:
        return False, f"Erreur de BDD lors de l'archivage : {e}"
    finally:
        conn.close()


def supprimer_demande_par_id_data(id_demande: str) -> Tuple[bool, str]:
    demande = obtenir_demande_par_id_data(id_demande)
    if not demande:
        demandes_archivees = charger_toutes_les_demandes_data(archived=True)
        demande = next((d for d in demandes_archivees if d.id_demande == id_demande), None)
        if not demande: return False, "Demande non trouvée."

    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM remboursements WHERE id_demande = ?", (id_demande,))
            if cursor.rowcount == 0: raise sqlite3.OperationalError("La suppression n'a affecté aucune ligne.")

        if demande.is_archived:
            chemin_archive = os.path.join(REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR,
                                          f"{demande.reference_facture_dossier}.zip")
            if os.path.exists(chemin_archive): os.remove(chemin_archive)
        else:
            dossier_a_supprimer = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, demande.reference_facture_dossier)
            if os.path.isdir(dossier_a_supprimer): shutil.rmtree(dossier_a_supprimer)

        return True, f"La demande {id_demande} et ses fichiers ont été supprimés."
    except sqlite3.Error as e:
        return False, f"Erreur de BDD lors de la suppression : {e}"
    except OSError as e:
        return False, f"Erreur système lors de la suppression des fichiers : {e}"
    finally:
        conn.close()