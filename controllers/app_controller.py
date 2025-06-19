import customtkinter as ctk
import os
import sys
import threading
import time
import shutil
from tkinter import messagebox
from views.login_view import LoginView
from views.main_view import MainView
from controllers.auth_controller import AuthController
from controllers.remboursement_controller import RemboursementController
from controllers.password_reset_controller import PasswordResetController
from models import user_model
from utils.ui_utils import ToastManager
from utils.database_manager import create_tables
from utils.cache_manager import CacheManager
from config.settings import REMBOURSEMENTS_ATTACHMENTS_DIR, ensure_shared_dirs_exist, load_smtp_config


class AppController:
    def __init__(self, root_tk_app):
        self.root = root_tk_app
        self.auth_controller = AuthController()
        self.password_reset_controller = PasswordResetController(self.auth_controller)
        self.remboursement_controller = None
        self.current_user = None
        self.login_view = None
        self.main_view = None

        self.toast_manager = ToastManager(self.root)
        self.cache_manager = CacheManager()

        load_smtp_config()
        ensure_shared_dirs_exist()
        self._ensure_database_is_ready()
        self._run_startup_tasks()
        self.show_login_view()

    def _ensure_database_is_ready(self):
        try:
            create_tables()
        except Exception as e:
            messagebox.showerror("Erreur Critique de Base de Données",
                                 f"Impossible d'initialiser la base de données.\nErreur: {e}\n\nL'application va se fermer.")
            sys.exit(1)

    def _cleanup_orphaned_temp_folders(self):
        try:
            base_dir = REMBOURSEMENTS_ATTACHMENTS_DIR
            if not os.path.isdir(base_dir):
                return

            cutoff = time.time() - (24 * 3600)
            for filename in os.listdir(base_dir):
                if filename.startswith("temp_creation_"):
                    folder_path = os.path.join(base_dir, filename)
                    if os.path.isdir(folder_path):
                        folder_mtime = os.path.getmtime(folder_path)
                        if folder_mtime < cutoff:
                            shutil.rmtree(folder_path, ignore_errors=True)
                            print(f"Nettoyage du dossier temporaire orphelin : {folder_path}")
        except Exception as e:
            print(f"Erreur lors du nettoyage des dossiers temporaires orphelins : {e}")

    def _run_startup_tasks(self):
        def task():
            print("Lancement des tâches de démarrage...")
            self._cleanup_orphaned_temp_folders()

            rc_temp = RemboursementController(utilisateur_actuel="system")
            rc_temp.archive_old_requests()
            print("Tâches de démarrage terminées.")

        startup_thread = threading.Thread(target=task, daemon=True)
        startup_thread.start()

    def _remboursement_controller_factory(self, nom_utilisateur: str) -> RemboursementController:
        if self.remboursement_controller is None:
            self.remboursement_controller = RemboursementController(nom_utilisateur)
        else:
            self.remboursement_controller.utilisateur_actuel = nom_utilisateur
        return self.remboursement_controller

    def show_toast(self, message: str, m_type: str = 'success'):
        self.toast_manager.show_toast(message, m_type)

    def show_login_view(self):
        self.current_user = None
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        if self.main_view:
            self.main_view.destroy()
            self.main_view = None

        self.login_view = LoginView(self.root, self.auth_controller, self)
        self.root.title("Application de Remboursement - Connexion")

    def on_login_success(self, nom_utilisateur: str):
        self.current_user = nom_utilisateur
        self._sync_user_cache()
        self.show_main_view()

    def _sync_user_cache(self):
        if self.remboursement_controller is None:
            self._remboursement_controller_factory(self.current_user)
        if not self.remboursement_controller or not self.current_user:
            return

        def task():
            user_data = self.auth_controller.get_user_data(self.current_user)
            if not user_data:
                return

            all_demandes = self.remboursement_controller.get_demandes_filtrees_triees(
                user_roles=user_data.roles,
                filter_choice="Toutes les demandes",
                sort_choice="Date de création (récent)",
                search_term="",
                include_archives=False,
                limit=None,
                offset=0
            )

            actionable_demandes = [d for d in all_demandes if d.is_active_for(user_data.roles, user_data.login)]
            top_10_demandes = all_demandes[:10]

            combined_demands_dict = {d.id_demande: d for d in actionable_demandes}
            for d in top_10_demandes:
                if d.id_demande not in combined_demands_dict:
                    combined_demands_dict[d.id_demande] = d

            demandes_to_cache = list(combined_demands_dict.values())

            self.cache_manager.sync_proactive_cache(demandes_to_cache)
            print(f"Cache proactif synchronisé pour {self.current_user}. {len(demandes_to_cache)} demande(s) en cache.")

        cache_thread = threading.Thread(target=task, daemon=True)
        cache_thread.start()

    def show_main_view(self):
        if self.login_view:
            self.root.focus_set()
            self.login_view.destroy()
            self.login_view = None

        self.main_view = MainView(
            master=self.root,
            nom_utilisateur=self.current_user,
            app_controller=self,
            remboursement_controller_factory=self._remboursement_controller_factory
        )
        self.root.title(f"Gestion Remboursements - {self.current_user}")

    def request_restart(self, reason: str):
        if messagebox.askyesno("Redémarrage Requis",
                               f"{reason}\n\nUn redémarrage de l'application est nécessaire pour appliquer tous les changements.\nVoulez-vous redémarrer maintenant ?"):
            self.on_logout(restart=True)

    def on_logout(self, restart=False):
        if self.main_view:
            self.main_view.stop_polling()

        if restart:
            try:
                python = sys.executable
                os.execl(python, python, *sys.argv)
            except Exception as e:
                print(f"Erreur lors de la tentative de redémarrage : {e}")
                self.show_toast("Le redémarrage automatique a échoué. Veuillez relancer l'application.", "info")
        else:
            self.show_login_view()

    def show_admin_warning_popup(self):
        self.show_toast("Vous êtes connecté en tant qu'administrateur.\nCertaines actions sont irréversibles.",
                        "warning")