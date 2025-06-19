import os
import customtkinter as ctk
import threading
import shutil
from views.mixins.task_runner_mixin import TaskRunnerMixin


class CreationDemandeDialog(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, remboursement_controller, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.app_controller = app_controller
        self.submitted = False
        self.copy_operations_in_progress = 0

        self.title("Nouvelle Demande de Remboursement")
        self.geometry("650x650")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.entries_demande = {}
        self.temp_dossier_path = self.remboursement_controller.creer_dossier_demande_temporaire()

        self._build_ui()
        self.after(100, lambda: self.entries_demande["nom"].focus_set())

    def _build_ui(self):
        form_frame = ctk.CTkFrame(self)
        form_frame.pack(expand=True, fill="both", padx=20, pady=20)
        form_frame.columnconfigure(1, weight=1)

        current_row = 0
        labels_entries = {
            "Nom:": "nom", "Prénom:": "prenom", "Référence Facture:": "reference_facture",
            "Montant demandé (€):": "montant_demande"
        }

        for label_text, key_name in labels_entries.items():
            ctk.CTkLabel(form_frame, text=label_text).grid(row=current_row, column=0, padx=5, pady=8, sticky="w")
            entry = ctk.CTkEntry(form_frame, width=350)
            entry.grid(row=current_row, column=1, padx=5, pady=8, sticky="ew")
            self.entries_demande[key_name] = entry
            current_row += 1

        ctk.CTkLabel(form_frame, text="Description/Raison:").grid(row=current_row, column=0, padx=5, pady=(8, 0),
                                                                  sticky="nw")
        self.textbox_description = ctk.CTkTextbox(form_frame, width=350, height=100)
        self.textbox_description.grid(row=current_row, column=1, padx=5, pady=8, sticky="ew")
        current_row += 1

        self.chemin_facture_var = ctk.StringVar(value="Aucun fichier sélectionné (Optionnel)")
        self.chemin_rib_var = ctk.StringVar(value="Aucun fichier sélectionné (Obligatoire)")

        btn_facture = ctk.CTkButton(form_frame, text="Choisir Facture",
                                    command=lambda: self._selectionner_pj("facture"))
        btn_facture.grid(row=current_row, column=0, padx=5, pady=10, sticky="w")
        self.label_facture = ctk.CTkLabel(form_frame, textvariable=self.chemin_facture_var, wraplength=300)
        self.label_facture.grid(row=current_row, column=1, padx=5, pady=10, sticky="ew")
        current_row += 1

        btn_rib = ctk.CTkButton(form_frame, text="Choisir RIB", command=lambda: self._selectionner_pj("rib"))
        btn_rib.grid(row=current_row, column=0, padx=5, pady=10, sticky="w")
        self.label_rib = ctk.CTkLabel(form_frame, textvariable=self.chemin_rib_var, wraplength=300)
        self.label_rib.grid(row=current_row, column=1, padx=5, pady=10, sticky="ew")
        current_row += 1

        self.btn_soumettre = ctk.CTkButton(form_frame, text="Enregistrer la Demande", command=self._soumettre_demande,
                                           height=35)
        self.btn_soumettre.grid(row=current_row, column=0, columnspan=2, pady=25, padx=5)

    def _selectionner_pj(self, type_pj: str):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image(
            f"Sélectionner {type_pj.title()}")
        if not chemin_local:
            return

        self.copy_operations_in_progress += 1
        self.btn_soumettre.configure(state="disabled", text="Copie de fichier en cours...")

        label_var = self.chemin_facture_var if type_pj == "facture" else self.chemin_rib_var
        label_widget = self.label_facture if type_pj == "facture" else self.label_rib

        subfolder_map = {"facture": "Facture", "rib": "RIB"}
        subfolder_path = os.path.join(self.temp_dossier_path, subfolder_map.get(type_pj))
        if os.path.exists(subfolder_path):
            shutil.rmtree(subfolder_path)

        label_widget.configure(text_color="orange")
        label_var.set(f"Copie en cours: {os.path.basename(chemin_local)}...")

        if type_pj == "facture":
            self._extraire_infos_pdf(chemin_local)

        def task():
            return self.remboursement_controller.copier_pj_vers_dossier_demande(chemin_local, self.temp_dossier_path,
                                                                                type_pj)

        def on_complete(result, error):
            try:
                if error:
                    label_var.set("Échec copie !")
                    label_widget.configure(text_color="red")
                else:
                    label_var.set(os.path.basename(chemin_local))
                    label_widget.configure(text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            finally:
                self.copy_operations_in_progress -= 1
                if self.copy_operations_in_progress == 0:
                    self.btn_soumettre.configure(state="normal", text="Enregistrer la Demande")

        self.run_task(task, on_complete, "Copie du fichier...", show_overlay=False)

    def _extraire_infos_pdf(self, chemin_local_pdf):
        if not chemin_local_pdf.lower().endswith(".pdf"): return

        def task():
            return self.remboursement_controller.extraire_info_facture_pdf(chemin_local_pdf)

        def on_complete(infos, error):
            if error: self.app_controller.show_toast(f"Erreur d'analyse PDF: {error}", "error"); return
            if infos:
                if infos.get("nom"): self.entries_demande["nom"].delete(0, "end"); self.entries_demande["nom"].insert(0,
                                                                                                                      infos.get(
                                                                                                                          "nom"))
                if infos.get("prenom"): self.entries_demande["prenom"].delete(0, "end"); self.entries_demande[
                    "prenom"].insert(0, infos.get("prenom"))
                if infos.get("reference"): self.entries_demande["reference_facture"].delete(0, "end");
                self.entries_demande["reference_facture"].insert(0, infos.get("reference"))

        self.run_task(task, on_complete, "Analyse du PDF...", show_overlay=False)

    def _soumettre_demande(self):
        self.btn_soumettre.configure(state="disabled")
        nom = self.entries_demande["nom"].get()
        prenom = self.entries_demande["prenom"].get()
        ref_facture = self.entries_demande["reference_facture"].get()
        montant_str = self.entries_demande["montant_demande"].get()
        description = self.textbox_description.get("1.0", "end-1c").strip()

        is_valid, error_message, montant_valide = self.remboursement_controller.valider_donnees_demande(
            nom, prenom, ref_facture, montant_str, description, self.temp_dossier_path
        )

        if not is_valid:
            self.app_controller.show_toast(error_message, "error")
            self.btn_soumettre.configure(state="normal")
            return

        def task():
            dossier = self.temp_dossier_path
            self.temp_dossier_path = None
            return self.remboursement_controller.creer_demande_remboursement(
                nom, prenom, ref_facture, montant_valide, description, dossier
            )

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", 'error')
                self.btn_soumettre.configure(state="normal")
                return

            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success')
                self.submitted = True
                self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')
                self.btn_soumettre.configure(state="normal")

        self.run_task(task, on_complete, "Enregistrement de la demande...")

    def _on_close(self):
        if self.temp_dossier_path:
            threading.Thread(target=self.remboursement_controller.supprimer_dossier_temporaire,
                             args=(self.temp_dossier_path,), daemon=True).start()
        self.destroy()