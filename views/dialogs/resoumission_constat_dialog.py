import os
import customtkinter as ctk
import threading
from .comment_dialog import CommentDialog
from views.mixins.task_runner_mixin import TaskRunnerMixin


class ResoumissionConstatDialog(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, remboursement_controller, id_demande, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.id_demande = id_demande
        self.app_controller = app_controller
        self.submitted = False

        self.title(f"Corriger Constat TP {id_demande[:8]}")
        self.geometry("550x450")
        self.transient(master)
        self.grab_set()
        self.minsize(500, 400)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.chemin_pj_reseau_temp = None
        self.keep_pj_var = ctk.BooleanVar(value=True)
        self.chemin_pj_var = ctk.StringVar(value="Ancienne preuve conservée")

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self._load_data_and_build_ui()

    def _load_data_and_build_ui(self):
        def task():
            return self.remboursement_controller.get_demande(self.id_demande)

        def on_complete(demande, error):
            if error or not demande:
                self.app_controller.show_toast("Impossible de charger les données de la demande.", "error")
                self.destroy()
                return
            self._build_ui(demande)

        self.run_task(task, on_complete, "Chargement de la demande...")

    def _build_ui(self, demande):
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(side="bottom", pady=(10, 0), fill="x")
        center_buttons_frame = ctk.CTkFrame(button_frame, fg_color="transparent")
        center_buttons_frame.pack()
        ctk.CTkButton(center_buttons_frame, text="Resoumettre le Constat",
                      command=self._submit_correction_constat).pack(side="left", padx=10)
        ctk.CTkButton(center_buttons_frame, text="Renvoyer au Demandeur", command=self._reject_and_return_to_demandeur,
                      fg_color="#D35400", hover_color="#A84300").pack(side="left", padx=10)

        ctk.CTkLabel(self.main_frame, text="Veuillez fournir une nouvelle preuve et un commentaire.").pack(pady=(0, 15),
                                                                                                           side="top",
                                                                                                           padx=10)
        pj_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        pj_frame.pack(fill="x", padx=10, pady=(5, 0))
        pj_frame.columnconfigure(1, weight=1)
        self.btn_sel_pj = ctk.CTkButton(pj_frame, text="Choisir Nouvelle Preuve TP", command=self._sel_new_pj_tp,
                                        state="disabled")
        self.btn_sel_pj.grid(row=0, column=0, padx=(0, 10))
        self.lbl_pj_sel = ctk.CTkLabel(pj_frame, textvariable=self.chemin_pj_var, text_color="gray", anchor="w")
        self.lbl_pj_sel.grid(row=0, column=1, sticky="ew")
        pjs_existantes = demande.chemins_trop_percu_stockees
        self.cb_keep_pj = ctk.CTkCheckBox(self.main_frame, variable=self.keep_pj_var, command=self._toggle_pj_ui)
        if pjs_existantes:
            self.cb_keep_pj.configure(text=f"Conserver la preuve : {os.path.basename(pjs_existantes[-1])}")
        else:
            self.cb_keep_pj.configure(text="Pas de preuve précédente", state="disabled")
            self.keep_pj_var.set(False)
            self._toggle_pj_ui()
        self.cb_keep_pj.pack(anchor="w", padx=20, pady=(5, 15))
        ctk.CTkLabel(self.main_frame, text="Commentaire de correction (Obligatoire):").pack(pady=(15, 0), side="top",
                                                                                            padx=10)
        self.commentaire_box = ctk.CTkTextbox(self.main_frame)
        self.commentaire_box.pack(pady=(5, 10), padx=10, fill="both", expand=True, side="top")
        self.commentaire_box.focus()

    def _toggle_pj_ui(self):
        is_kept = self.keep_pj_var.get()
        self.btn_sel_pj.configure(state="disabled" if is_kept else "normal")
        self.lbl_pj_sel.configure(text_color="gray" if is_kept else ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        if self.chemin_pj_reseau_temp:
            self.remboursement_controller.supprimer_fichier_temporaire_reseau(self.chemin_pj_reseau_temp)
            self.chemin_pj_reseau_temp = None
        if is_kept:
            self.chemin_pj_var.set("Ancienne preuve conservée")
        else:
            self.chemin_pj_var.set("Aucun fichier sélectionné")

    def _sel_new_pj_tp(self):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image("Nouvelle Preuve Trop-Perçu")
        if not chemin_local: return

        if self.chemin_pj_reseau_temp:
            self.run_task(lambda p=self.chemin_pj_reseau_temp: self.remboursement_controller.supprimer_fichier_temporaire_reseau(p), None, show_overlay=False)
        self.chemin_pj_reseau_temp = None

        self.chemin_pj_var.set("Copie en cours...")
        def task(): return self.remboursement_controller.preparer_piece_jointe_reseau(chemin_local)
        def on_complete(result, error):
            if error:
                self.chemin_pj_var.set("Échec copie!")
            else:
                self.chemin_pj_reseau_temp = result
                self.chemin_pj_var.set(os.path.basename(result))
        self.run_task(task, on_complete, show_overlay=False)

    def _submit_correction_constat(self):
        commentaire = self.commentaire_box.get("1.0", "end-1c").strip()
        if not self.keep_pj_var.get() and not self.chemin_pj_reseau_temp:
            self.app_controller.show_toast("Une nouvelle preuve est obligatoire si vous ne conservez pas l'ancienne.", "error")
            return
        if not commentaire:
            self.app_controller.show_toast("Un commentaire expliquant la correction est obligatoire.", "error")
            return

        def task():
            path_to_submit = self.chemin_pj_reseau_temp
            self.chemin_pj_reseau_temp = None
            return self.remboursement_controller.mlupo_resoumettre_constat_corrige(
                self.id_demande, commentaire,
                None if self.keep_pj_var.get() else path_to_submit
            )

        def on_complete(result, error):
            if error: self.app_controller.show_toast(f"Erreur : {error}", 'error'); return
            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success')
                self.submitted = True
                self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')
        self.run_task(task, on_complete, "Resoumission du constat...")

    def _reject_and_return_to_demandeur(self):
        dialog = CommentDialog(self, title="Renvoyer au Demandeur", prompt="Motif du renvoi à p.neri (obligatoire) :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is None: return

        self._on_close() # Nettoie les fichiers temporaires avant de potentiellement détruire la fenêtre
        def task(): return self.remboursement_controller.mlupo_refuser_correction(self.id_demande, commentaire)
        def on_complete(result, error):
            if error: self.app_controller.show_toast(f"Erreur : {error}", 'error'); return
            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success')
                self.submitted = True
                # La fenêtre est déjà fermée par _on_close() qui appelle self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')
        self.run_task(task, on_complete, "Renvoi au demandeur...")

    def _on_close(self):
        if self.chemin_pj_reseau_temp:
            threading.Thread(target=self.remboursement_controller.supprimer_fichier_temporaire_reseau, args=(self.chemin_pj_reseau_temp,), daemon=True).start()
        self.destroy()