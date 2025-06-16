import os
import datetime
import uuid
import shutil
import re
from . import remboursement_data
from . import remboursement_workflow
from config.settings import (
    REMBOURSEMENTS_ATTACHMENTS_DIR,
    STATUT_CREEE,
    STATUT_PAIEMENT_EFFECTUE,
    STATUT_ANNULEE,
    STATUT_REFUSEE_CONSTAT_TP,
    STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO
)
from .schemas import Remboursement as RemboursementSchema, HistoriqueStatut


def _sanitize_for_filename(text: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", text).replace(" ", "_")


def _copy_and_version_attachment(source_path: str, dossier_demande: str, subfolder: str, file_prefix: str) -> str | None:
    if not source_path or not os.path.exists(source_path):
        return None

    destination_folder = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, dossier_demande, subfolder)
    os.makedirs(destination_folder, exist_ok=True)

    _, extension = os.path.splitext(source_path)

    version_pattern = re.compile(f"^{re.escape(file_prefix)}_v(\\d+)")
    max_version = 0
    if os.path.exists(destination_folder):
        for item in os.listdir(destination_folder):
            match = version_pattern.match(item)
            if match:
                version_num = int(match.group(1))
                if version_num > max_version:
                    max_version = version_num

    new_version = max_version + 1
    new_filename = f"{file_prefix}_v{new_version}{extension}"
    destination_path = os.path.join(destination_folder, new_filename)

    try:
        shutil.copy2(source_path, destination_path)
        return os.path.join(dossier_demande, subfolder, new_filename)
    except Exception as e:
        print(f"Erreur lors de la copie de {source_path} vers {destination_path}: {e}")
        return None


def creer_nouvelle_demande(
        nom: str,
        prenom: str,
        reference_facture: str,
        montant_demande: float,
        chemin_facture_source: str | None,
        chemin_rib_source: str,
        utilisateur_createur: str,
        description: str
) -> tuple[bool, str]:
    id_unique_demande = f"D{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:4]}"

    ref_sanitized = _sanitize_for_filename(reference_facture)
    nom_dossier = f"{ref_sanitized}_{id_unique_demande}"

    chemins_factures_relatifs = []
    if chemin_facture_source:
        path = _copy_and_version_attachment(chemin_facture_source, nom_dossier, "Facture", "Facture")
        if path:
            chemins_factures_relatifs.append(path)

    chemins_rib_relatifs = []
    if chemin_rib_source:
        path = _copy_and_version_attachment(chemin_rib_source, nom_dossier, "RIB", "RIB")
        if not path:
            return False, "Erreur critique lors de la copie du RIB."
        chemins_rib_relatifs.append(path)

    now = datetime.datetime.now()

    demande_a_creer = RemboursementSchema(
        id_demande=id_unique_demande,
        nom=nom.upper() if nom else None,
        prenom=prenom.title() if prenom else None,
        reference_facture=reference_facture,
        reference_facture_dossier=nom_dossier,
        description=description,
        montant_demande=montant_demande,
        chemins_factures_stockees=chemins_factures_relatifs,
        chemins_rib_stockes=chemins_rib_relatifs,
        statut=STATUT_CREEE,
        cree_par=utilisateur_createur,
        date_creation=now,
        derniere_modification_par=utilisateur_createur,
        date_derniere_modification=now,
        historique_statuts=[HistoriqueStatut(
            statut=STATUT_CREEE, date=now, par_utilisateur=utilisateur_createur, commentaire=description
        )]
    )

    return remboursement_data.creer_demande_data(demande_a_creer)


def obtenir_demande_par_id(id_demande: str) -> RemboursementSchema | None:
    return remboursement_data.obtenir_demande_par_id_data(id_demande)


def obtenir_toutes_les_demandes(include_archives: bool = False) -> list[RemboursementSchema]:
    return remboursement_data.charger_toutes_les_demandes_data(include_archives)


def archiver_les_vieilles_demandes() -> int:
    count = 0
    douze_mois = datetime.timedelta(days=365)
    now = datetime.datetime.now()
    demandes_actives = obtenir_toutes_les_demandes(include_archives=False)

    for demande in demandes_actives:
        if demande.statut in [STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE]:
            if demande.date_derniere_modification and (now - demande.date_derniere_modification) > douze_mois:
                succes, _ = archiver_demande_par_id(demande.id_demande)
                if succes:
                    count += 1
    return count


def admin_supprimer_archives_anciennes(age_en_annees: int) -> tuple[int, list[str]]:
    demandes_supprimees = 0
    erreurs = []
    date_limite = datetime.datetime.now() - datetime.timedelta(days=age_en_annees * 365.25)
    demandes_archivees = obtenir_toutes_les_demandes(include_archives=True)

    for demande in demandes_archivees:
        if demande.is_archived and demande.date_derniere_modification < date_limite:
            succes, msg = supprimer_demande_par_id(demande.id_demande)
            if succes:
                demandes_supprimees += 1
            else:
                erreurs.append(f"Erreur suppression {demande.id_demande}: {msg}")
    return demandes_supprimees, erreurs


