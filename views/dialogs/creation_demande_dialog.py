import os
import customtkinter as ctk
import threading
import shutil
import queue
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.animation_mixin import AnimationMixin
from utils.ui_utils import DragDropFrame


class CreationDemandeDialog(ctk.CTkToplevel, TaskRunnerMixin, AnimationMixin):
    def __init__(self, master, remboursement_controller, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        AnimationMixin.__init__(self, master)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.app_controller = app_controller
        self.submitted = False
        self.copy_operations_in_progress = 0

        self.title("Nouvelle Demande de Remboursement")
        self.geometry("700x800")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self.entries_demande = {}
        self.temp_dossier_path = self.remboursement_controller.creer_dossier_demande_temporaire()
        self.copy_progress_queue = queue.Queue()

        self._build_ui()
        self.fade_in()
        self.after(100, lambda: self.entries_demande["nom"].focus_set())
        self._check_copy_progress()

    def destroy(self):
        if self.temp_dossier_path:
            threading.Thread(target=self.remboursement_controller.supprimer_dossier_temporaire,
                             args=(self.temp_dossier_path,), daemon=True).start()
        super().destroy()

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

        ctk.CTkLabel(form_frame, text="Facture:").grid(row=current_row, column=0, padx=5, pady=(15, 5), sticky="w")

        facture_file_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        facture_file_frame.grid(row=current_row, column=1, sticky="ew")
        facture_file_frame.columnconfigure(1, weight=1)

        btn_facture = ctk.CTkButton(facture_file_frame, text="Choisir Facture", width=120,
                                    command=lambda: self._selectionner_pj("facture"))
        btn_facture.grid(row=0, column=0, padx=(5, 10), pady=5)
        self.label_facture = ctk.CTkLabel(facture_file_frame, textvariable=self.chemin_facture_var, wraplength=300)
        self.label_facture.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        current_row += 1

        drop_zone_facture = DragDropFrame(form_frame,
                                          drop_callback=lambda path: self._selectionner_pj("facture", file_path=path),
                                          text="Déposez la facture ici (optionnel)")
        drop_zone_facture.grid(row=current_row, column=1, padx=5, pady=(0, 10), sticky="ew", rowspan=1)
        current_row += 1

        ctk.CTkLabel(form_frame, text="RIB:").grid(row=current_row, column=0, padx=5, pady=(15, 5), sticky="w")

        rib_file_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        rib_file_frame.grid(row=current_row, column=1, sticky="ew")
        rib_file_frame.columnconfigure(1, weight=1)

        btn_rib = ctk.CTkButton(rib_file_frame, text="Choisir RIB", width=120,
                                command=lambda: self._selectionner_pj("rib"))
        btn_rib.grid(row=0, column=0, padx=(5, 10), pady=5)
        self.label_rib = ctk.CTkLabel(rib_file_frame, textvariable=self.chemin_rib_var, wraplength=300)
        self.label_rib.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        current_row += 1

        drop_zone_rib = DragDropFrame(form_frame,
                                      drop_callback=lambda path: self._selectionner_pj("rib", file_path=path),
                                      text="Déposez le RIB ici (obligatoire)")
        drop_zone_rib.grid(row=current_row, column=1, padx=5, pady=(0, 10), sticky="ew")
        current_row += 1

        self.progress_label = ctk.CTkLabel(form_frame, text="")
        self.progress_label.grid(row=current_row, column=0, columnspan=2, sticky="w", padx=5)
        current_row += 1

        self.progress_bar = ctk.CTkProgressBar(form_frame)
        self.progress_bar.grid(row=current_row, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
        self.progress_bar.set(0)
        self.progress_label.grid_remove()
        self.progress_bar.grid_remove()
        current_row += 1

        self.btn_soumettre = ctk.CTkButton(form_frame, text="Enregistrer la Demande", command=self._soumettre_demande,
                                           height=35)
        self.btn_soumettre.grid(row=current_row, column=0, columnspan=2, pady=(15, 5), padx=5)

    def _selectionner_pj(self, type_pj: str, file_path: str = None):
        if file_path:
            chemin_local = file_path
        else:
            chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image(
                f"Sélectionner {type_pj.title()}")

        if not chemin_local:
            return

        if type_pj == "facture":
            self._extraire_infos_pdf(chemin_local)

        self.copy_operations_in_progress += 1
        self.btn_soumettre.configure(state="disabled", text="Copie de fichier en cours...")
        self.progress_bar.grid()
        self.progress_label.grid()
        self.progress_bar.set(0)

        filename = os.path.basename(chemin_local)
        self.progress_label.configure(text=f"Copie en cours : {filename}")

        label_var = self.chemin_facture_var if type_pj == "facture" else self.chemin_rib_var
        label_var.set(filename)

        subfolder_map = {"facture": "Facture", "rib": "RIB"}
        subfolder_path = os.path.join(self.temp_dossier_path, subfolder_map.get(type_pj))
        if os.path.exists(subfolder_path):
            shutil.rmtree(subfolder_path)

        def copy_task():
            try:
                callback = lambda p: self.copy_progress_queue.put(p)
                self.remboursement_controller.copier_pj_vers_dossier_demande(
                    chemin_local, self.temp_dossier_path, type_pj, callback
                )
                self.copy_progress_queue.put("done")
            except Exception as e:
                self.copy_progress_queue.put(f"error: {e}")

        threading.Thread(target=copy_task, daemon=True).start()

    def _check_copy_progress(self):
        try:
            while not self.copy_progress_queue.empty():
                message = self.copy_progress_queue.get_nowait()
                if isinstance(message, float):
                    self.progress_bar.set(message)
                elif message == "done":
                    self.copy_operations_in_progress -= 1
                    if self.copy_operations_in_progress == 0:
                        self.btn_soumettre.configure(state="normal", text="Enregistrer la Demande")
                        self.progress_bar.grid_remove()
                        self.progress_label.grid_remove()
                elif isinstance(message, str) and message.startswith("error:"):
                    self.app_controller.show_toast(f"Erreur de copie: {message}", "error")
                    self.copy_operations_in_progress -= 1
                    if self.copy_operations_in_progress == 0:
                        self.btn_soumettre.configure(state="normal", text="Enregistrer la Demande")
                        self.progress_bar.grid_remove()
                        self.progress_label.grid_remove()

        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._check_copy_progress)

    def _extraire_infos_pdf(self, chemin_local_pdf):
        if not chemin_local_pdf.lower().endswith(".pdf"):
            return
        try:
            infos = self.remboursement_controller.extraire_info_facture_pdf(chemin_local_pdf)
            if infos.get("nom"):
                self.entries_demande["nom"].delete(0, "end")
                self.entries_demande["nom"].insert(0, infos["nom"])
            if infos.get("prenom"):
                self.entries_demande["prenom"].delete(0, "end")
                self.entries_demande["prenom"].insert(0, infos["prenom"])
            if infos.get("reference"):
                self.entries_demande["reference_facture"].delete(0, "end")
                self.entries_demande["reference_facture"].insert(0, infos["reference"])
        except Exception as e:
            self.app_controller.show_toast(f"Erreur d'analyse du PDF : {e}", "error")

    def _soumettre_demande(self):
        if self.copy_operations_in_progress > 0:
            self.app_controller.show_toast("Veuillez attendre la fin de la copie des fichiers.", "warning")
            return

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
                self.close_animated()
            else:
                self.app_controller.show_toast(message, 'error')
                self.btn_soumettre.configure(state="normal")

        self.run_task(task, on_complete, "Enregistrement de la demande...")