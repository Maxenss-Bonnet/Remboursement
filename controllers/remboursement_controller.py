from models import remboursement_model
from utils import pdf_utils
from tkinter import filedialog
import os
import shutil
import datetime
import tempfile
import zipfile

from config.settings import (
    REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR, REMBOURSEMENTS_ATTACHMENTS_DIR
)


class RemboursementController:
    def __init__(self, utilisateur_actuel: str):
        self.utilisateur_actuel = utilisateur_actuel

    def archive_old_requests(self):
        count = remboursement_model.archiver_les_vieilles_demandes()
        if count > 0:
            print(f"{count} demande(s) ont été archivée(s).")

    def admin_optimiser_bdd(self):
        return remboursement_model.optimiser_base_de_donnees_data()

    def extraire_info_facture_pdf(self, chemin_pdf: str) -> dict:
        if not chemin_pdf or not os.path.exists(chemin_pdf):
            return {"nom": "", "prenom": "", "reference": ""}
        return pdf_utils.extraire_infos_facture(chemin_pdf)

    def selectionner_fichier_document_ou_image(self, titre_dialogue="Sélectionner un fichier"):
        filetypes = (
            ("Documents & Images", "*.pdf *.png *.jpg *.jpeg *.bmp"),
            ("Documents PDF", "*.pdf"),
            ("Images", "*.png *.jpg *.jpeg *.bmp"),
            ("Tous les fichiers", "*.*")
        )
        return filedialog.askopenfilename(title=titre_dialogue, filetypes=filetypes)

    def _valider_donnees_demande(self, nom: str, prenom: str, reference_facture: str, montant_demande_str: str,
                                 description: str, chemin_facture_source: str | None, chemin_rib_source: str
                                 ) -> tuple[bool, str, float | None]:
        if not all([nom, prenom, reference_facture, montant_demande_str, description]):
            return False, "Tous les champs de texte (sauf facture) sont obligatoires.", None
        if not chemin_rib_source:
            return False, "La sélection du fichier RIB est obligatoire.", None
        try:
            montant_demande = float(montant_demande_str.replace(",", "."))
            if montant_demande <= 0: return False, "Le montant demandé doit être un nombre positif.", None
        except ValueError:
            return False, "Le montant demandé doit être un nombre valide.", None
        if chemin_facture_source and not os.path.exists(chemin_facture_source):
            return False, f"Fichier facture non trouvé : {chemin_facture_source}", None
        if not os.path.exists(chemin_rib_source):
            return False, f"Fichier RIB non trouvé : {chemin_rib_source}", None
        return True, "", montant_demande

    def creer_demande_remboursement(
            self, nom: str, prenom: str, reference_facture: str, montant_demande: float,
            description: str, chemin_facture_source: str | None, chemin_rib_source: str
    ) -> tuple[bool, str]:
        succes, message = remboursement_model.creer_nouvelle_demande(
            nom, prenom, reference_facture, montant_demande,
            chemin_facture_source, chemin_rib_source, self.utilisateur_actuel, description
        )
        if succes:
            return True, f"Demande pour {prenom.title()} {nom.upper()} créée."
        else:
            return False, message

    def get_toutes_les_demandes(self, include_archives: bool = False):
        return remboursement_model.obtenir_toutes_les_demandes(include_archives)

    def get_demande(self, demande_id: str):
        return remboursement_model.obtenir_demande_par_id(demande_id)

    def supprimer_demande(self, demande_id: str):
        return remboursement_model.supprimer_demande_par_id(demande_id)

    def admin_purge_archives(self, age_en_annees: int):
        return remboursement_model.admin_supprimer_archives_anciennes(age_en_annees)

    def admin_manual_archive(self, demande_id: str):
        return remboursement_model.archiver_demande_par_id(demande_id)

    def get_viewable_attachment_path(self, demande_id: str, relative_path: str) -> tuple[str | None, str | None]:
        demande = self.get_demande(demande_id)
        if not demande:
            return None, None

        if not demande.is_archived:
            full_path = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, relative_path)
            return full_path, None
        else:
            zip_path = os.path.join(REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR, f"{demande.reference_facture_dossier}.zip")
            if not os.path.exists(zip_path):
                return None, None
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
                print(f"Erreur lors de l'extraction de l'archive : {e}")
                return None, None

    def telecharger_copie_piece_jointe(self, chemin_source_pj, temp_dir_a_nettoyer=None):
        try:
            nom_fichier = os.path.basename(chemin_source_pj)
            extension = os.path.splitext(nom_fichier)[1]
            chemin_destination = filedialog.asksaveasfilename(
                defaultextension=extension, initialfile=nom_fichier,
                filetypes=[(f"{extension.upper()} files", f"*{extension}"), ("All files", "*.*")]
            )
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

    def mlupo_accepter_constat(self, id_demande: str, commentaire: str, chemin_pj_trop_percu: str) -> tuple[bool, str]:
        return remboursement_model.accepter_constat_trop_percu(id_demande, commentaire, self.utilisateur_actuel,
                                                               chemin_pj_trop_percu)

    def mlupo_refuser_constat(self, id_demande: str, commentaire: str) -> tuple[bool, str]:
        return remboursement_model.refuser_constat_trop_percu(id_demande, commentaire, self.utilisateur_actuel)

    def jdurousset_valider_demande(self, id_demande: str, commentaire: str | None) -> tuple[bool, str]:
        return remboursement_model.valider_demande_par_validateur(id_demande, commentaire, self.utilisateur_actuel)

    def jdurousset_refuser_demande(self, id_demande: str, commentaire: str) -> tuple[bool, str]:
        return remboursement_model.refuser_demande_par_validateur(id_demande, commentaire, self.utilisateur_actuel)

    def pdiop_confirmer_paiement_effectue(self, id_demande: str, commentaire: str | None) -> tuple[bool, str]:
        return remboursement_model.confirmer_paiement_effectue(id_demande, self.utilisateur_actuel, commentaire)

    def pneri_resoumettre_demande_corrigee(self, id_demande: str, commentaire: str, nouveau_chemin_facture: str | None,
                                           nouveau_chemin_rib: str | None) -> tuple[bool, str]:
        return remboursement_model.pneri_resoumettre_demande_corrigee(id_demande, commentaire, nouveau_chemin_facture,
                                                                      nouveau_chemin_rib, self.utilisateur_actuel)

    def mlupo_resoumettre_constat_corrige(self, id_demande: str, commentaire: str,
                                          nouveau_chemin_pj_trop_percu: str | None) -> tuple[bool, str]:
        return remboursement_model.mlupo_resoumettre_constat_corrige(id_demande, commentaire,
                                                                     nouveau_chemin_pj_trop_percu,
                                                                     self.utilisateur_actuel)

    def mlupo_refuser_correction(self, id_demande: str, commentaire: str) -> tuple[bool, str]:
        return remboursement_model.mlupo_refuser_correction(id_demande, commentaire, self.utilisateur_actuel)