import os
import customtkinter as ctk
import threading
import shutil
import queue
from PIL import Image
import fitz

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
        self.geometry("950x700")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self.entries_demande = {}
        self.temp_dossier_path = self.remboursement_controller.creer_dossier_demande_temporaire()
        self.copy_progress_queue = queue.Queue()

        self.facture_local_path = None
        self.rib_local_path = None
        self.currently_previewing = None

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
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        form_frame = ctk.CTkFrame(self)
        form_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)
        form_frame.columnconfigure(1, weight=1)

        labels_entries = {
            "Nom:": "nom", "Prénom:": "prenom", "Référence Facture:": "reference_facture",
            "Montant demandé (€):": "montant_demande"
        }
        for i, (label_text, key_name) in enumerate(labels_entries.items()):
            ctk.CTkLabel(form_frame, text=label_text).grid(row=i, column=0, padx=10, pady=8, sticky="w")
            entry = ctk.CTkEntry(form_frame)
            entry.grid(row=i, column=1, padx=10, pady=8, sticky="ew")
            self.entries_demande[key_name] = entry

        ctk.CTkLabel(form_frame, text="Description/Raison:").grid(row=4, column=0, padx=10, pady=(8, 0), sticky="nw")
        self.textbox_description = ctk.CTkTextbox(form_frame, height=100)
        self.textbox_description.grid(row=4, column=1, padx=10, pady=8, sticky="ew")

        self.chemin_facture_var = ctk.StringVar(value="Aucun fichier (Optionnel)")
        self.chemin_rib_var = ctk.StringVar(value="Aucun fichier (Obligatoire)")

        ctk.CTkLabel(form_frame, text="Facture:").grid(row=5, column=0, padx=10, pady=(15, 5), sticky="w")
        facture_file_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        facture_file_frame.grid(row=5, column=1, sticky="ew", pady=5, padx=10)
        facture_file_frame.columnconfigure(1, weight=1)
        ctk.CTkButton(facture_file_frame, text="Choisir", width=80,
                      command=lambda: self._selectionner_pj("facture")).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(facture_file_frame, textvariable=self.chemin_facture_var, wraplength=250).pack(side="left",
                                                                                                    fill="x",
                                                                                                    expand=True)
        DragDropFrame(form_frame, drop_callback=lambda p: self._selectionner_pj("facture", p),
                      text="Déposez la facture ici").grid(row=6, column=1, padx=10, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form_frame, text="RIB:").grid(row=7, column=0, padx=10, pady=(15, 5), sticky="w")
        rib_file_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        rib_file_frame.grid(row=7, column=1, sticky="ew", pady=5, padx=10)
        rib_file_frame.columnconfigure(1, weight=1)
        ctk.CTkButton(rib_file_frame, text="Choisir", width=80, command=lambda: self._selectionner_pj("rib")).pack(
            side="left", padx=(0, 10))
        ctk.CTkLabel(rib_file_frame, textvariable=self.chemin_rib_var, wraplength=250).pack(side="left", fill="x",
                                                                                            expand=True)
        DragDropFrame(form_frame, drop_callback=lambda p: self._selectionner_pj("rib", p),
                      text="Déposez le RIB ici").grid(row=8, column=1, padx=10, pady=(0, 10), sticky="ew")

        self.progress_label = ctk.CTkLabel(form_frame, text="")
        self.progress_label.grid(row=9, column=0, columnspan=2, pady=(10, 0), padx=10, sticky="ew")
        self.progress_bar = ctk.CTkProgressBar(form_frame)
        self.progress_bar.grid(row=10, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))
        self.progress_label.grid_remove()
        self.progress_bar.grid_remove()

        self._build_preview_panel()

        self.btn_soumettre = ctk.CTkButton(self, text="Enregistrer la Demande", command=self._soumettre_demande,
                                           height=35)
        self.btn_soumettre.grid(row=1, column=0, columnspan=2, pady=(0, 20))

    def _build_preview_panel(self):
        self.preview_area_frame = ctk.CTkFrame(self, border_width=1)
        self.preview_area_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 20), pady=20)
        self.preview_area_frame.grid_rowconfigure(2, weight=1)
        self.preview_area_frame.grid_columnconfigure(0, weight=1)

        preview_buttons_frame = ctk.CTkFrame(self.preview_area_frame, fg_color="transparent")
        preview_buttons_frame.grid(row=0, column=0, pady=(5, 5), padx=10, sticky="ew")
        preview_buttons_frame.grid_columnconfigure((0, 1), weight=1)

        self.show_facture_button = ctk.CTkButton(preview_buttons_frame, text="Aperçu Facture",
                                                 command=lambda: self._show_preview(self.facture_local_path,
                                                                                    "facture") if self.facture_local_path else None,
                                                 state="disabled")
        self.show_facture_button.grid(row=0, column=0, padx=(0, 5))

        self.show_rib_button = ctk.CTkButton(preview_buttons_frame, text="Aperçu RIB",
                                             command=lambda: self._show_preview(self.rib_local_path,
                                                                                "rib") if self.rib_local_path else None,
                                             state="disabled")
        self.show_rib_button.grid(row=0, column=1, padx=(5, 0))

        self.preview_title_label = ctk.CTkLabel(self.preview_area_frame, text="",
                                                font=ctk.CTkFont(size=14, weight="bold"))
        self.preview_title_label.grid(row=1, column=0, pady=(5, 5), padx=10)

        self.preview_image_label = ctk.CTkLabel(self.preview_area_frame,
                                                text="Sélectionnez un fichier\npour voir un aperçu.",
                                                text_color="gray60")
        self.preview_image_label.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        self.preview_info_label = ctk.CTkLabel(self.preview_area_frame, text="", font=ctk.CTkFont(size=11),
                                               text_color="gray60")
        self.preview_info_label.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 10))

    def _update_preview_buttons(self, new_preview: str | None):
        self.currently_previewing = new_preview

        default_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        selected_color = "green"

        facture_color = default_color if self.currently_previewing != "facture" else selected_color
        rib_color = default_color if self.currently_previewing != "rib" else selected_color

        self.show_facture_button.configure(fg_color=facture_color)
        self.show_rib_button.configure(fg_color=rib_color)

    def _show_preview(self, file_path: str, pj_type: str):
        if not file_path: return

        self._update_preview_buttons(pj_type)
        self.preview_title_label.configure(text=f"Aperçu de la {pj_type.title()}")
        self.preview_image_label.configure(text="Chargement...", image=None)
        self.preview_info_label.configure(text=os.path.basename(file_path))

        def task():
            file_ext = file_path.lower().split('.')[-1]
            preview_max_size = (300, 400)
            if file_ext in ("png", "jpg", "jpeg", "gif", "bmp"):
                with Image.open(file_path) as img:
                    img.thumbnail(preview_max_size, Image.Resampling.LANCZOS)
                    return img
            elif file_ext == "pdf":
                with fitz.open(file_path) as doc:
                    if not doc.page_count: return None
                    page = doc.load_page(0)
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img.thumbnail(preview_max_size, Image.Resampling.LANCZOS)
                    return img
            return None

        def on_complete(image, error):
            if error or not image:
                self.preview_image_label.configure(image=None, text="Aperçu non disponible")
                self.preview_image_label.image = None
                return

            ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            self.preview_image_label.configure(image=ctk_image, text="")
            self.preview_image_label.image = ctk_image
            self.preview_info_label.configure(text=f"{os.path.basename(file_path)}\n({image.width}x{image.height})")

        self.run_task(task, on_complete, show_overlay=False)

    def _selectionner_pj(self, type_pj: str, file_path: str = None):
        if file_path:
            chemin_local = file_path
        else:
            chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image(
                f"Sélectionner {type_pj.title()}")

        if not chemin_local: return

        if type_pj == "facture":
            self.facture_local_path = chemin_local
            self.show_facture_button.configure(state="normal")
            self._extraire_infos_pdf(chemin_local)
        elif type_pj == "rib":
            self.rib_local_path = chemin_local
            self.show_rib_button.configure(state="normal")

        self._show_preview(chemin_local, type_pj)

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
        if os.path.exists(subfolder_path): shutil.rmtree(subfolder_path)

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
        if not chemin_local_pdf.lower().endswith(".pdf"): return
        try:
            infos = self.remboursement_controller.extraire_info_facture_pdf(chemin_local_pdf)
            if infos.get("nom"):
                self.entries_demande["nom"].delete(0, "end");
                self.entries_demande["nom"].insert(0, infos["nom"])
            if infos.get("prenom"):
                self.entries_demande["prenom"].delete(0, "end");
                self.entries_demande["prenom"].insert(0,
                                                      infos[
                                                          "prenom"])
            if infos.get("reference"):
                self.entries_demande["reference_facture"].delete(0, "end");
                self.entries_demande[
                    "reference_facture"].insert(0, infos["reference"])
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