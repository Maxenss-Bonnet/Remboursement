import customtkinter as ctk
from utils.password_utils import check_password_strength
from views.mixins.task_runner_mixin import TaskRunnerMixin


class LoginView(ctk.CTkFrame, TaskRunnerMixin):
    def __init__(self, master, auth_controller, app_controller):
        ctk.CTkFrame.__init__(self, master, corner_radius=0, fg_color="transparent")
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.master = master
        self.auth_controller = auth_controller
        self.app_controller = app_controller
        self.pack(fill="both", expand=True)
        self.creer_widgets_connexion()

    def creer_widgets_connexion(self):
        main_frame = ctk.CTkFrame(self, width=380, height=420, corner_radius=10)
        main_frame.place(relx=0.5, rely=0.5, anchor="center")

        label_titre = ctk.CTkLabel(main_frame, text="Connexion Utilisateur", font=ctk.CTkFont(size=20, weight="bold"))
        label_titre.pack(pady=(30, 15))

        self.entry_utilisateur = ctk.CTkEntry(main_frame, placeholder_text="Nom d'utilisateur", width=250)
        self.entry_utilisateur.pack(pady=10, padx=20)
        self.entry_utilisateur.bind("<Return>", lambda event: self._action_connexion())

        self.entry_mdp = ctk.CTkEntry(main_frame, placeholder_text="Mot de passe", show="*", width=250)
        self.entry_mdp.pack(pady=5, padx=20)
        self.entry_mdp.bind("<Return>", lambda event: self._action_connexion())

        self.show_password_var_login = ctk.BooleanVar()
        ctk.CTkCheckBox(main_frame, text="Afficher le mot de passe", variable=self.show_password_var_login,
                        command=self._toggle_login_password_visibility).pack(padx=20, pady=(0, 10), anchor="w")

        bouton_connexion = ctk.CTkButton(main_frame, text="Se connecter", command=self._action_connexion, width=200)
        bouton_connexion.pack(pady=10, padx=20)

        bouton_modifier_mdp = ctk.CTkButton(main_frame, text="Modifier mon mot de passe",
                                            command=self._ouvrir_fenetre_modifier_mdp, width=220, fg_color="gray")
        bouton_modifier_mdp.pack(pady=6, padx=20)

        bouton_mdp_oublie = ctk.CTkButton(main_frame, text="Mot de passe oublié ?",
                                          command=self._ouvrir_fenetre_mdp_oublie, width=220, fg_color="gray")
        bouton_mdp_oublie.pack(pady=(6, 30), padx=20)

        self.after(100, self.entry_utilisateur.focus_set)

    def _toggle_login_password_visibility(self):
        show_char = "" if self.show_password_var_login.get() else "*"
        self.entry_mdp.configure(show=show_char)

    def _action_connexion(self):
        nom_utilisateur = self.entry_utilisateur.get()
        mot_de_passe = self.entry_mdp.get()

        if not nom_utilisateur or not mot_de_passe:
            self.app_controller.show_toast("Veuillez entrer un nom d'utilisateur et un mot de passe.", "error")
            return

        def task():
            return self.auth_controller.tenter_connexion(nom_utilisateur, mot_de_passe)

        def on_complete(utilisateur_connecte, error):
            if error:
                self.app_controller.show_toast(f"Erreur de connexion: {error}", "error")
                return

            if utilisateur_connecte:
                self.focus_set()
                self.after(10, lambda: self.app_controller.on_login_success(utilisateur_connecte))
            else:
                self.app_controller.show_toast("Nom d'utilisateur ou mot de passe incorrect.", "error")
                self.entry_mdp.delete(0, 'end')

        self.run_task(task, on_complete, "Connexion...")

    def _ouvrir_fenetre_modifier_mdp(self):
        # Cette sous-fenêtre peut aussi être adaptée pour utiliser le mixin si besoin,
        # mais pour l'instant, nous corrigeons l'erreur principale.
        # Pour la simplicité, on laisse cette partie telle quelle car elle n'était pas la source du plantage.
        dialog = ctk.CTkToplevel(self.master)
        dialog.title("Modifier le mot de passe")
        dialog.geometry("480x520")
        dialog.transient(self.master)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Nom d'utilisateur:", font=ctk.CTkFont(size=14)).pack(pady=(20, 0))
        entry_user = ctk.CTkEntry(dialog, width=300, height=30)
        entry_user.pack(pady=5)

        ctk.CTkLabel(dialog, text="Ancien mot de passe:", font=ctk.CTkFont(size=14)).pack(pady=(10, 0))
        entry_ancien_mdp = ctk.CTkEntry(dialog, show="*", width=300, height=30)
        entry_ancien_mdp.pack(pady=5)

        ctk.CTkLabel(dialog, text="Nouveau mot de passe:", font=ctk.CTkFont(size=14)).pack(pady=(10, 0))
        entry_nouveau_mdp = ctk.CTkEntry(dialog, show="*", width=300, height=30)
        entry_nouveau_mdp.pack(pady=5)

        strength_progress = ctk.CTkProgressBar(dialog, progress_color="grey")
        strength_progress.set(0)
        strength_progress.pack(fill="x", padx=90, pady=(5, 2))
        strength_label = ctk.CTkLabel(dialog, text="", font=ctk.CTkFont(size=12))
        strength_label.pack(fill="x", padx=90)

        ctk.CTkLabel(dialog, text="Confirmer nouveau mot de passe:", font=ctk.CTkFont(size=14)).pack(pady=(10, 0))
        entry_confirm_mdp = ctk.CTkEntry(dialog, show="*", width=300, height=30)
        entry_confirm_mdp.pack(pady=5)

        def _update_strength(event=None):
            password = entry_nouveau_mdp.get()
            if not password:
                strength_label.configure(text="")
                strength_progress.set(0)
                return
            score, feedback = check_password_strength(password)
            progress = score / 5.0
            colors = {"Très faible": "#D32F2F", "Faible": "#F44336", "Moyen": "#FFC107", "Fort": "#4CAF50",
                      "Très fort": "#4CAF50"}
            color = colors.get(feedback, "grey")
            strength_progress.set(progress)
            strength_progress.configure(progress_color=color)
            strength_label.configure(text=feedback, text_color=color)

        entry_nouveau_mdp.bind("<KeyRelease>", _update_strength)

        show_password_var = ctk.BooleanVar()

        def _toggle_visibility():
            show_char = "" if show_password_var.get() else "*"
            entry_ancien_mdp.configure(show=show_char)
            entry_nouveau_mdp.configure(show=show_char)
            entry_confirm_mdp.configure(show=show_char)

        ctk.CTkCheckBox(dialog, text="Afficher les mots de passe", variable=show_password_var,
                        command=_toggle_visibility).pack(pady=10)

        def valider_modification():
            user = entry_user.get()
            ancien = entry_ancien_mdp.get()
            nouveau = entry_nouveau_mdp.get()
            confirm = entry_confirm_mdp.get()

            if not all([user, ancien, nouveau, confirm]):
                self.app_controller.show_toast("Tous les champs sont requis.", "error")
                return
            if nouveau != confirm:
                self.app_controller.show_toast("Le nouveau mot de passe et sa confirmation ne correspondent pas.",
                                               "error")
                return
            if len(nouveau) < 6:
                self.app_controller.show_toast("Le nouveau mot de passe doit comporter au moins 6 caractères.", "error")
                return

            def task():
                return self.auth_controller.modifier_mot_de_passe(user, ancien, nouveau)

            def on_complete(success, error):
                if error:
                    self.app_controller.show_toast(f"Erreur : {error}", "error")
                    return
                if success:
                    self.app_controller.show_toast("Mot de passe modifié avec succès.", 'success')
                    dialog.destroy()
                else:
                    self.app_controller.show_toast(
                        "Échec de la modification. Vérifiez votre nom d'utilisateur et votre ancien mot de passe.",
                        "error")

            # Ici, la sous-fenêtre utilise la méthode de la vue de connexion
            self.run_task(task, on_complete, "Modification en cours...")

        bouton_valider_modif = ctk.CTkButton(dialog, text="Valider la Modification", command=valider_modification,
                                             height=35)
        bouton_valider_modif.pack(pady=20)
        dialog.after(100, lambda: entry_user.focus_set())

    def _ouvrir_fenetre_mdp_oublie(self):
        from views.password_reset_view import PasswordResetView
        PasswordResetView(self, self.app_controller.password_reset_controller, self.app_controller)