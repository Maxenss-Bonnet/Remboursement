import os
import datetime
import shutil
from . import remboursement_data
from config.settings import (
    REMBOURSEMENTS_ATTACHMENTS_DIR,
    STATUT_CREEE, STATUT_TROP_PERCU_CONSTATE,
    STATUT_REFUSEE_CONSTAT_TP, STATUT_ANNULEE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_PAIEMENT_EFFECTUE
)
from .schemas import Remboursement, HistoriqueStatut


def _ajouter_pj_a_liste(id_demande: str, chemin_pj_source: str, utilisateur: str, type_pj_key_schema: str,
                        prefixe_nom_fichier: str) -> tuple[bool, str]:
    """Copie un fichier, puis met à jour la base de données avec le chemin relatif."""
    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande:
        return False, "Demande non trouvée pour ajouter PJ."

    ref_dossier = demande.reference_facture_dossier
    dossier_cible = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, ref_dossier)
    os.makedirs(dossier_cible, exist_ok=True)

    base_nom_original, extension = os.path.splitext(os.path.basename(chemin_pj_source))
    sanitized_base_name = "".join(c if c.isalnum() or c in ['_', '-'] else '_' for c in base_nom_original)

    version_index = len(getattr(demande, type_pj_key_schema, [])) + 1

    nom_fichier_final = f"{prefixe_nom_fichier}_v{version_index}_{ref_dossier}_{sanitized_base_name}{extension}"
    chemin_destination = os.path.join(dossier_cible, nom_fichier_final)
    chemin_relatif_db = nom_fichier_final  # Le chemin relatif est maintenant juste le nom du fichier

    try:
        shutil.copy2(chemin_pj_source, chemin_destination)
    except Exception as e:
        return False, f"Erreur lors de la copie du fichier : {e}"

    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=demande.statut,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=f"Ajout pièce jointe : {nom_fichier_final}"
    ))

    # On passe le chemin relatif à la couche data pour l'enregistrement BDD
    return remboursement_data.mettre_a_jour_demande_data(demande, chemin_relatif_db, type_pj_key_schema)


def ajouter_piece_jointe_trop_percu_action(id_demande: str, chemin_pj_source: str, utilisateur: str) -> tuple[
    bool, str]:
    # L'ancienne fonction retournait un 3e argument, on le simule pour la compatibilité
    succes, msg = _ajouter_pj_a_liste(id_demande, chemin_pj_source, utilisateur, "chemins_trop_percu_stockes",
                                      "trop_percu")
    return succes, msg


def accepter_constat_trop_percu_action(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_CREEE:
        return False, f"La demande n'est pas au statut '{STATUT_CREEE}'."

    demande.statut = STATUT_TROP_PERCU_CONSTATE
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_TROP_PERCU_CONSTATE,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=commentaire
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)
    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Constat accepté pour {nom_patient}."
    return False, f"Erreur lors de l'acceptation du constat: {msg}"


def refuser_constat_trop_percu_action(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_CREEE:
        return False, f"La demande n'est pas au statut '{STATUT_CREEE}' pour un refus."

    demande.statut = STATUT_REFUSEE_CONSTAT_TP
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_REFUSEE_CONSTAT_TP,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=commentaire
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)
    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Constat refusé pour {nom_patient}."
    return False, f"Erreur lors du refus du constat: {msg}"


def annuler_demande_action(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut == STATUT_ANNULEE: return False, "Demande déjà annulée."

    demande.statut = STATUT_ANNULEE
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_ANNULEE,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=commentaire
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)
    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Demande pour {nom_patient} annulée."
    return False, f"Erreur lors de l'annulation: {msg}"


def valider_demande_par_validateur_action(id_demande: str, commentaire: str | None, utilisateur: str) -> tuple[
    bool, str]:
    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_TROP_PERCU_CONSTATE:
        return False, f"La demande n'est pas au statut '{STATUT_TROP_PERCU_CONSTATE}'."

    demande.statut = STATUT_VALIDEE
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_VALIDEE,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=commentaire if commentaire and commentaire.strip() else "Demande validée par validateur."
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)
    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Demande pour {nom_patient} validée."
    return False, f"Erreur lors de la validation: {msg}"


