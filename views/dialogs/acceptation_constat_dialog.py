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
        self.chemin_pj_reseau_temp = None
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

        ctk.CTkButton(self, text="Valider et Soumettre à J. Durousset", command=self._submit, height=35).pack(pady=20)

    def _select_pj(self):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image("Sélectionner Preuve Trop-Perçu")
        if not chemin_local:
            return

        if self.chemin_pj_reseau_temp:
            self.run_task(
                lambda path=self.chemin_pj_reseau_temp: self.remboursement_controller.supprimer_fichier_temporaire_reseau(path),
                on_complete=None, show_overlay=False
            )
        self.chemin_pj_reseau_temp = None

        original_text_color = self.label_pj.cget("text_color")
        self.chemin_pj_var.set(f"Copie en cours: {os.path.basename(chemin_local)}...")
        self.label_pj.configure(text_color="orange")

        def task():
            return self.remboursement_controller.preparer_piece_jointe_reseau(chemin_local)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur de copie: {error}", "error")
                self.chemin_pj_var.set("Échec de la copie !")
                self.label_pj.configure(text_color="red")
                self.chemin_pj_reseau_temp = None
                return

            self.chemin_pj_reseau_temp = result
            self.chemin_pj_var.set(os.path.basename(result))
            self.label_pj.configure(text_color=original_text_color)

        self.run_task(task, on_complete, show_overlay=False)

    def _submit(self):
        commentaire = self.commentaire_box.get("1.0", "end-1c").strip()
        if not commentaire:
            commentaire = "Constat de trop-perçu accepté."

        if not self.chemin_pj_reseau_temp:
            self.app_controller.show_toast("La pièce jointe de preuve est obligatoire.", "error")
            return

        def task():
            path_to_submit = self.chemin_pj_reseau_temp
            self.chemin_pj_reseau_temp = None

            return self.remboursement_controller.mlupo_accepter_constat(
                id_demande=self.id_demande,
                chemin_pj_trop_percu=path_to_submit,
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

    def _on_close(self):
        if self.chemin_pj_reseau_temp:
            # Utilise un thread simple pour ne pas bloquer la fermeture
            threading.Thread(
                target=self.remboursement_controller.supprimer_fichier_temporaire_reseau,
                args=(self.chemin_pj_reseau_temp,),
                daemon=True
            ).start()
        self.destroy()