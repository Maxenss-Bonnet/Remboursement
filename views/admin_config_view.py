import customtkinter as ctk
from tkinter import messagebox
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.animation_mixin import AnimationMixin


class AdminConfigView(ctk.CTkToplevel, TaskRunnerMixin, AnimationMixin):
    def __init__(self, master, maintenance_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        AnimationMixin.__init__(self, master)

        self.transient(master)
        self.grab_set()
        self.title("Configuration Email Récupération")
        self.geometry("550x450")
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self.app_controller = master.app_controller
        self.maintenance_controller = maintenance_controller
        self.config_data = self.maintenance_controller.get_smtp_config()

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        self.entries = {}
        fields = {
            "server": "Serveur SMTP:",
            "port": "Port:",
            "email_sender": "E-mail de l'expéditeur:",
            "password": "Mot de passe d'application:",
            "use_tls": "Utiliser TLS (True/False):",
            "use_ssl": "Utiliser SSL (True/False):"
        }

        for i, (key, label) in enumerate(fields.items()):
            ctk.CTkLabel(self.main_frame, text=label).grid(row=i, column=0, padx=10, pady=8, sticky="w")
            entry = ctk.CTkEntry(self.main_frame, width=250)
            if key == "password":
                entry.configure(show="*")
            entry.insert(0, str(self.config_data.get(key, "")))
            entry.grid(row=i, column=1, padx=10, pady=8, sticky="ew")
            self.entries[key] = entry

        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=20)

        ctk.CTkButton(button_frame, text="Tester la Connexion", command=self._test_connection).pack(
            side="left",
            padx=10)
        ctk.CTkButton(button_frame, text="Enregistrer", command=self._save_config).pack(side="left",
                                                                                        padx=10)
        ctk.CTkButton(button_frame, text="Annuler", command=self.close_animated, fg_color="gray").pack(side="left",
                                                                                                padx=10)
        self.fade_in()

    def _get_current_values(self):
        return {key: entry.get() for key, entry in self.entries.items()}

    def _test_connection(self):
        current_config = self._get_current_values()
        try:
            current_config['port'] = int(current_config.get('port', 587))
            current_config['use_tls'] = current_config.get('use_tls', 'true').lower() in ('true', '1', 't')
            current_config['use_ssl'] = current_config.get('use_ssl', 'false').lower() in ('true', '1', 't')
        except ValueError:
            self.app_controller.show_toast("Le port doit être un nombre.", 'error')
            return

        def task():
            return self.maintenance_controller.test_smtp_connection(current_config)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Échec de la Connexion SMTP.\nErreur : {error}", 'error')
                return

            is_ok, message = result
            if is_ok:
                self.app_controller.show_toast("La connexion au serveur SMTP a réussi !", 'success')
            else:
                self.app_controller.show_toast(f"Échec de la Connexion SMTP.\nErreur : {message}", 'error')

        self.run_task(task, on_complete, "Test de la connexion SMTP...")

    def _save_config(self):
        new_config_data = self._get_current_values()

        def task():
            return self.maintenance_controller.save_smtp_config(new_config_data)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Impossible d'enregistrer : {error}", 'error')
                return

            success, message = result
            if success:
                self.app_controller.show_toast("Configuration enregistrée. Redémarrage requis.", 'info')
                self.close_animated()
            else:
                self.app_controller.show_toast(f"Impossible d'enregistrer la configuration : {message}", 'error')

        self.run_task(task, on_complete, "Enregistrement de la configuration...")