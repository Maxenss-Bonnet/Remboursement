import os
import customtkinter as ctk
import threading
from views.mixins.task_runner_mixin import TaskRunnerMixin


class AcceptationConstatDialog(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, remboursement_controller, id_demande, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.id_demande = id_demande
        self.app_controller = app_controller
        self.chemin_pj_reseau = None
        self.submitted = False

        self.title(f"Accepter Constat TP - Demande {id_demande[:8]}")
        self.geometry("500x450")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.chemin_pj_var = ctk.StringVar(value="Aucune PJ sélectionnée (Obligatoire)")

        ctk.CTkLabel(self, text="Preuve de Trop-Perçu (Image/PDF/Doc...):", font=ctk.CTkFont(weight="bold")).pack(
            pady=(15, 2))
        ctk.CTkButton(self, text="Choisir Fichier...", command=self._select_pj).pack(pady=(0, 5))
        self.label_pj = ctk.CTkLabel(self, textvariable=self.chemin_pj_var)
        self.label_pj.pack()

        ctk.CTkLabel(self, text="Commentaire (Optionnel):", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 2))
        self.commentaire_box = ctk.CTkTextbox(self, height=100, width=450)
        self.commentaire_box.pack(pady=5, padx=10, fill="x", expand=True)
        self.commentaire_box.focus()

        self.btn_submit = ctk.CTkButton(self, text="Valider et Soumettre à J. Durousset", command=self._submit,
                                        height=35)
        self.btn_submit.pack(pady=20)

    def _select_pj(self):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image(
            "Sélectionner Preuve Trop-Perçu")
        if not chemin_local: return

        if self.chemin_pj_reseau:
            self.run_task(
                lambda p=self.chemin_pj_reseau: self.remboursement_controller.supprimer_piece_jointe_reseau(p), None,
                show_overlay=False)
        self.chemin_pj_reseau = None

        original_text_color = self.label_pj.cget("text_color")
        self.chemin_pj_var.set(f"Copie en cours: {os.path.basename(chemin_local)}...")
        self.label_pj.configure(text_color="orange")

        def task():
            return self.remboursement_controller.ajouter_pj_a_demande_existante(self.id_demande, chemin_local,
                                                                                "trop_percu")

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur de copie: {error}", "error")
                self.chemin_pj_var.set("Échec de la copie !")
                self.label_pj.configure(text_color="red")
            else:
                self.chemin_pj_reseau = result
                self.chemin_pj_var.set(os.path.basename(chemin_local))
                self.label_pj.configure(text_color=original_text_color)

        self.run_task(task, on_complete, "Copie du fichier...", show_overlay=False)

    def _submit(self):
        self.btn_submit.configure(state="disabled")
        commentaire = self.commentaire_box.get("1.0", "end-1c").strip()
        if not commentaire: commentaire = "Constat de trop-perçu accepté."
        if not self.chemin_pj_reseau:
            self.app_controller.show_toast("La pièce jointe de preuve est obligatoire.", "error")
            self.btn_submit.configure(state="normal")
            return

        def task():
            path_to_submit = self.chemin_pj_reseau
            self.chemin_pj_reseau = None
            return self.remboursement_controller.mlupo_accepter_constat(self.id_demande, commentaire, path_to_submit)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur : {error}", 'error')
                self.btn_submit.configure(state="normal")
                return

            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success')
                self.submitted = True
                self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')
                self.btn_submit.configure(state="normal")

        self.run_task(task, on_complete, "Acceptation du constat...")

    def _on_close(self):
        if self.chemin_pj_reseau:
            threading.Thread(target=self.remboursement_controller.supprimer_piece_jointe_reseau,
                             args=(self.chemin_pj_reseau,), daemon=True).start()
        self.destroy()