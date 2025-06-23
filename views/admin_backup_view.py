import customtkinter as ctk
from tkinter import messagebox
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.animation_mixin import AnimationMixin


class AdminBackupView(ctk.CTkToplevel, TaskRunnerMixin, AnimationMixin):
    def __init__(self, master, auth_controller, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        AnimationMixin.__init__(self, master)

        self.auth_controller = auth_controller
        self.app_controller = app_controller

        self.title("Gestion des Sauvegardes de la Base de Données")
        self.geometry("750x550")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(500, 300)
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        action_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_frame.pack(fill="x", pady=5)
        ctk.CTkButton(action_frame, text="Créer une Sauvegarde Manuelle",
                      command=self._action_create_backup).pack(side="left", padx=5)
        ctk.CTkButton(action_frame, text="Nettoyer Fichiers de Restauration",
                      command=self._action_cleanup_restore_files, fg_color="gray50").pack(side="left", padx=5)

        self.scrollable_frame = ctk.CTkScrollableFrame(main_frame, label_text="Sauvegardes Existantes")
        self.scrollable_frame.pack(expand=True, fill="both", padx=5, pady=5)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.populate_backup_list()
        self.fade_in()

    def populate_backup_list(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        def task():
            return self.auth_controller.get_database_backups()

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", "error")
                return

            backup_files, message = result
            if message:
                self.app_controller.show_toast(message, "error")
                return

            if not backup_files:
                ctk.CTkLabel(self.scrollable_frame, text="Aucune sauvegarde trouvée.").pack(pady=20)
                return

            for backup_file in backup_files:
                item_frame = ctk.CTkFrame(self.scrollable_frame)
                item_frame.pack(fill="x", pady=3, padx=3)
                item_frame.columnconfigure(0, weight=1)

                ctk.CTkLabel(item_frame, text=backup_file, anchor="w").grid(row=0, column=0, padx=10, sticky="w")

                button_sub_frame = ctk.CTkFrame(item_frame, fg_color="transparent")
                button_sub_frame.grid(row=0, column=1, padx=10, pady=5, sticky="e")

                restore_btn = ctk.CTkButton(button_sub_frame, text="Restaurer", fg_color="#D35400",
                                            hover_color="#A93226", width=100,
                                            command=lambda f=backup_file: self._action_restore_backup(f))
                restore_btn.pack(side="left", padx=(0, 5))

                delete_btn = ctk.CTkButton(button_sub_frame, text="Supprimer", fg_color="#C0392B",
                                           hover_color="#922B21", width=100,
                                           command=lambda f=backup_file: self._action_delete_backup(f))
                delete_btn.pack(side="left")

        self.run_task(task, on_complete, "Recherche des sauvegardes...")

    def _action_create_backup(self):
        def task():
            return self.auth_controller.admin_backup_database()

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", "error")
                return
            success, message = result
            if success:
                self.app_controller.show_toast(message, "success")
                self.populate_backup_list()
            else:
                self.app_controller.show_toast(message, "error")

        self.run_task(task, on_complete, "Création de la sauvegarde...")

    def _action_restore_backup(self, backup_filename):
        msg = (f"Voulez-vous vraiment restaurer la sauvegarde '{backup_filename}' ?\n\n"
               "ATTENTION : L'opération est IRRÉVERSIBLE.\n"
               "La base de données actuelle sera écrasée. "
               "Assurez-vous qu'aucun autre utilisateur n'est connecté.\n\n"
               "L'application redémarrera après la restauration.")

        if messagebox.askyesno("Confirmation de Restauration", msg, icon='warning', parent=self):
            def task():
                return self.auth_controller.admin_restore_database(backup_filename)

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur de restauration : {error}", "error")
                    return
                success, message = result
                if success:
                    self.app_controller.show_toast(message, "info")
                    self.app_controller.request_restart(
                        "Restauration de la base de données terminée.")
                else:
                    self.app_controller.show_toast(message, "error")

            self.run_task(task, on_complete, "Restauration en cours...")

    def _action_delete_backup(self, backup_filename):
        msg = f"Voulez-vous vraiment supprimer la sauvegarde '{backup_filename}' ?\n\nCette action est définitive."
        if messagebox.askyesno("Confirmation de Suppression", msg, icon='warning', parent=self):
            def task():
                return self.auth_controller.admin_delete_backup(backup_filename)

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur: {error}", "error")
                    return
                success, message = result
                if success:
                    self.app_controller.show_toast(message, "success")
                    self.populate_backup_list()
                else:
                    self.app_controller.show_toast(message, "error")

            self.run_task(task, on_complete, "Suppression de la sauvegarde...")

    def _action_cleanup_restore_files(self):
        msg = "Ceci supprimera tous les fichiers de sécurité temporaires (.before_restore) créés lors des restaurations précédentes.\n\nVoulez-vous continuer ?"
        if messagebox.askyesno("Confirmation du Nettoyage", msg, icon='info', parent=self):
            def task():
                return self.auth_controller.admin_cleanup_restore_files()

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur: {error}", "error")
                    return
                success, message = result
                if success:
                    self.app_controller.show_toast(message, "success")
                else:
                    self.app_controller.show_toast(message, "error")

            self.run_task(task, on_complete, "Nettoyage des fichiers...")