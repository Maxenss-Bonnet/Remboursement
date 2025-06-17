import os
import customtkinter as ctk
import threading
from views.mixins.task_runner_mixin import TaskRunnerMixin


class CreationDemandeDialog(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, remboursement_controller, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.app_controller = app_controller
        self.submitted = False

        self.title("Nouvelle Demande de Remboursement")
        self.geometry("650x650")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.chemin_facture_reseau_temp = None
        self.chemin_rib_reseau_temp = None
        self.entries_demande = {}

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

        btn_facture = ctk.CTkButton(form_frame, text="Choisir Facture", command=self._selectionner_facture)
        btn_facture.grid(row=current_row, column=0, padx=5, pady=10, sticky="w")
        self.label_facture = ctk.CTkLabel(form_frame, textvariable=self.chemin_facture_var, wraplength=300)
        self.label_facture.grid(row=current_row, column=1, padx=5, pady=10, sticky="ew")
        current_row += 1

        btn_rib = ctk.CTkButton(form_frame, text="Choisir RIB", command=self._selectionner_rib)
        btn_rib.grid(row=current_row, column=0, padx=5, pady=10, sticky="w")
        self.label_rib = ctk.CTkLabel(form_frame, textvariable=self.chemin_rib_var, wraplength=300)
        self.label_rib.grid(row=current_row, column=1, padx=5, pady=10, sticky="ew")
        current_row += 1

        btn_soumettre = ctk.CTkButton(form_frame, text="Enregistrer la Demande", command=self._soumettre_demande,
                                      height=35)
        btn_soumettre.grid(row=current_row, column=0, columnspan=2, pady=25, padx=5)

    def _selectionner_facture(self):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image("Sélectionner la Facture")
        if not chemin_local:
            return

        # Lancer la suppression de l'ancien fichier temporaire s'il existe
        if self.chemin_facture_reseau_temp:
            self.run_task(
                lambda path=self.chemin_facture_reseau_temp: self.remboursement_controller.supprimer_fichier_temporaire_reseau(path),
                on_complete=None, show_overlay=False
            )
        self.chemin_facture_reseau_temp = None

        original_text_color = self.label_facture.cget("text_color")
        self.chemin_facture_var.set(f"Copie en cours: {os.path.basename(chemin_local)}...")
        self.label_facture.configure(text_color="orange")

        # Lancer l'analyse du PDF immédiatement sur le fichier local
        self._extraire_infos_pdf(chemin_local)

        # Lancer la copie en tâche de fond
        def task_copy():
            return self.remboursement_controller.preparer_piece_jointe_reseau(chemin_local)

        def on_complete_copy(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur de copie: {error}", "error")
                self.chemin_facture_var.set("Échec de la copie !")
                self.label_facture.configure(text_color="red")
                self.chemin_facture_reseau_temp = None
                return

            self.chemin_facture_reseau_temp = result
            self.chemin_facture_var.set(os.path.basename(self.chemin_facture_reseau_temp))
            self.label_facture.configure(text_color=original_text_color)

        self.run_task(task_copy, on_complete_copy, show_overlay=False)

    def _extraire_infos_pdf(self, chemin_local_pdf):
        if not chemin_local_pdf.lower().endswith(".pdf"):
            return

        def task_extract():
            return self.remboursement_controller.extraire_info_facture_pdf(chemin_local_pdf)

        def on_complete_extract(infos, error):
            if error:
                self.app_controller.show_toast(f"Erreur d'analyse PDF: {error}", "error")
                return
            if infos:
                if infos.get("nom"):
                    self.entries_demande["nom"].delete(0, "end")
                    self.entries_demande["nom"].insert(0, infos.get("nom"))
                if infos.get("prenom"):
                    self.entries_demande["prenom"].delete(0, "end")
                    self.entries_demande["prenom"].insert(0, infos.get("prenom"))
                if infos.get("reference"):
                    self.entries_demande["reference_facture"].delete(0, "end")
                    self.entries_demande["reference_facture"].insert(0, infos.get("reference"))

        self.run_task(task_extract, on_complete_extract, show_overlay=False)

    def _selectionner_rib(self):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image("Sélectionner le RIB")
        if not chemin_local:
            return

        if self.chemin_rib_reseau_temp:
            self.run_task(
                lambda path=self.chemin_rib_reseau_temp: self.remboursement_controller.supprimer_fichier_temporaire_reseau(path),
                on_complete=None, show_overlay=False
            )
        self.chemin_rib_reseau_temp = None

        original_text_color = self.label_rib.cget("text_color")
        self.chemin_rib_var.set(f"Copie en cours: {os.path.basename(chemin_local)}...")
        self.label_rib.configure(text_color="orange")

        def task():
            return self.remboursement_controller.preparer_piece_jointe_reseau(chemin_local)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur de copie: {error}", "error")
                self.chemin_rib_var.set("Échec de la copie !")
                self.label_rib.configure(text_color="red")
                self.chemin_rib_reseau_temp = None
                return

            self.chemin_rib_reseau_temp = result
            self.chemin_rib_var.set(os.path.basename(self.chemin_rib_reseau_temp))
            self.label_rib.configure(text_color=original_text_color)

        self.run_task(task, on_complete, show_overlay=False)

    def _soumettre_demande(self):
        nom = self.entries_demande["nom"].get()
        prenom = self.entries_demande["prenom"].get()
        ref_facture = self.entries_demande["reference_facture"].get()
        montant_str = self.entries_demande["montant_demande"].get()
        description = self.textbox_description.get("1.0", "end-1c").strip()

        is_valid, error_message, montant_valide = self.remboursement_controller.valider_donnees_demande(
            nom, prenom, ref_facture, montant_str, description,
            self.chemin_facture_reseau_temp, self.chemin_rib_reseau_temp
        )

        if not is_valid:
            self.app_controller.show_toast(error_message, "error")
            return

        def task():
            # Une fois soumis, les fichiers ne sont plus considérés comme "temporaires"
            facture_path = self.chemin_facture_reseau_temp
            rib_path = self.chemin_rib_reseau_temp
            self.chemin_facture_reseau_temp = None
            self.chemin_rib_reseau_temp = None

            return self.remboursement_controller.creer_demande_remboursement(
                nom, prenom, ref_facture, montant_valide, description,
                facture_path, rib_path
            )

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", 'error')
                return

            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success')
                self.submitted = True
                self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')

        self.run_task(task, on_complete, "Enregistrement de la demande...")

    def _on_close(self):
        files_to_delete = []
        if self.chemin_facture_reseau_temp:
            files_to_delete.append(self.chemin_facture_reseau_temp)
        if self.chemin_rib_reseau_temp:
            files_to_delete.append(self.chemin_rib_reseau_temp)

        if files_to_delete:
            def delete_task():
                for path in files_to_delete:
                    self.remboursement_controller.supprimer_fichier_temporaire_reseau(path)
            threading.Thread(target=delete_task, daemon=True).start()

        self.destroy()