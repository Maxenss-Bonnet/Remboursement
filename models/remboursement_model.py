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


def creer_nouvelle_demande(nom: str, prenom: str, reference_facture: str, montant_demande: float,
                           dossier_temporaire: str, utilisateur_createur: str, description: str) -> tuple[bool, str]:
    id_unique_demande = f"D{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:4]}"
    ref_sanitized = _sanitize_for_filename(reference_facture)
    nom_dossier_final = f"{ref_sanitized}_{id_unique_demande}"
    chemin_dossier_final = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, nom_dossier_final)

    try:
        os.rename(dossier_temporaire, chemin_dossier_final)
    except OSError as e:
        return False, f"Erreur critique lors de la finalisation du dossier de demande : {e}"

    chemins_factures_relatifs = []
    facture_dir = os.path.join(chemin_dossier_final, "Facture")
    if os.path.isdir(facture_dir):
        for f in sorted(os.listdir(facture_dir)):
            chemins_factures_relatifs.append(os.path.join(nom_dossier_final, "Facture", f))

    chemins_rib_relatifs = []
    rib_dir = os.path.join(chemin_dossier_final, "RIB")
    if os.path.isdir(rib_dir):
        for f in sorted(os.listdir(rib_dir)):
            chemins_rib_relatifs.append(os.path.join(nom_dossier_final, "RIB", f))

    now = datetime.datetime.now()
    demande_a_creer = RemboursementSchema(
        id_demande=id_unique_demande, nom=nom.upper() if nom else None,
        prenom=prenom.title() if prenom else None, reference_facture=reference_facture,
        reference_facture_dossier=nom_dossier_final, description=description,
        montant_demande=montant_demande, chemins_factures_stockees=chemins_factures_relatifs,
        chemins_rib_stockes=chemins_rib_relatifs, statut=STATUT_CREEE,
        cree_par=utilisateur_createur, date_creation=now,
        derniere_modification_par=utilisateur_createur, date_derniere_modification=now,
        historique_statuts=[HistoriqueStatut(statut=STATUT_CREEE, date=now, par_utilisateur=utilisateur_createur,
                                             commentaire=description)]
    )
    return remboursement_data.creer_demande_data(demande_a_creer)


def _generic_workflow_action(demande, utilisateur: str, commentaire: str | None, action_function, **kwargs) -> tuple[
    bool, str]:
    if not demande: return False, "Demande non trouvée."
    return action_function(demande, utilisateur, commentaire, **kwargs)


def accepter_constat_trop_percu(id_demande: str, commentaire: str, utilisateur: str, chemin_pj_relatif: str) -> tuple[
    bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, utilisateur, commentaire,
                                    remboursement_workflow.accepter_constat_trop_percu_action,
                                    nouveau_pj_relatif=chemin_pj_relatif, type_pj='trop_percu')


def pneri_resoumettre_demande_corrigee(id_demande: str, commentaire: str, chemin_facture_rel: str | None,
                                       chemin_rib_rel: str | None, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_REFUSEE_CONSTAT_TP: return False, f"La demande n'est pas au statut '{STATUT_REFUSEE_CONSTAT_TP}'."

    if chemin_facture_rel:
        succes, msg = remboursement_data.ajouter_piece_jointe_data(id_demande, chemin_facture_rel, "facture")
        if not succes: return False, f"Erreur BDD (facture): {msg}"
    if chemin_rib_rel:
        succes, msg = remboursement_data.ajouter_piece_jointe_data(id_demande, chemin_rib_rel, "rib")
        if not succes: return False, f"Erreur BDD (RIB): {msg}"

    demande_a_jour = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande_a_jour, utilisateur, commentaire,
                                    remboursement_workflow.pneri_resoumettre_demande_action)


def mlupo_resoumettre_constat_corrige(id_demande: str, commentaire: str, chemin_pj_relatif: str | None,
                                      utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO: return False, f"La demande n'est pas au statut '{STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO}'."

    return _generic_workflow_action(demande, utilisateur, commentaire,
                                    remboursement_workflow.mlupo_resoumettre_constat_action,
                                    nouveau_pj_relatif=chemin_pj_relatif, type_pj='trop_percu')


def obtenir_demande_par_id(
        id_demande: str) -> RemboursementSchema | None: return remboursement_data.obtenir_demande_par_id_data(
    id_demande)


def obtenir_demandes_filtrees_triees(statut_filter: list | None, search_term: str, sort_field: str, sort_order: str,
                                     is_archived: bool, limit: int | None, offset: int):
    return remboursement_data.charger_demandes_data(statut_filter=statut_filter, search_term=search_term,
                                                    sort_field=sort_field, sort_order=sort_order,
                                                    is_archived=is_archived, limit=limit, offset=offset)


def archiver_les_vieilles_demandes() -> int:
    count = 0
    douze_mois = datetime.timedelta(days=365)
    now = datetime.datetime.now()
    demandes_actives, _ = obtenir_demandes_filtrees_triees(None, "", "date_derniere_modification", "ASC", False, None, 0)
    for demande in demandes_actives:
        if demande.statut in [STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE]:
            if demande.date_derniere_modification and (now - demande.date_derniere_modification) > douze_mois:
                succes, _ = archiver_demande_par_id(demande.id_demande)
                if succes: count += 1
    return count


def admin_supprimer_archives_anciennes(age_en_annees: int) -> tuple[int, list[str]]:
    demandes_supprimees, erreurs = 0, []
    date_limite = datetime.datetime.now() - datetime.timedelta(days=age_en_annees * 365.25)
    demandes_archivees, _ = obtenir_demandes_filtrees_triees(None, "", "date_derniere_modification", "ASC", True, None, 0)
    for demande in demandes_archivees:
        if demande.is_archived and demande.date_derniere_modification < date_limite:
            succes, msg = supprimer_demande_par_id(demande.id_demande)
            if succes:
                demandes_supprimees += 1
            else:
                erreurs.append(f"Erreur suppression {demande.id_demande}: {msg}")
    return demandes_supprimees, erreurs


def annuler_demande(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, utilisateur, commentaire, remboursement_workflow.annuler_demande_action)


def refuser_constat_trop_percu(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, utilisateur, commentaire,
                                    remboursement_workflow.refuser_constat_trop_percu_action)


def valider_demande_par_validateur(id_demande: str, commentaire: str | None, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, utilisateur, commentaire,
                                    remboursement_workflow.valider_demande_par_validateur_action)


def refuser_demande_par_validateur(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, utilisateur, commentaire,
                                    remboursement_workflow.refuser_demande_par_validateur_action)


def confirmer_paiement_effectue(id_demande: str, utilisateur: str, commentaire: str | None) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, utilisateur, commentaire, remboursement_workflow.confirmer_paiement_action)


def mlupo_refuser_correction(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    return _generic_workflow_action(demande, utilisateur, commentaire,
                                    remboursement_workflow.mlupo_refuser_correction_action)


def optimiser_base_de_donnees_data() -> tuple[bool, str]: return remboursement_data.optimiser_base_de_donnees_data()


archiver_demande_par_id = remboursement_data.archiver_demande_par_id_data
supprimer_demande_par_id = remboursement_data.supprimer_demande_par_id_data