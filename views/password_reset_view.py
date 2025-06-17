import customtkinter as ctk
from views.mixins.task_runner_mixin import TaskRunnerMixin


class PasswordResetView(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, controller, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.controller = controller
        self.app_controller = app_controller
        self.master = master

        self.title("Réinitialisation du mot de passe")
        self.geometry("450x550")
        self.transient(master)
        self.grab_set()

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        self.current_step = 1
        self.username_to_reset = ""
        self._setup_step1()

    def _clear_frame(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def _setup_step1(self):
        self._clear_frame()
        self.current_step = 1
        self.geometry("450x250")

        ctk.CTkLabel(self.main_frame, text="Étape 1: Demander un code",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 15))
        ctk.CTkLabel(self.main_frame,
                     text="Veuillez entrer votre nom d'utilisateur pour recevoir un code de réinitialisation par e-mail.").pack(
            pady=5, padx=10)

        ctk.CTkLabel(self.main_frame, text="Nom d'utilisateur:").pack(pady=(10, 2))
        self.username_entry = ctk.CTkEntry(self.main_frame, width=250)
        self.username_entry.pack(pady=(0, 20))
        self.username_entry.focus()
        self.username_entry.bind("<Return>", lambda e: self._handle_step1())

        ctk.CTkButton(self.main_frame, text="Envoyer le code", command=self._handle_step1).pack(pady=10)

    def _handle_step1(self):
        username = self.username_entry.get()
        if not username:
            self.app_controller.show_toast("Veuillez saisir votre nom d'utilisateur.", "warning")
            return

        def task():
            return self.controller.request_password_reset(username)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur : {error}", "error")
                return

            success, message = result
            if success:
                self.username_to_reset = username
                self.app_controller.show_toast(message, 'success')
                self._setup_step2()
            else:
                self.app_controller.show_toast(message, 'error')

        self.run_task(task, on_complete, "Envoi du code...")

    def _setup_step2(self):
        self._clear_frame()
        self.current_step = 2
        self.geometry("450x400")

        ctk.CTkLabel(self.main_frame, text="Étape 2: Changer le mot de passe",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 15))
        ctk.CTkLabel(self.main_frame,
                     text="Veuillez entrer le code reçu par e-mail et votre nouveau mot de passe.").pack(pady=5,
                                                                                                         padx=10)

        ctk.CTkLabel(self.main_frame, text="Code de réinitialisation:").pack(pady=(10, 2))
        self.code_entry = ctk.CTkEntry(self.main_frame, width=250)
        self.code_entry.pack()
        self.code_entry.focus()

        ctk.CTkLabel(self.main_frame, text="Nouveau mot de passe:").pack(pady=(10, 2))
        self.new_password_entry = ctk.CTkEntry(self.main_frame, width=250, show="*")
        self.new_password_entry.pack()

        ctk.CTkLabel(self.main_frame, text="Confirmer le nouveau mot de passe:").pack(pady=(10, 2))
        self.confirm_password_entry = ctk.CTkEntry(self.main_frame, width=250, show="*")
        self.confirm_password_entry.pack()
        self.confirm_password_entry.bind("<Return>", lambda e: self._handle_step2())

        ctk.CTkButton(self.main_frame, text="Réinitialiser le mot de passe", command=self._handle_step2).pack(
            pady=20)
        ctk.CTkButton(self.main_frame, text="< Retour", fg_color="transparent", command=self._setup_step1).pack()

    def _handle_step2(self):
        code = self.code_entry.get()
        new_password = self.new_password_entry.get()
        confirm_password = self.confirm_password_entry.get()

        if not all([code, new_password, confirm_password]):
            self.app_controller.show_toast("Veuillez remplir tous les champs.", "warning")
            return

        if new_password != confirm_password:
            self.app_controller.show_toast("Les mots de passe ne correspondent pas.", "error")
            return

        def task():
            return self.controller.reset_password(self.username_to_reset, code, new_password)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur : {error}", "error")
                return

            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success')
                self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')

        self.run_task(task, on_complete, "Réinitialisation du mot de passe...")