def refuser_demande_par_validateur_action(id_demande: str, commentaire: str, utilisateur: str) -> tuple[
    bool, str]:
    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_TROP_PERCU_CONSTATE:
        return False, f"La demande n'est pas au statut '{STATUT_TROP_PERCU_CONSTATE}'."

    demande.statut = STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=commentaire
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)
    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Demande pour {nom_patient} refusée et renvoyée pour correction."
    return False, f"Erreur lors du refus par le validateur: {msg}"


def confirmer_paiement_action(id_demande: str, utilisateur: str, commentaire: str | None) -> tuple[bool, str]:
    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_VALIDEE:
        return False, f"La demande n'est pas au statut '{STATUT_VALIDEE}'."

    now = datetime.datetime.now()
    demande.statut = STATUT_PAIEMENT_EFFECTUE
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = now
    demande.date_paiement_effectue = now
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_PAIEMENT_EFFECTUE,
        date=now,
        par_utilisateur=utilisateur,
        commentaire=commentaire if commentaire and commentaire.strip() else "Paiement effectué."
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)
    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Paiement confirmé pour {nom_patient}."
    return False, f"Erreur lors de la confirmation du paiement: {msg}"


def pneri_resoumettre_demande_action(id_demande: str, nouveau_commentaire: str,
                                     nouveau_chemin_facture_source: str | None,
                                     nouveau_chemin_rib_source: str | None,
                                     utilisateur: str) -> tuple[bool, str]:
    if nouveau_chemin_facture_source:
        succes, msg = _ajouter_pj_a_liste(id_demande, nouveau_chemin_facture_source, utilisateur,
                                          "chemins_factures_stockees", "facture")
        if not succes: return False, msg
    if nouveau_chemin_rib_source:
        succes, msg = _ajouter_pj_a_liste(id_demande, nouveau_chemin_rib_source, utilisateur, "chemins_rib_stockes",
                                          "rib")
        if not succes: return False, msg

    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_REFUSEE_CONSTAT_TP:
        return False, f"La demande n'est pas au statut '{STATUT_REFUSEE_CONSTAT_TP}'."

    demande.statut = STATUT_CREEE
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_CREEE,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=f"Demande corrigée et resoumise: {nouveau_commentaire}"
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)
    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Demande pour {nom_patient} corrigée et resoumise."
    return False, f"Erreur lors de la resoumission : {msg}"


def mlupo_resoumettre_constat_action(id_demande: str, nouveau_commentaire: str,
                                     nouveau_chemin_pj_trop_percu_source: str | None,
                                     utilisateur: str) -> tuple[bool, str]:
    if nouveau_chemin_pj_trop_percu_source:
        succes, msg = ajouter_piece_jointe_trop_percu_action(id_demande, nouveau_chemin_pj_trop_percu_source,
                                                             utilisateur)
        if not succes: return False, msg

    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande: return False, "Demande non trouvée."
    if demande.statut != STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO:
        return False, f"La demande n'est pas au statut '{STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO}'."

    demande.statut = STATUT_TROP_PERCU_CONSTATE
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_TROP_PERCU_CONSTATE,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=f"Constat corrigé et resoumis: {nouveau_commentaire}"
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)

    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Constat pour {nom_patient} corrigé et resoumis."
    return False, f"Erreur lors de la resoumission: {msg}"


def mlupo_refuser_correction_action(id_demande: str, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    demande = remboursement_data.obtenir_demande_par_id_data(id_demande)
    if not demande:
        return False, "Demande non trouvée."

    if demande.statut != STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO:
        return False, f"L'action n'est pas possible depuis le statut '{demande.statut}'."

    demande.statut = STATUT_REFUSEE_CONSTAT_TP
    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=STATUT_REFUSEE_CONSTAT_TP,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=f"Correction refusée et renvoyée au demandeur : {commentaire}"
    ))

    succes, msg = remboursement_data.mettre_a_jour_demande_data(demande)
    if succes:
        nom_patient = f"{demande.prenom} {demande.nom}".strip()
        return True, f"Demande pour {nom_patient} renvoyée au demandeur."
    return False, f"Erreur lors du renvoi de la demande au demandeur."