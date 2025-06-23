import os
import customtkinter as ctk
import threading
import queue
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.animation_mixin import AnimationMixin


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
        self.geometry("600x650")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self.chemin_facture_reseau = None
        self.chemin_rib_reseau = None
        self.keep_facture_var = ctk.BooleanVar(value=True)
        self.keep_rib_var = ctk.BooleanVar(value=True)

        self.chemin_facture_var = ctk.StringVar(value="Ancienne facture conservée")
        self.chemin_rib_var = ctk.StringVar(value="Ancien RIB conservé")

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(expand=True, fill="both", padx=20, pady=10)

        self._load_data_and_build_ui()
        self.fade_in()
        self._check_copy_progress()

    def destroy(self):
        paths_to_delete = [self.chemin_facture_reseau, self.chemin_rib_reseau]
        for path in paths_to_delete:
            if path: threading.Thread(target=self.remboursement_controller.supprimer_piece_jointe_reseau, args=(path,),
                                      daemon=True).start()
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
        ctk.CTkLabel(self.main_frame, text="Veuillez fournir les documents mis à jour et un commentaire.").pack(
            pady=(0, 15))

        # --- Section Facture ---
        facture_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        facture_frame.pack(fill="x", pady=(5, 0))
        facture_frame.columnconfigure(1, weight=1)
        self.btn_sel_facture = ctk.CTkButton(facture_frame, text="Choisir Nouvelle Facture (Optionnel)",
                                             command=lambda: self._sel_new_pj("facture"), state="disabled")
        self.btn_sel_facture.grid(row=0, column=0, padx=(0, 10))
        self.lbl_facture_sel = ctk.CTkLabel(facture_frame, textvariable=self.chemin_facture_var, text_color="gray",
                                            anchor="w")
        self.lbl_facture_sel.grid(row=0, column=1, sticky="ew")
        self.cb_keep_facture = ctk.CTkCheckBox(self.main_frame, variable=self.keep_facture_var,
                                               command=self._toggle_facture_ui)
        if demande.chemins_factures_stockees:
            self.cb_keep_facture.configure(
                text=f"Conserver la facture : {os.path.basename(demande.chemins_factures_stockees[-1])}")
        else:
            self.cb_keep_facture.configure(text="Pas de facture précédente à conserver", state="disabled");
            self.keep_facture_var.set(False);
            self._toggle_facture_ui()
        self.cb_keep_facture.pack(anchor="w", padx=20, pady=(5, 10))

        # --- Section RIB ---
        rib_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        rib_frame.pack(fill="x", pady=(5, 0))
        rib_frame.columnconfigure(1, weight=1)
        self.btn_sel_rib = ctk.CTkButton(rib_frame, text="Choisir Nouveau RIB", command=lambda: self._sel_new_pj("rib"),
                                         state="disabled")
        self.btn_sel_rib.grid(row=0, column=0, padx=(0, 10))
        self.lbl_rib_sel = ctk.CTkLabel(rib_frame, textvariable=self.chemin_rib_var, text_color="gray", anchor="w")
        self.lbl_rib_sel.grid(row=0, column=1, sticky="ew")
        self.cb_keep_rib = ctk.CTkCheckBox(self.main_frame, variable=self.keep_rib_var, command=self._toggle_rib_ui)
        if demande.chemins_rib_stockes:
            self.cb_keep_rib.configure(text=f"Conserver le RIB : {os.path.basename(demande.chemins_rib_stockes[-1])}")
        else:
            self.cb_keep_rib.configure(text="Pas de RIB précédent à conserver", state="disabled");
            self.keep_rib_var.set(False);
            self._toggle_rib_ui()
        self.cb_keep_rib.pack(anchor="w", padx=20, pady=(5, 10))

        # --- Barres de progression ---
        self.facture_progress_label = ctk.CTkLabel(self.main_frame, text="")
        self.facture_progress_label.pack(fill='x', padx=20, pady=(10, 0))
        self.facture_progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.facture_progress_bar.pack(fill='x', padx=20)
        self.facture_progress_label.pack_forget()
        self.facture_progress_bar.pack_forget()

        self.rib_progress_label = ctk.CTkLabel(self.main_frame, text="")
        self.rib_progress_label.pack(fill='x', padx=20, pady=(5, 0))
        self.rib_progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.rib_progress_bar.pack(fill='x', padx=20)
        self.rib_progress_label.pack_forget()
        self.rib_progress_bar.pack_forget()

        ctk.CTkLabel(self.main_frame, text="Commentaire de correction (Obligatoire):").pack(pady=(15, 0))
        self.commentaire_box = ctk.CTkTextbox(self.main_frame, height=80)
        self.commentaire_box.pack(pady=5, padx=20, fill="x", expand=True)
        self.commentaire_box.focus()

        self.btn_submit = ctk.CTkButton(self, text="Resoumettre la Demande", command=self._submit_correction)
        self.btn_submit.pack(pady=20)

    def _toggle_facture_ui(self):
        is_kept = self.keep_facture_var.get()
        self.btn_sel_facture.configure(state="disabled" if is_kept else "normal")
        if self.chemin_facture_reseau: self.remboursement_controller.supprimer_piece_jointe_reseau(
            self.chemin_facture_reseau); self.chemin_facture_reseau = None
        self.chemin_facture_var.set("Ancienne facture conservée" if is_kept else "Aucun fichier sélectionné")

    def _toggle_rib_ui(self):
        is_kept = self.keep_rib_var.get()
        self.btn_sel_rib.configure(state="disabled" if is_kept else "normal")
        if self.chemin_rib_reseau: self.remboursement_controller.supprimer_piece_jointe_reseau(
            self.chemin_rib_reseau); self.chemin_rib_reseau = None
        self.chemin_rib_var.set("Ancien RIB conservé" if is_kept else "Aucun fichier sélectionné")

    def _sel_new_pj(self, type_pj: str):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image(
            f"Nouvelle {type_pj.title()}")
        if not chemin_local: return

        self.copy_operations_in_progress += 1
        self.btn_submit.configure(state="disabled", text="Copie en cours...")

        progress_bar = self.facture_progress_bar if type_pj == "facture" else self.rib_progress_bar
        progress_label = self.facture_progress_label if type_pj == "facture" else self.rib_progress_label
        progress_bar.pack()
        progress_label.pack()
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
        setattr(self, chemin_reseau_attr, None)
        label_var.set(filename)

        def copy_task():
            try:
                # CORRECTION : Ajout du type de message "progress"
                callback = lambda p: self.copy_progress_queue.put(("progress", type_pj, p))
                new_path = self.remboursement_controller.ajouter_pj_a_demande_existante(
                    self.id_demande, chemin_local, type_pj, callback
                )
                self.copy_progress_queue.put(("done", type_pj, new_path))
            except Exception as e:
                self.copy_progress_queue.put(("error", type_pj, str(e)))

        threading.Thread(target=copy_task, daemon=True).start()

    def _check_copy_progress(self):
        try:
            while not self.copy_progress_queue.empty():
                message = self.copy_progress_queue.get(block=False)

                # Vérification de sécurité pour le dépaquetage
                if not isinstance(message, tuple) or len(message) != 3:
                    continue

                msg_type, pj_type, value = message

                progress_bar = self.facture_progress_bar if pj_type == "facture" else self.rib_progress_bar
                progress_label = self.facture_progress_label if pj_type == "facture" else self.rib_progress_label

                if msg_type == "done":
                    if pj_type == "facture":
                        self.chemin_facture_reseau = value
                    else:
                        self.chemin_rib_reseau = value
                    self.copy_operations_in_progress -= 1
                    progress_bar.pack_forget()
                    progress_label.pack_forget()
                elif msg_type == "error":
                    self.app_controller.show_toast(f"Erreur de copie ({pj_type}): {value}", "error")
                    self.copy_operations_in_progress -= 1
                    progress_bar.pack_forget()
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