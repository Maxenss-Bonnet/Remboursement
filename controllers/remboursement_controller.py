import os
import shutil
import datetime
import tempfile
import zipfile
import uuid
import re
import logging
from tkinter import filedialog
from typing import Tuple, List

from models import remboursement_model
from utils import pdf_utils
from config.settings import (
    REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR, REMBOURSEMENTS_ATTACHMENTS_DIR,
    STATUT_CREEE, STATUT_TROP_PERCU_CONSTATE,
    STATUT_REFUSEE_CONSTAT_TP, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_VALIDEE, STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE
)
from models.schemas import Remboursement

_log = logging.getLogger(__name__)


class RemboursementController:
    def __init__(self, utilisateur_actuel: str):
        self.utilisateur_actuel = utilisateur_actuel

    def _get_attachment_subfolder_and_prefix(self, type_pj: str) -> tuple[str, str]:
        subfolder_map = {"facture": "Facture", "rib": "RIB", "trop_percu": "Trop_Percu"}
        prefix_map = {"facture": "Facture", "rib": "RIB", "trop_percu": "Preuve_TP"}
        return subfolder_map.get(type_pj, "Autres"), prefix_map.get(type_pj, "PJ")

    def archive_old_requests(self):
        try:
            count = remboursement_model.archiver_les_vieilles_demandes()
            if count > 0:
                _log.info(f"{count} demande(s) ont été automatiquement archivée(s).")
        except Exception as e:
            _log.error("Erreur lors de l'archivage automatique des vieilles demandes.", exc_info=True)

    def extraire_info_facture_pdf(self, chemin_pdf: str) -> dict:
        if not chemin_pdf or not os.path.exists(chemin_pdf):
            return {"nom": "", "prenom": "", "reference": ""}
        return pdf_utils.extraire_infos_facture(chemin_pdf)

    def selectionner_fichier_document_ou_image(self, titre_dialogue="Sélectionner un fichier"):
        filetypes = (("Documents & Images", "*.pdf *.png *.jpg *.jpeg *.bmp"), ("Documents PDF", "*.pdf"),
                     ("Images", "*.png *.jpg *.jpeg *.bmp"), ("Tous les fichiers", "*.*"))
        return filedialog.askopenfilename(title=titre_dialogue, filetypes=filetypes)

    def creer_dossier_demande_temporaire(self) -> str:
        temp_dir_name = f"temp_creation_{uuid.uuid4()}"
        temp_dir_path = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, temp_dir_name)
        os.makedirs(temp_dir_path, exist_ok=True)
        return temp_dir_path

    def supprimer_dossier_temporaire(self, dossier_temporaire: str):
        if not dossier_temporaire or not os.path.isdir(dossier_temporaire): return
        if os.path.basename(dossier_temporaire).startswith("temp_creation_") and os.path.dirname(
                dossier_temporaire) == REMBOURSEMENTS_ATTACHMENTS_DIR:
            try:
                shutil.rmtree(dossier_temporaire, ignore_errors=True)
            except Exception as e:
                _log.warning(f"Impossible de supprimer le dossier temporaire {dossier_temporaire}.", exc_info=True)

    def supprimer_piece_jointe_reseau(self, chemin_fichier_reseau: str):
        if not chemin_fichier_reseau or not os.path.exists(chemin_fichier_reseau): return
        try:
            if os.path.commonpath(
                    [chemin_fichier_reseau, REMBOURSEMENTS_ATTACHMENTS_DIR]) == REMBOURSEMENTS_ATTACHMENTS_DIR:
                os.remove(chemin_fichier_reseau)
        except Exception as e:
            _log.warning(f"Impossible de supprimer la pièce jointe {chemin_fichier_reseau}.", exc_info=True)

    def copier_pj_vers_dossier_demande(self, chemin_local_source: str, dossier_parent_demande: str,
                                       type_pj: str) -> str:
        subfolder, file_prefix = self._get_attachment_subfolder_and_prefix(type_pj)
        destination_subfolder = os.path.join(dossier_parent_demande, subfolder)
        os.makedirs(destination_subfolder, exist_ok=True)

        _, extension = os.path.splitext(chemin_local_source)

        max_version = 0
        version_pattern = re.compile(f"^{re.escape(file_prefix)}_v(\\d+)")
        if os.path.exists(destination_subfolder):
            for item in os.listdir(destination_subfolder):
                match = version_pattern.match(item)
                if match:
                    version_num = int(match.group(1))
                    if version_num > max_version:
                        max_version = version_num

        new_version = max_version + 1
        new_filename = f"{file_prefix}_v{new_version}{extension}"
        destination_path = os.path.join(destination_subfolder, new_filename)

        shutil.copy2(chemin_local_source, destination_path)
        return destination_path

    def ajouter_pj_a_demande_existante(self, id_demande: str, chemin_local_source: str, type_pj: str) -> str:
        demande = self.get_demande(id_demande)
        if not demande: raise ValueError("Demande non trouvée.")

        dossier_demande_path = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, demande.reference_facture_dossier)
        return self.copier_pj_vers_dossier_demande(chemin_local_source, dossier_demande_path, type_pj)

    def valider_donnees_demande(self, nom: str, prenom: str, reference_facture: str, montant_demande_str: str,
                                description: str, dossier_temporaire: str) -> tuple[bool, str, float | None]:
        if not all([nom, prenom, reference_facture, montant_demande_str,
                    description]): return False, "Tous les champs de texte sont obligatoires.", None
        if not os.path.isdir(os.path.join(dossier_temporaire, "RIB")) or not os.listdir(
                os.path.join(dossier_temporaire, "RIB")):
            return False, "La sélection du fichier RIB est obligatoire.", None
        try:
            montant_demande = float(montant_demande_str.replace(",", "."))
            if montant_demande <= 0: return False, "Le montant demandé doit être un nombre positif.", None
        except ValueError:
            return False, "Le montant demandé doit être un nombre valide.", None
        return True, "", montant_demande

    def creer_demande_remboursement(self, nom: str, prenom: str, reference_facture: str, montant_demande: float,
                                    description: str, dossier_temporaire: str) -> tuple[bool, str]:
        succes, message = remboursement_model.creer_nouvelle_demande(nom, prenom, reference_facture, montant_demande,
                                                                     dossier_temporaire, self.utilisateur_actuel,
                                                                     description)
        if succes: return True, f"Demande pour {prenom.title()} {nom.upper()} créée."
        self.supprimer_dossier_temporaire(dossier_temporaire)
        return False, message

    def _relativize_path(self, full_path: str) -> str:
        """Convertit un chemin absolu de PJ en chemin relatif au dossier des PJs."""
        return os.path.relpath(full_path, REMBOURSEMENTS_ATTACHMENTS_DIR).replace('\\', '/')

    def mlupo_accepter_constat(self, id_demande: str, commentaire: str, chemin_pj_trop_percu_full: str) -> tuple[
        bool, str]:
        chemin_relatif = self._relativize_path(chemin_pj_trop_percu_full)
        return remboursement_model.accepter_constat_trop_percu(id_demande, commentaire, self.utilisateur_actuel,
                                                               chemin_relatif)

    def pneri_resoumettre_demande_corrigee(self, id_demande: str, commentaire: str, chemin_facture_full: str | None,
                                           chemin_rib_full: str | None) -> tuple[bool, str]:
        chemin_facture_rel = self._relativize_path(chemin_facture_full) if chemin_facture_full else None
        chemin_rib_rel = self._relativize_path(chemin_rib_full) if chemin_rib_full else None
        return remboursement_model.pneri_resoumettre_demande_corrigee(id_demande, commentaire, chemin_facture_rel,
                                                                      chemin_rib_rel, self.utilisateur_actuel)

    def mlupo_resoumettre_constat_corrige(self, id_demande: str, commentaire: str,
                                          chemin_pj_trop_percu_full: str | None) -> tuple[bool, str]:
        chemin_pj_rel = self._relativize_path(chemin_pj_trop_percu_full) if chemin_pj_trop_percu_full else None
        return remboursement_model.mlupo_resoumettre_constat_corrige(id_demande, commentaire, chemin_pj_rel,
                                                                     self.utilisateur_actuel)

    def get_demandes_filtrees_triees(self, user_roles: list, filter_choice: str, sort_choice: str, search_term: str,
                                     include_archives: bool, limit: int | None = None, offset: int = 0) -> Tuple[
        List[Remboursement], int]:
        sort_map = {"Date de création (récent)": ("date_derniere_modification", "DESC"),
                    "Date de création (ancien)": ("date_derniere_modification", "ASC"),
                    "Montant (décroissant)": ("montant_demande", "DESC"),
                    "Montant (croissant)": ("montant_demande", "ASC"), "Nom du patient (A-Z)": ("nom", "ASC")}
        sort_field, sort_order = sort_map.get(sort_choice, ("date_derniere_modification", "DESC"))

        statut_filter = None
        if not include_archives:
            if filter_choice == "En cours":
                statut_filter = [STATUT_CREEE, STATUT_TROP_PERCU_CONSTATE, STATUT_VALIDEE, STATUT_REFUSEE_CONSTAT_TP,
                                 STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO]
            elif filter_choice == "Terminées et annulées":
                statut_filter = [STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE]
            elif filter_choice == "En attente de mon action":
                statut_filter = [STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE, STATUT_VALIDEE,
                                 STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO]

        if filter_choice == "En attente de mon action" and not include_archives:
            all_potential_demands, _ = remboursement_model.obtenir_demandes_filtrees_triees(
                statut_filter=statut_filter,
                search_term=search_term,
                sort_field=sort_field,
                sort_order=sort_order,
                is_archived=include_archives,
                limit=None,
                offset=0
            )
            demandes_actives = [d for d in all_potential_demands if
                                d.is_active_for(user_roles, self.utilisateur_actuel)]
            total_count = len(demandes_actives)

            start_index = offset
            end_index = offset + limit if limit is not None else total_count
            paginated_demands = demandes_actives[start_index:end_index]

            return paginated_demands, total_count

        demandes, total_count = remboursement_model.obtenir_demandes_filtrees_triees(statut_filter=statut_filter,
                                                                                     search_term=search_term,
                                                                                     sort_field=sort_field,
                                                                                     sort_order=sort_order,
                                                                                     is_archived=include_archives,
                                                                                     limit=limit, offset=offset)

        return demandes, total_count

    def get_demande(self, demande_id: str):
        return remboursement_model.obtenir_demande_par_id(demande_id)

    def supprimer_demande(self, demande_id: str):
        return remboursement_model.supprimer_demande_par_id(demande_id)

    def admin_purge_archives(self, age_en_annees: int):
        return remboursement_model.admin_supprimer_archives_anciennes(age_en_annees)

    def admin_manual_archive(self, demande_id: str):
        return remboursement_model.archiver_demande_par_id(demande_id)

    def admin_optimiser_bdd(self):
        return remboursement_model.optimiser_base_de_donnees_data()

    def get_viewable_attachment_path(self, demande_id: str, relative_path: str) -> tuple[str | None, str | None]:
        demande = self.get_demande(demande_id)
        if not demande: return None, None
        if not demande.is_archived:
            full_path = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, relative_path)
            return full_path, None
        else:
            zip_path = os.path.join(REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR, f"{demande.reference_facture_dossier}.zip")
            if not os.path.exists(zip_path): return None, None
            try:
                temp_dir = tempfile.mkdtemp(prefix="remb-archive-")
                path_parts = relative_path.replace('\\', '/').split('/')
                file_in_zip = '/'.join(path_parts[1:]) if len(path_parts) > 1 else path_parts[0]
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    if file_in_zip in zf.namelist():
                        extracted_path = zf.extract(file_in_zip, path=temp_dir)
                        return extracted_path, temp_dir
                    else:
                        shutil.rmtree(temp_dir)
                        return None, None
            except Exception as e:
                _log.error(f"Erreur lors de l'extraction de l'archive : {e}", exc_info=True)
                return None, None

    def telecharger_copie_piece_jointe(self, chemin_source_pj, temp_dir_a_nettoyer=None):
        try:
            nom_fichier = os.path.basename(chemin_source_pj)
            extension = os.path.splitext(nom_fichier)[1]
            chemin_destination = filedialog.asksaveasfilename(defaultextension=extension, initialfile=nom_fichier,
                                                              filetypes=[
                                                                  (f"{extension.upper()} files", f"*{extension}"),
                                                                  ("All files", "*.*")])
            if chemin_destination:
                shutil.copy2(chemin_source_pj, chemin_destination)
                return True, "Fichier téléchargé avec succès."
            else:
                return False, "Téléchargement annulé."
        except Exception as e:
            return False, f"Erreur lors du téléchargement : {e}"
        finally:
            if temp_dir_a_nettoyer and os.path.isdir(temp_dir_a_nettoyer):
                from utils.archive_utils import cleanup_temp_dir
                cleanup_temp_dir(temp_dir_a_nettoyer)

    def pneri_annuler_demande(self, id_demande: str, commentaire: str) -> tuple[bool, str]:
        return remboursement_model.annuler_demande(id_demande, commentaire, self.utilisateur_actuel)

    def mlupo_refuser_constat(self, id_demande: str, commentaire: str) -> tuple[bool, str]:
        return remboursement_model.refuser_constat_trop_percu(id_demande, commentaire, self.utilisateur_actuel)

    def jdurousset_valider_demande(self, id_demande: str, commentaire: str | None) -> tuple[bool, str]:
        return remboursement_model.valider_demande_par_validateur(id_demande, commentaire, self.utilisateur_actuel)

    def jdurousset_refuser_demande(self, id_demande: str, commentaire: str) -> tuple[bool, str]:
        return remboursement_model.refuser_demande_par_validateur(id_demande, commentaire, self.utilisateur_actuel)

    def pdiop_confirmer_paiement_effectue(self, id_demande: str, commentaire: str | None) -> tuple[bool, str]:
        return remboursement_model.confirmer_paiement_effectue(id_demande, self.utilisateur_actuel, commentaire)

    def mlupo_refuser_correction(self, id_demande: str, commentaire: str) -> tuple[bool, str]:
        return remboursement_model.mlupo_refuser_correction(id_demande, commentaire, self.utilisateur_actuel)