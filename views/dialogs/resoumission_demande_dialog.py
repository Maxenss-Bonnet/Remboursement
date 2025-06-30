import os
import customtkinter as ctk
import threading
import queue
from PIL import Image, ImageGrab
import fitz
import tempfile

from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.animation_mixin import AnimationMixin
from utils.ui_utils import DragDropFrame


class ResoumissionDemandeDialog(ctk.CTkToplevel, TaskRunnerMixin, AnimationMixin):
    def __init__(self, master, remboursement_controller, id_demande, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        AnimationMixin.__init__(self, master)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.id_demande = id_demande
        self.app_controller = app_controller
        self.submitted = False
        self.copy_operations_in_progress = 0
        self.copy_progress_queue = queue.Queue()

        self.title(f"Corriger Demande {id_demande[:8]}")
        self.geometry("950x700")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self.chemin_facture_reseau = None
        self.chemin_rib_reseau = None
        self.facture_local_path = None
        self.rib_local_path = None
        self.currently_previewing = None

        self.keep_facture_var = ctk.BooleanVar(value=True)
        self.keep_rib_var = ctk.BooleanVar(value=True)

        self.chemin_facture_var = ctk.StringVar(value="Ancienne facture conservée")
        self.chemin_rib_var = ctk.StringVar(value="Ancien RIB conservé")

        self._load_data_and_build_ui()
        self.fade_in()
        self._check_copy_progress()

    def destroy(self):
        paths_to_delete = [self.chemin_facture_reseau, self.chemin_rib_reseau]
        for path in paths_to_delete:
            if path: threading.Thread(target=self.remboursement_controller.supprimer_piece_jointe_reseau,
                                      args=(path,), daemon=True).start()
        super().destroy()

    def _load_data_and_build_ui(self):
        def task():
            return self.remboursement_controller.get_demande(self.id_demande)

        def on_complete(demande, error):
            if error or not demande:
                self.app_controller.show_toast("Impossible de charger les données de la demande.", "error")
                self.close_animated()
                return
            self._build_ui(demande)

        self.run_task(task, on_complete, "Chargement de la demande...")

    def _build_ui(self, demande):
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        form_frame = ctk.CTkFrame(self)
        form_frame.grid(row=0, column=0, sticky="nsew", padx=(20, 10), pady=20)

        ctk.CTkLabel(form_frame, text="Veuillez fournir les documents mis à jour et un commentaire.").pack(
            pady=(10, 15), padx=10)

        facture_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        facture_frame.pack(fill="x", pady=(5, 0), padx=10)
        facture_frame.columnconfigure(2, weight=1)
        self.btn_sel_facture = ctk.CTkButton(facture_frame, text="Nlle Facture",
                                             command=lambda: self._sel_new_pj("facture"), state="disabled")
        self.btn_sel_facture.grid(row=0, column=0, padx=(0, 5))
        ctk.CTkButton(facture_frame, text="Coller",
                      command=lambda: self._coller_pj("facture"), state="disabled").grid(row=0, column=1, padx=(0, 10))

        self.lbl_facture_sel = ctk.CTkLabel(facture_frame, textvariable=self.chemin_facture_var,
                                            text_color="gray", anchor="w", wraplength=300)
        self.lbl_facture_sel.grid(row=0, column=2, sticky="ew")

        drop_zone_facture = DragDropFrame(form_frame,
                                          drop_callback=lambda p: self._sel_new_pj("facture", file_path=p),
                                          text="Déposez la nouvelle facture ici")
        drop_zone_facture.pack(fill="x", pady=5, padx=10)

        self.cb_keep_facture = ctk.CTkCheckBox(form_frame, variable=self.keep_facture_var,
                                               command=self._toggle_facture_ui)
        if demande.chemins_factures_stockees:
            self.cb_keep_facture.configure(
                text=f"Conserver facture: {os.path.basename(demande.chemins_factures_stockees[-1])}")
        else:
            self.cb_keep_facture.configure(text="Pas de facture précédente", state="disabled");
            self.keep_facture_var.set(False);
            self._toggle_facture_ui()
        self.cb_keep_facture.pack(anchor="w", padx=20, pady=(5, 20))

        rib_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        rib_frame.pack(fill="x", pady=(5, 0), padx=10)
        rib_frame.columnconfigure(2, weight=1)
        self.btn_sel_rib = ctk.CTkButton(rib_frame, text="Nouveau RIB",
                                         command=lambda: self._sel_new_pj("rib"), state="disabled")
        self.btn_sel_rib.grid(row=0, column=0, padx=(0, 5))
        ctk.CTkButton(rib_frame, text="Coller",
                      command=lambda: self._coller_pj("rib"), state="disabled").grid(row=0, column=1, padx=(0, 10))
        self.lbl_rib_sel = ctk.CTkLabel(rib_frame, textvariable=self.chemin_rib_var, text_color="gray",
                                        anchor="w", wraplength=300)
        self.lbl_rib_sel.grid(row=0, column=2, sticky="ew")

        drop_zone_rib = DragDropFrame(form_frame,
                                      drop_callback=lambda p: self._sel_new_pj("rib", file_path=p),
                                      text="Déposez le nouveau RIB ici")
        drop_zone_rib.pack(fill="x", pady=5, padx=10)

        self.cb_keep_rib = ctk.CTkCheckBox(form_frame, variable=self.keep_rib_var, command=self._toggle_rib_ui)
        if demande.chemins_rib_stockes:
            self.cb_keep_rib.configure(
                text=f"Conserver RIB: {os.path.basename(demande.chemins_rib_stockes[-1])}")
        else:
            self.cb_keep_rib.configure(text="Pas de RIB précédent", state="disabled");
            self.keep_rib_var.set(False);
            self._toggle_rib_ui()
        self.cb_keep_rib.pack(anchor="w", padx=20, pady=(5, 10))

        ctk.CTkLabel(form_frame, text="Commentaire de correction (Obligatoire):").pack(pady=(15, 0), padx=10)
        self.commentaire_box = ctk.CTkTextbox(form_frame)
        self.commentaire_box.pack(pady=5, padx=10, fill="both", expand=True)
        self.commentaire_box.focus()

        self.progress_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", expand=False, padx=10, pady=5)
        self.facture_progress_label = ctk.CTkLabel(self.progress_frame, text="")
        self.facture_progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.rib_progress_label = ctk.CTkLabel(self.progress_frame, text="")
        self.rib_progress_bar = ctk.CTkProgressBar(self.progress_frame)

        self._build_preview_panel()

        self.btn_submit = ctk.CTkButton(self, text="Resoumettre la Demande", command=self._submit_correction)
        self.btn_submit.grid(row=1, column=0, columnspan=2, pady=(0, 20))

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
                                                text="Cochez une case 'Conserver...'\npour désactiver la sélection\nou choisissez un nouveau fichier.",
                                                text_color="gray60", wraplength=250)
        self.preview_image_label.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        self.preview_info_label = ctk.CTkLabel(self.preview_area_frame, text="", font=ctk.CTkFont(size=11),
                                               text_color="gray60")
        self.preview_info_label.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 10))

    def _clear_preview(self):
        self._update_preview_buttons(None)
        self.preview_title_label.configure(text="")
        self.preview_image_label.configure(image=None,
                                           text="Cochez une case 'Conserver...'\npour désactiver la sélection\nou choisissez un nouveau fichier.")
        self.preview_info_label.configure(text="")
        self.preview_image_label.image = None

    def _update_preview_buttons(self, new_preview: str | None):
        self.currently_previewing = new_preview
        default_color = ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        selected_color = "green"

        facture_color = default_color if self.currently_previewing != "facture" else selected_color
        rib_color = default_color if self.currently_previewing != "rib" else selected_color

        self.show_facture_button.configure(fg_color=facture_color)
        self.show_rib_button.configure(fg_color=rib_color)

    def _toggle_facture_ui(self):
        is_kept = self.keep_facture_var.get()
        self.btn_sel_facture.configure(state="disabled" if is_kept else "normal")
        self.show_facture_button.configure(state="disabled")
        self.facture_local_path = None
        if self.chemin_facture_reseau: self.remboursement_controller.supprimer_piece_jointe_reseau(
            self.chemin_facture_reseau); self.chemin_facture_reseau = None
        self.chemin_facture_var.set("Ancienne facture conservée" if is_kept else "Aucun fichier sélectionné")
        if is_kept or self.currently_previewing == "facture": self._clear_preview()

    def _toggle_rib_ui(self):
        is_kept = self.keep_rib_var.get()
        self.btn_sel_rib.configure(state="disabled" if is_kept else "normal")
        self.show_rib_button.configure(state="disabled")
        self.rib_local_path = None
        if self.chemin_rib_reseau: self.remboursement_controller.supprimer_piece_jointe_reseau(
            self.chemin_rib_reseau); self.chemin_rib_reseau = None
        self.chemin_rib_var.set("Ancien RIB conservé" if is_kept else "Aucun fichier sélectionné")
        if is_kept or self.currently_previewing == "rib": self._clear_preview()

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
            self.preview_info_label.configure(
                text=f"{os.path.basename(file_path)}\n({image.width}x{image.height})")

        self.run_task(task, on_complete, show_overlay=False)

    def _coller_pj(self, type_pj: str):
        try:
            image = ImageGrab.grabclipboard()
            if not isinstance(image, Image.Image):
                self.app_controller.show_toast("Aucune image valide dans le presse-papiers.", "info")
                return

            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix="pasted_")
            image.save(temp_file, "PNG")
            temp_file.close()

            self._sel_new_pj(type_pj, temp_file.name)

        except Exception as e:
            self.app_controller.show_toast(f"Erreur lors du collage : {e}", "error")

    def _sel_new_pj(self, type_pj: str, file_path: str = None):
        if file_path:
            chemin_local = file_path
        else:
            chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image(
                f"Nouvelle {type_pj.title()}")
        if not chemin_local: return

        if type_pj == "facture":
            self.keep_facture_var.set(False);
            self._toggle_facture_ui();
            self.facture_local_path = chemin_local;
            self.show_facture_button.configure(state="normal")
        elif type_pj == "rib":
            self.keep_rib_var.set(False);
            self._toggle_rib_ui();
            self.rib_local_path = chemin_local;
            self.show_rib_button.configure(state="normal")

        self._show_preview(chemin_local, type_pj)
        self.copy_operations_in_progress += 1
        self.btn_submit.configure(state="disabled", text="Copie en cours...")

        progress_bar = self.facture_progress_bar if type_pj == "facture" else self.rib_progress_bar
        progress_label = self.facture_progress_label if type_pj == "facture" else self.rib_progress_label
        progress_bar.pack(fill="x");
        progress_label.pack(fill="x")
        progress_bar.set(0)

        filename = os.path.basename(chemin_local)
        progress_label.configure(text=f"Copie de {filename}...")

        label_var = self.chemin_facture_var if type_pj == "facture" else self.chemin_rib_var
        chemin_reseau_attr = "chemin_facture_reseau" if type_pj == "facture" else "chemin_rib_reseau"
        if getattr(self, chemin_reseau_attr):
            self.run_task(
                lambda p=getattr(self, chemin_reseau_attr): self.remboursement_controller.supprimer_piece_jointe_reseau(
                    p),
                None, show_overlay=False)
        setattr(self, chemin_reseau_attr, None);
        label_var.set(filename)

        def copy_task():
            try:
                callback = lambda p: self.copy_progress_queue.put(("progress", type_pj, p))
                new_path = self.remboursement_controller.ajouter_pj_a_demande_existante(
                    self.id_demande, chemin_local, type_pj, callback)
                self.copy_progress_queue.put(("done", type_pj, new_path))
            except Exception as e:
                self.copy_progress_queue.put(("error", type_pj, str(e)))
            finally:
                if "pasted_" in chemin_local:
                    try:
                        os.unlink(chemin_local)
                    except OSError:
                        pass

        threading.Thread(target=copy_task, daemon=True).start()

    def _check_copy_progress(self):
        try:
            while not self.copy_progress_queue.empty():
                message = self.copy_progress_queue.get(block=False)
                if not isinstance(message, tuple) or len(message) != 3: continue

                msg_type, pj_type, value = message
                progress_bar = self.facture_progress_bar if pj_type == "facture" else self.rib_progress_bar
                progress_label = self.facture_progress_label if pj_type == "facture" else self.rib_progress_label

                if msg_type == "done":
                    if pj_type == "facture":
                        self.chemin_facture_reseau = value
                    else:
                        self.chemin_rib_reseau = value
                    self.copy_operations_in_progress -= 1
                    progress_bar.pack_forget();
                    progress_label.pack_forget()
                elif msg_type == "error":
                    self.app_controller.show_toast(f"Erreur de copie ({pj_type}): {value}", "error")
                    self.copy_operations_in_progress -= 1
                    progress_bar.pack_forget();
                    progress_label.pack_forget()
                elif msg_type == "progress" and isinstance(value, float):
                    progress_bar.set(value)

                if self.copy_operations_in_progress == 0:
                    self.btn_submit.configure(state="normal", text="Resoumettre la Demande")
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._check_copy_progress)

    def _submit_correction(self):
        if self.copy_operations_in_progress > 0:
            self.app_controller.show_toast("Veuillez attendre la fin de la copie des fichiers.", "warning")
            return

        self.btn_submit.configure(state="disabled")
        commentaire = self.commentaire_box.get("1.0", "end-1c").strip()
        if not self.keep_rib_var.get() and not self.chemin_rib_reseau:
            self.app_controller.show_toast("Un nouveau RIB est obligatoire si vous ne conservez pas l'ancien.",
                                           "error");
            self.btn_submit.configure(state="normal");
            return
        if not commentaire:
            self.app_controller.show_toast("Un commentaire expliquant la correction est obligatoire.", "error");
            self.btn_submit.configure(state="normal");
            return

        def task():
            facture_path = self.chemin_facture_reseau
            rib_path = self.chemin_rib_reseau
            self.chemin_facture_reseau, self.chemin_rib_reseau = None, None
            return self.remboursement_controller.pneri_resoumettre_demande_corrigee(self.id_demande, commentaire,
                                                                                    None if self.keep_facture_var.get() else facture_path,
                                                                                    None if self.keep_rib_var.get() else rib_path)

        def on_complete(result, error):
            if error: self.app_controller.show_toast(f"Erreur : {error}", 'error'); self.btn_submit.configure(
                state="normal"); return
            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success');
                self.submitted = True;
                self.close_animated()
            else:
                self.app_controller.show_toast(message, 'error');
                self.btn_submit.configure(state="normal")

        self.run_task(task, on_complete, "Resoumission de la demande...")