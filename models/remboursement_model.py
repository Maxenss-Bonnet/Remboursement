import os
import datetime
import uuid
import shutil
from . import remboursement_data
from . import remboursement_workflow
from config.settings import (
    REMBOURSEMENTS_ATTACHMENTS_DIR,
    STATUT_CREEE,
    STATUT_PAIEMENT_EFFECTUE,
    STATUT_ANNULEE
)
from .schemas import Remboursement as RemboursementSchema, HistoriqueStatut


def _copy_and_version_attachment(source_path: str, demande_id: str, subfolder: str, file_prefix: str) -> str | None:
    """
    Copie un fichier dans le bon sous-dossier avec un nom versionné.
    Retourne le chemin relatif pour la BDD (ex: 'D2025.../RIB/RIB_v1.pdf').
    """
    if not source_path or not os.path.exists(source_path):
        return None

    destination_folder = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, demande_id, subfolder)
    os.makedirs(destination_folder, exist_ok=True)

    _, extension = os.path.splitext(source_path)

    # Compter les fichiers existants pour déterminer la nouvelle version
    version = 1
    for item in os.listdir(destination_folder):
        if item.startswith(file_prefix) and item.endswith(extension):
            version += 1

    new_filename = f"{file_prefix}_v{version}{extension}"
    destination_path = os.path.join(destination_folder, new_filename)

    try:
        shutil.copy2(source_path, destination_path)
        # Retourne le chemin relatif complet depuis la base des attachments
        return os.path.join(demande_id, subfolder, new_filename)
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

    chemins_factures_relatifs = []
    if chemin_facture_source:
        path = _copy_and_version_attachment(chemin_facture_source, id_unique_demande, "Facture", "Facture")
        if path: chemins_factures_relatifs.append(path)

    chemins_rib_relatifs = []
    if chemin_rib_source:
        path = _copy_and_version_attachment(chemin_rib_source, id_unique_demande, "RIB", "RIB")
        if not path:
            return False, "Erreur critique lors de la copie du RIB."
        chemins_rib_relatifs.append(path)

    now = datetime.datetime.now()

    demande_a_creer = RemboursementSchema(
        id_demande=id_unique_demande,
        nom=nom.upper() if nom else None,
        prenom=prenom.title() if prenom else None,
        reference_facture=reference_facture,
        reference_facture_dossier=id_unique_demande,
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


def ajouter_piece_jointe_trop_percu(id_demande: str, chemin_pj_source: str, utilisateur: str) -> tuple[bool, str]:
    demande = obtenir_demande_par_id(id_demande)
    if not demande:
        return False, "Demande non trouvée."

    chemin_relatif = _copy_and_version_attachment(chemin_pj_source, demande.id_demande, "Trop_Percu", "Preuve_TP")

    if not chemin_relatif:
        return False, "Erreur lors de la copie de la preuve de trop-perçu."

    demande.derniere_modification_par = utilisateur
    demande.date_derniere_modification = datetime.datetime.now()
    demande.historique_statuts.append(HistoriqueStatut(
        statut=demande.statut,
        date=demande.date_derniere_modification,
        par_utilisateur=utilisateur,
        commentaire=f"Ajout pièce jointe : {os.path.basename(chemin_relatif)}"
    ))
    return remboursement_data.mettre_a_jour_demande_data(demande, chemin_relatif, 'trop_percu')


# Alias pour les fonctions
archiver_demande_par_id = remboursement_data.archiver_demande_par_id_data
supprimer_demande_par_id = remboursement_data.supprimer_demande_par_id_data
accepter_constat_trop_percu = remboursement_workflow.accepter_constat_trop_percu_action
refuser_constat_trop_percu = remboursement_workflow.refuser_constat_trop_percu_action
annuler_demande = remboursement_workflow.annuler_demande_action
valider_demande_par_validateur = remboursement_workflow.valider_demande_par_validateur_action
refuser_demande_par_validateur = remboursement_workflow.refuser_demande_par_validateur_action
confirmer_paiement_effectue = remboursement_workflow.confirmer_paiement_action
pneri_resoumettre_demande_corrigee = remboursement_workflow.pneri_resoumettre_demande_action
mlupo_resoumettre_constat_corrige = remboursement_workflow.mlupo_resoumettre_constat_action
mlupo_refuser_correction = remboursement_workflow.mlupo_refuser_correction_action