def _generic_workflow_action(demande, commentaire: str | None, utilisateur: str,
                             action_function, **kwargs) -> tuple[bool, str]:
    if not demande:
        return False, "Demande non trouvée."
    return action_function(demande, commentaire, utilisateur, **kwargs)


def annuler_demande(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, commentaire, utilisateur,
                                    remboursement_workflow.annuler_demande_action)


def accepter_constat_trop_percu(id_demande: str, commentaire: str, utilisateur: str,
                                chemin_pj_trop_percu: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    if not demande:
        return False, "Demande non trouvée."

    if not chemin_pj_trop_percu or not os.path.exists(chemin_pj_trop_percu):
        return False, "Le chemin de la pièce jointe du trop-perçu est invalide."

    chemin_relatif = _copy_and_version_attachment(chemin_pj_trop_percu, demande.reference_facture_dossier, "Trop_Percu",
                                                  "Preuve_TP")
    if not chemin_relatif:
        return False, "Erreur lors de la copie de la preuve de trop-perçu."

    return _generic_workflow_action(
        demande, commentaire, utilisateur,
        remboursement_workflow.accepter_constat_trop_percu_action,
        nouveau_pj_relatif=chemin_relatif,
        type_pj='trop_percu'
    )


def refuser_constat_trop_percu(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, commentaire, utilisateur,
                                    remboursement_workflow.refuser_constat_trop_percu_action)


def valider_demande_par_validateur(id_demande: str, commentaire: str | None, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, commentaire, utilisateur,
                                    remboursement_workflow.valider_demande_par_validateur_action)


def refuser_demande_par_validateur(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, commentaire, utilisateur,
                                    remboursement_workflow.refuser_demande_par_validateur_action)


def confirmer_paiement_effectue(id_demande: str, utilisateur: str, commentaire: str | None) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, commentaire, utilisateur,
                                    remboursement_workflow.confirmer_paiement_action)


def mlupo_refuser_correction(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, commentaire, utilisateur,
                                    remboursement_workflow.mlupo_refuser_correction_action)


def pneri_resoumettre_demande_corrigee(id_demande: str, commentaire: str, nouveau_chemin_facture: str | None,
                                       nouveau_chemin_rib: str | None, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    if not demande:
        return False, "Demande non trouvée."
    if demande.statut != STATUT_REFUSEE_CONSTAT_TP:
        return False, f"La demande n'est pas au statut '{STATUT_REFUSEE_CONSTAT_TP}'."

    if nouveau_chemin_facture:
        path = _copy_and_version_attachment(nouveau_chemin_facture, demande.reference_facture_dossier, "Facture",
                                            "Facture")
        if not path:
            return False, "Erreur lors de la copie de la nouvelle facture."
        succes, msg = remboursement_data.ajouter_piece_jointe_data(id_demande, path, "facture")
        if not succes:
            return False, f"Erreur BDD (facture): {msg}"

    if nouveau_chemin_rib:
        path = _copy_and_version_attachment(nouveau_chemin_rib, demande.reference_facture_dossier, "RIB", "RIB")
        if not path:
            return False, "Erreur lors de la copie du nouveau RIB."
        succes, msg = remboursement_data.ajouter_piece_jointe_data(id_demande, path, "rib")
        if not succes:
            return False, f"Erreur BDD (RIB): {msg}"

    demande_a_jour = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande_a_jour, commentaire, utilisateur,
                                    remboursement_workflow.pneri_resoumettre_demande_action)


def mlupo_resoumettre_constat_corrige(id_demande: str, commentaire: str, nouveau_chemin_pj_trop_percu: str | None,
                                      utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    if not demande:
        return False, "Demande non trouvée."
    if demande.statut != STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO:
        return False, f"La demande n'est pas au statut '{STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO}'."

    nouveau_pj_relatif = None
    if nouveau_chemin_pj_trop_percu:
        nouveau_pj_relatif = _copy_and_version_attachment(nouveau_chemin_pj_trop_percu,
                                                          demande.reference_facture_dossier, "Trop_Percu",
                                                          "Preuve_TP")
        if not nouveau_pj_relatif:
            return False, "Erreur lors de la copie de la nouvelle preuve de trop-perçu."

    return _generic_workflow_action(
        demande, commentaire, utilisateur,
        remboursement_workflow.mlupo_resoumettre_constat_action,
        nouveau_pj_relatif=nouveau_pj_relatif,
        type_pj='trop_percu'
    )


archiver_demande_par_id = remboursement_data.archiver_demande_par_id_data
supprimer_demande_par_id = remboursement_data.supprimer_demande_par_id_data