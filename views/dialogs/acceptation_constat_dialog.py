import os
import customtkinter as ctk
import threading
import queue
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.animation_mixin import AnimationMixin


class AcceptationConstatDialog(ctk.CTkToplevel, TaskRunnerMixin, AnimationMixin):
    def __init__(self, master, remboursement_controller, id_demande, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        AnimationMixin.__init__(self, master)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.id_demande = id_demande
        self.app_controller = app_controller
        self.chemin_pj_reseau = None
        self.submitted = False
        self.copy_progress_queue = queue.Queue()

        self.title(f"Accepter Constat TP - Demande {id_demande[:8]}")
        self.geometry("500x500")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self.chemin_pj_var = ctk.StringVar(value="Aucune PJ sélectionnée (Obligatoire)")

        ctk.CTkLabel(self, text="Preuve de Trop-Perçu (Image/PDF/Doc...):", font=ctk.CTkFont(weight="bold")).pack(
            pady=(15, 2))
        ctk.CTkButton(self, text="Choisir Fichier...", command=self._select_pj).pack(pady=(0, 5))
        self.label_pj = ctk.CTkLabel(self, textvariable=self.chemin_pj_var)
        self.label_pj.pack()

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.pack(pady=(5, 10), padx=20, fill="x")
        self.progress_bar.set(0)
        self.progress_bar.pack_forget()

        ctk.CTkLabel(self, text="Commentaire (Optionnel):", font=ctk.CTkFont(weight="bold")).pack(pady=(10, 2))
        self.commentaire_box = ctk.CTkTextbox(self, height=100, width=450)
        self.commentaire_box.pack(pady=5, padx=10, fill="x", expand=True)
        self.commentaire_box.focus()

        self.btn_submit = ctk.CTkButton(self, text="Valider et Soumettre à J. Durousset", command=self._submit,
                                        height=35)
        self.btn_submit.pack(pady=20)

        self.fade_in()
        self._check_copy_progress()

    def destroy(self):
        if self.chemin_pj_reseau:
            threading.Thread(target=self.remboursement_controller.supprimer_piece_jointe_reseau,
                             args=(self.chemin_pj_reseau,), daemon=True).start()
        super().destroy()

    def _select_pj(self):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image(
            "Sélectionner Preuve Trop-Perçu")
        if not chemin_local: return

        self.btn_submit.configure(state="disabled", text="Copie en cours...")
        self.progress_bar.pack()
        self.progress_bar.set(0)

        if self.chemin_pj_reseau:
            self.run_task(
                lambda p=self.chemin_pj_reseau: self.remboursement_controller.supprimer_piece_jointe_reseau(p), None,
                show_overlay=False)
        self.chemin_pj_reseau = None

        self.chemin_pj_var.set(os.path.basename(chemin_local))

        def copy_task():
            try:
                callback = lambda p: self.copy_progress_queue.put(p)
                new_path = self.remboursement_controller.ajouter_pj_a_demande_existante(
                    self.id_demande, chemin_local, "trop_percu", callback
                )
                self.copy_progress_queue.put(("done", new_path))
            except Exception as e:
                self.copy_progress_queue.put(f"error: {e}")

        threading.Thread(target=copy_task, daemon=True).start()

    def _check_copy_progress(self):
        try:
            while not self.copy_progress_queue.empty():
                message = self.copy_progress_queue.get_nowait()
                if isinstance(message, float):
                    self.progress_bar.set(message)
                elif isinstance(message, tuple) and message[0] == "done":
                    self.chemin_pj_reseau = message[1]
                    self.btn_submit.configure(state="normal", text="Valider et Soumettre à J. Durousset")
                    self.progress_bar.pack_forget()
                elif isinstance(message, str) and message.startswith("error:"):
                    self.app_controller.show_toast(f"Erreur de copie: {message.split(': ', 1)[1]}", "error")
                    self.btn_submit.configure(state="normal", text="Valider et Soumettre à J. Durousset")
                    self.progress_bar.pack_forget()
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._check_copy_progress)

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
                self.close_animated()
            else:
                self.app_controller.show_toast(message, 'error')
                self.btn_submit.configure(state="normal")

        self.run_task(task, on_complete, "Acceptation du constat...")