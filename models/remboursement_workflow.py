import datetime
from . import remboursement_data
from config.settings import (
    STATUT_CREEE, STATUT_TROP_PERCU_CONSTATE,
    STATUT_REFUSEE_CONSTAT_TP, STATUT_ANNULEE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_PAIEMENT_EFFECTUE
)
from .schemas import HistoriqueStatut


def accepter_constat_trop_percu_action(demande, commentaire: str, utilisateur: str) -> tuple[bool, str]:
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


def refuser_constat_trop_percu_action(demande, commentaire: str, utilisateur: str) -> tuple[bool, str]:
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


def annuler_demande_action(demande, commentaire: str, utilisateur: str) -> tuple[bool, str]:
    if demande.statut == STATUT_ANNULEE:
        return False, "Demande déjà annulée."

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


def valider_demande_par_validateur_action(demande, commentaire: str | None, utilisateur: str) -> tuple[bool, str]:
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


def refuser_demande_par_validateur_action(demande, commentaire: str, utilisateur: str) -> tuple[bool, str]:
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


def confirmer_paiement_action(demande, utilisateur: str, commentaire: str | None) -> tuple[bool, str]:
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


def pneri_resoumettre_demande_action(demande, nouveau_commentaire: str, utilisateur: str) -> tuple[bool, str]:
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


def mlupo_resoumettre_constat_action(demande, nouveau_commentaire: str, utilisateur: str) -> tuple[bool, str]:
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


def mlupo_refuser_correction_action(demande, commentaire: str, utilisateur: str) -> tuple[bool, str]:
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