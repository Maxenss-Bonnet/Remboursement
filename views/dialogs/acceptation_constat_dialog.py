import os
import customtkinter as ctk
from views.mixins.task_runner_mixin import TaskRunnerMixin


class AcceptationConstatDialog(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, remboursement_controller, id_demande, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.id_demande = id_demande
        self.app_controller = app_controller
        self.current_pj_path = None
        self.submitted = False

        self.title(f"Accepter Constat TP - Demande {id_demande[:8]}")
        self.geometry("500x450")
        self.transient(master)
        self.grab_set()

        self.chemin_pj_var = ctk.StringVar(value="Aucune PJ sélectionnée (Obligatoire)")

        ctk.CTkLabel(self, text="Preuve de Trop-Perçu (Image/PDF/Doc...):", font=ctk.CTkFont(weight="bold")).pack(
            pady=(15, 2))
        ctk.CTkButton(self, text="Choisir Fichier...", command=self._select_pj).pack(pady=(0, 5))
        ctk.CTkLabel(self, textvariable=self.chemin_pj_var).pack()

        ctk.CTkLabel(self, text="Commentaire (Optionnel):", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 2))
        self.commentaire_box = ctk.CTkTextbox(self, height=100, width=450)
        self.commentaire_box.pack(pady=5, padx=10, fill="x", expand=True)
        self.commentaire_box.focus()

        ctk.CTkButton(self, text="Valider et Soumettre à J. Durousset", command=self._submit, height=35).pack(pady=20)

    def _select_pj(self):
        path = self.remboursement_controller.selectionner_fichier_document_ou_image("Sélectionner Preuve Trop-Perçu")
        if path:
            self.chemin_pj_var.set(os.path.basename(path))
            self.current_pj_path = path

    def _submit(self):
        commentaire = self.commentaire_box.get("1.0", "end-1c").strip()
        if not commentaire:
            commentaire = "Constat de trop-perçu accepté."

        if not self.current_pj_path:
            self.app_controller.show_toast("La pièce jointe de preuve est obligatoire.", "error")
            return

        def task():
            return self.remboursement_controller.mlupo_accepter_constat(
                id_demande=self.id_demande,
                chemin_pj_trop_percu=self.current_pj_path,
                commentaire=commentaire
            )

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur : {error}", 'error')
                return

            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success')
                self.submitted = True
                self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')

        self.run_task(task, on_complete, "Acceptation du constat...")