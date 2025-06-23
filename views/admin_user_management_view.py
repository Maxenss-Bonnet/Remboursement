import customtkinter as ctk
from tkinter import messagebox, simpledialog
from config.settings import ASSIGNABLE_ROLES
from .admin_config_view import AdminConfigView
from .admin_backup_view import AdminBackupView
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.animation_mixin import AnimationMixin


class AdminUserManagementView(ctk.CTkToplevel, TaskRunnerMixin, AnimationMixin):
    def __init__(self, master, auth_controller, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        AnimationMixin.__init__(self, master)

        self.auth_controller = auth_controller
        self.app_controller = app_controller
        self.master = master

        self.title("Gestion des Utilisateurs (Admin)")
        self.geometry("950x600")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(800, 400)
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        title_label = ctk.CTkLabel(main_frame, text="Gestion des Utilisateurs et Maintenance",
                                   font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(10, 15))

        action_bar_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_bar_frame.pack(fill="x", pady=(0, 10))

        btn_create_user = ctk.CTkButton(action_bar_frame, text="Créer un Utilisateur",
                                        command=self._open_create_user_dialog)
        btn_create_user.pack(side="left", padx=5)

        btn_show_roles_info = ctk.CTkButton(action_bar_frame, text="Infos sur les Rôles",
                                            command=self._show_role_descriptions)
        btn_show_roles_info.pack(side="left", padx=5)

        btn_manage_backups = ctk.CTkButton(action_bar_frame, text="Gérer les Sauvegardes",
                                           command=self._open_backup_management_view,
                                           fg_color="#0B5345", hover_color="#0E6655")
        btn_manage_backups.pack(side="left", padx=5)

        btn_config_smtp = ctk.CTkButton(action_bar_frame, text="Configuration Email",
                                        command=self._open_smtp_config_dialog,
                                        fg_color="#334155", hover_color="#475569")
        btn_config_smtp.pack(side="left", padx=5)

        self.scrollable_frame = ctk.CTkScrollableFrame(main_frame,
                                                       label_text="Utilisateurs enregistrés (sauf 'admin')")
        self.scrollable_frame.pack(expand=True, fill="both", padx=5, pady=(0, 5))
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.populate_user_list()

        close_button = ctk.CTkButton(self, text="Fermer", command=self.close_animated, width=100)
        close_button.pack(pady=10)
        self.fade_in()

    def _open_backup_management_view(self):
        AdminBackupView(self, self.auth_controller, self.app_controller)

    def _open_smtp_config_dialog(self):
        AdminConfigView(self, self.auth_controller)

    def populate_user_list(self):
        def task():
            return self.auth_controller.get_all_users_for_management()

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", 'error')
                return

            utilisateurs = result
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()

            if not utilisateurs:
                ctk.CTkLabel(self.scrollable_frame, text="Aucun autre utilisateur à gérer.").pack(pady=10)
                return

            for i, user_data in enumerate(utilisateurs):
                user_login = user_data.get("login")
                user_email = user_data.get("email")
                user_roles_list = user_data.get("roles", [])
                user_roles_str = ", ".join(user_roles_list) if user_roles_list else "Aucun rôle assigné"

                item_frame = ctk.CTkFrame(self.scrollable_frame, corner_radius=3)
                item_frame.pack(fill="x", pady=(2, 2), padx=4)

                item_frame.columnconfigure(0, weight=2)
                item_frame.columnconfigure(1, weight=2)
                item_frame.columnconfigure(2, weight=0)
                item_frame.columnconfigure(3, weight=0)

                info_text = f"{user_login}"
                ctk.CTkLabel(item_frame, text=info_text, anchor="w",
                             font=ctk.CTkFont(weight="bold")).grid(row=0, column=0,
                                                                   padx=5, pady=3,
                                                                   sticky="w")

                email_text = f"Email: {user_email}"
                ctk.CTkLabel(item_frame, text=email_text, anchor="w", font=ctk.CTkFont(size=11)).grid(
                    row=1, column=0,
                    padx=5, pady=(0, 3),
                    sticky="w")

                roles_text = f"Rôles: {user_roles_str}"
                ctk.CTkLabel(item_frame, text=roles_text, anchor="w", font=ctk.CTkFont(size=11),
                             wraplength=250).grid(row=0,
                                                  rowspan=2,
                                                  column=1,
                                                  padx=5,
                                                  pady=3,
                                                  sticky="w")

                if user_login != "admin":
                    modify_button = ctk.CTkButton(
                        item_frame,
                        text="Modifier",
                        width=70,
                        command=lambda u_login=user_login, u_email=user_email,
                                       u_roles=user_roles_list: self._open_modify_user_dialog(u_login,
                                                                                              u_email,
                                                                                              u_roles)
                    )
                    modify_button.grid(row=0, rowspan=2, column=2, padx=(10, 2), pady=5, sticky="e")

                    delete_button = ctk.CTkButton(
                        item_frame,
                        text="Supprimer",
                        width=70,
                        fg_color="red",
                        hover_color="darkred",
                        command=lambda u=user_login: self._confirm_delete_user(u)
                    )
                    delete_button.grid(row=0, rowspan=2, column=3, padx=(2, 5), pady=5, sticky="e")

        self.run_task(task, on_complete, "Chargement des utilisateurs...")

    def _confirm_delete_user(self, username_to_delete: str):
        if messagebox.askyesno("Confirmation de Suppression",
                               f"Êtes-vous sûr de vouloir supprimer l'utilisateur '{username_to_delete}' ?\n"
                               "Cette action est irréversible.",
                               icon=messagebox.WARNING, parent=self):
            def task():
                return self.auth_controller.admin_delete_user(username_to_delete)

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur: {error}", 'error')
                    return

                succes, message = result
                if succes:
                    self.app_controller.show_toast(message, 'success')
                    self.app_controller._load_user_cache()
                    self.populate_user_list()
                else:
                    self.app_controller.show_toast(message, 'error')

            self.run_task(task, on_complete, f"Suppression de {username_to_delete}...")

    def _open_create_user_dialog(self):
        self._open_user_form_dialog(mode="create")

    def _open_modify_user_dialog(self, login: str, current_email: str, current_roles: list):
        self._open_user_form_dialog(mode="modify", login_original=login, email_actuel=current_email,
                                    roles_actuels=current_roles)

    def _open_user_form_dialog(self, mode: str, login_original: str = "", email_actuel: str = "",
                               roles_actuels: list | None = None):
        if roles_actuels is None: roles_actuels = []

        title = "Créer un Nouvel Utilisateur" if mode == "create" else f"Modifier Utilisateur: {login_original}"

        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("550x550")
        dialog.transient(self)
        dialog.grab_set()

        # Application de l'animation à la sous-fenêtre
        dialog.attributes('-alpha', 0)

        form_frame = ctk.CTkFrame(dialog)
        form_frame.pack(expand=True, fill="both", padx=20, pady=20)

        ctk.CTkLabel(form_frame, text="Login:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        login_entry = ctk.CTkEntry(form_frame, width=250)
        login_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        if mode == "modify":
            login_entry.insert(0, login_original)

        ctk.CTkLabel(form_frame, text="Email:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        email_entry = ctk.CTkEntry(form_frame, width=250)
        email_entry.insert(0, email_actuel if mode == "modify" else "")
        email_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(form_frame, text="Mot de passe:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        password_entry = ctk.CTkEntry(form_frame, width=250, show="*")
        password_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        if mode == "modify":
            password_entry.configure(placeholder_text="Laisser vide pour ne pas changer")

        ctk.CTkLabel(form_frame, text="Rôles:").grid(row=3, column=0, padx=5, pady=(10, 0), sticky="nw")

        roles_scroll_frame = ctk.CTkScrollableFrame(form_frame, height=150)
        roles_scroll_frame.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        role_vars = {}
        assignable_roles_list = self.auth_controller.get_assignable_roles()
        for role_name in assignable_roles_list:
            var = ctk.StringVar(value="on" if role_name in roles_actuels else "off")
            cb = ctk.CTkCheckBox(roles_scroll_frame, text=role_name, variable=var, onvalue="on",
                                 offvalue="off")
            cb.pack(anchor="w", padx=10, pady=2)
            role_vars[role_name] = var

        def _submit_user_form():
            login_val = login_entry.get().strip()
            email_val = email_entry.get().strip()
            password_val = password_entry.get().strip()
            selected_roles = [role for role, var in role_vars.items() if var.get() == "on"]

            def task():
                if mode == "create":
                    if not password_val:
                        return False, "Le mot de passe est requis pour créer un utilisateur."
                    return self.auth_controller.admin_create_user(login_val, email_val,
                                                                  password_val,
                                                                  selected_roles)
                else:
                    return self.auth_controller.admin_update_user_details(login_original,
                                                                          login_val,
                                                                          email_val,
                                                                          selected_roles,
                                                                          password_val if password_val else None)

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur: {error}", 'error')
                    return

                succes, message = result
                if succes:
                    self.app_controller.show_toast(message, 'success')
                    self.app_controller._load_user_cache()
                    self.populate_user_list()
                    dialog.destroy()
                else:
                    self.app_controller.show_toast(message, 'error')

            self.run_task(task, on_complete, "Sauvegarde en cours...")
            dialog.withdraw()

        submit_button_text = "Créer Utilisateur" if mode == "create" else "Enregistrer Modifications"
        submit_button = ctk.CTkButton(form_frame, text=submit_button_text, command=_submit_user_form)
        submit_button.grid(row=4, column=0, columnspan=2, pady=20)

        # Animation fade-in pour la sous-fenêtre
        alpha = 0

        def fade_in_dialog():
            nonlocal alpha
            alpha += 0.1
            if alpha < 1:
                dialog.attributes('-alpha', alpha)
                dialog.after(20, fade_in_dialog)
            else:
                dialog.attributes('-alpha', 1)

        fade_in_dialog()

        dialog.after(100,
                     lambda: login_entry.focus_set() if mode == "create" else email_entry.focus_set())

    def _show_role_descriptions(self):
        def task():
            return self.auth_controller.get_role_descriptions_with_users()

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", 'error')
                return

            descriptions_data = result
            desc_window = ctk.CTkToplevel(self)
            desc_window.title("Description des Rôles et Utilisateurs Associés")
            desc_window.geometry("750x550")
            desc_window.transient(self)
            desc_window.grab_set()

            scroll_frame = ctk.CTkScrollableFrame(desc_window)
            scroll_frame.pack(expand=True, fill="both", padx=10, pady=10)

            for role, data in descriptions_data.items():
                desc = data.get("description", "Pas de description.")
                users_with_role = data.get("utilisateurs_actuels", [])

                ctk.CTkLabel(scroll_frame, text=f"{role.replace('_', ' ').title()}:",
                             font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(10, 2))

                desc_textbox = ctk.CTkTextbox(scroll_frame, wrap="word", height=(desc.count('\n') + 2) * 18,
                                              activate_scrollbars=False, border_width=0,
                                              fg_color="transparent")
                desc_textbox.insert("1.0", desc)
                desc_textbox.configure(state="disabled")
                desc_textbox.pack(anchor="w", fill="x", padx=10, pady=(0, 5))

                if users_with_role:
                    ctk.CTkLabel(scroll_frame, text="  Utilisateurs ayant ce rôle:",
                                 font=ctk.CTkFont(size=11, slant="italic")).pack(anchor="w", padx=10)
                    users_str = "\n".join([f"    - {user}" for user in users_with_role])
                    ctk.CTkLabel(scroll_frame, text=users_str, justify="left", anchor="w",
                                 font=ctk.CTkFont(size=11)).pack(
                        anchor="w", padx=20, pady=(0, 10))
                else:
                    ctk.CTkLabel(scroll_frame, text="  Aucun utilisateur n'a actuellement ce rôle.",
                                 font=ctk.CTkFont(size=11, slant="italic")).pack(anchor="w", padx=10,
                                                                                 pady=(0, 10))

                ctk.CTkFrame(scroll_frame, height=1, fg_color="gray50").pack(fill="x", pady=5)

            ctk.CTkButton(desc_window, text="Fermer", command=desc_window.destroy).pack(pady=10)

        self.run_task(task, on_complete, "Chargement des descriptions...")