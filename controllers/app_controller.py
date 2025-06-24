import customtkinter as ctk
import os
import sys
import threading
import time
import shutil
import logging
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont

from views.login_view import LoginView
from views.main_view import MainView
from controllers.auth_controller import AuthController
from controllers.remboursement_controller import RemboursementController
from controllers.password_reset_controller import PasswordResetController
from controllers.user_controller import UserController
from controllers.maintenance_controller import MaintenanceController
from utils.ui_utils import ToastManager, LoadingOverlay
from utils.database_manager import create_tables, is_db_writer_busy
from utils import global_task_tracker
from utils.cache_manager import CacheManager
from config.settings import REMBOURSEMENTS_ATTACHMENTS_DIR, ensure_shared_dirs_exist, load_smtp_config, \
    PROFILE_PICTURES_DIR
from utils.image_utils import get_or_create_circular_pfp

_log = logging.getLogger(__name__)


class AppController:
    def __init__(self, root_tk_app):
        self.root = root_tk_app
        self.auth_controller = AuthController()
        self.password_reset_controller = PasswordResetController(self.auth_controller)
        self.user_controller = UserController()
        self.maintenance_controller = MaintenanceController()
        self.remboursement_controller = None
        self.current_user = None
        self.login_view = None
        self.main_view = None
        self.toast_manager = ToastManager(self.root)
        self.cache_manager = CacheManager()
        self.preloaded_pfp_cache = None
        self.user_cache = {}
        self.preloading_thread = None
        self.global_loading_overlay = LoadingOverlay(self.root)
        self.pfp_cache_lock = threading.Lock()

    def run_initialization(self):
        load_smtp_config()
        ensure_shared_dirs_exist()
        self._ensure_database_is_ready_and_healthy()
        self._load_user_cache()
        self._run_startup_tasks()

    def show_initial_view(self):
        self.show_login_view()

    def perform_login_and_show_main_view(self, username, password):
        if self.login_view:
            self.login_view.bouton_connexion.configure(state="disabled")

        self.show_global_loading("Connexion...")

        def task():
            try:
                user = self.auth_controller.tenter_connexion(username, password)
                if user:
                    self.root.after(0, self.transition_to_main_view, user)
                else:
                    self.root.after(0, self.handle_login_failure)
            except Exception as e:
                _log.error(f"Erreur pendant la tâche de connexion : {e}", exc_info=True)
                self.root.after(0, self.handle_login_failure)

        threading.Thread(target=task, daemon=True).start()

    def handle_login_failure(self):
        self.hide_global_loading()
        self.show_toast("Nom d'utilisateur ou mot de passe incorrect.", "error")
        if self.login_view:
            self.login_view.entry_mdp.delete(0, 'end')
            self.login_view.bouton_connexion.configure(state="normal")

    def transition_to_main_view(self, username: str):
        self.current_user = username
        if self.login_view:
            self.login_view.destroy()
            self.login_view = None

        self.update_global_loading_text("Préparation de l'affichage...")
        self.root.update_idletasks()

        if self.preloading_thread is not None:
            self.preloading_thread.join()

        self.show_main_view()
        self.hide_global_loading()

    def show_global_loading(self, message: str):
        self.global_loading_overlay.set_message(message)
        self.global_loading_overlay.show()

    def update_global_loading_text(self, message: str):
        self.global_loading_overlay.set_message(message)

    def hide_global_loading(self):
        self.global_loading_overlay.hide()

    def is_application_busy(self) -> bool:
        return global_task_tracker.is_busy() or is_db_writer_busy()

    def _load_user_cache(self):
        _log.info("Chargement/Rafraîchissement du cache utilisateur.")
        all_users = self.user_controller.get_all_users()
        self.user_cache = {user.login: user for user in all_users}
        _log.info(f"{len(self.user_cache)} utilisateurs chargés dans le cache.")

    def get_user_from_cache(self, login: str):
        return self.user_cache.get(login)

    def get_all_users_from_cache(self):
        return list(self.user_cache.values())

    def _preload_data(self):
        def _preloading_task():
            _log.info("Pré-chargement des données en arrière-plan démarré...")
            try:
                # Préchargement des photos de profil
                users_from_cache = self.get_all_users_from_cache()
                pfp_cache = {}
                pfp_size = 20
                pfp_cache['default'] = self._create_placeholder_image("?", pfp_size)
                pfp_cache['Système'] = self._create_placeholder_image("S", pfp_size)
                pfp_cache['Utilisateur supprimé'] = self._create_placeholder_image("?", pfp_size)
                for user in users_from_cache:
                    full_path = None
                    if user.profile_picture_path and os.path.exists(
                            os.path.join(PROFILE_PICTURES_DIR, user.profile_picture_path)):
                        full_path = os.path.join(PROFILE_PICTURES_DIR, user.profile_picture_path)
                    pfp_image = get_or_create_circular_pfp(
                        login=user.login, source_path=full_path, size=pfp_size,
                        cache_manager=self.cache_manager
                    )
                    if pfp_image:
                        pfp_cache[user.login] = pfp_image
                    else:
                        initial = user.login[0].upper() if user.login else "?"
                        pfp_cache[user.login] = self._create_placeholder_image(initial, pfp_size)
                with self.pfp_cache_lock:
                    self.preloaded_pfp_cache = pfp_cache

                # Préchargement de la vue par défaut de l'utilisateur
                if self.current_user:
                    user_data = self.get_user_from_cache(self.current_user)
                    if user_data:
                        controller = self._remboursement_controller_factory(self.current_user)
                        demandes, total = controller.get_demandes_filtrees_triees(
                            user_roles=user_data.roles,
                            filter_choice=user_data.default_filter,
                            sort_choice="Date de création (récent)",
                            search_term="",
                            is_archive_mode=False,
                            archive_date_range=None,
                            limit=20, offset=0
                        )
                        cache_key = f"{self.current_user}_{user_data.default_filter}_default"
                        self.cache_manager.set_demand_query_cache(cache_key, (demandes, total))
                        _log.info(f"Vue par défaut préchargée pour {self.current_user} avec {len(demandes)} demandes.")

                _log.info("Pré-chargement des données terminé avec succès.")
            except Exception as e:
                _log.error(f"Erreur durant le pré-chargement des données : {e}", exc_info=True)
                with self.pfp_cache_lock:
                    self.preloaded_pfp_cache = {}

        if self.preloading_thread is None or not self.preloading_thread.is_alive():
            self.preloading_thread = threading.Thread(target=_preloading_task, daemon=True)
            self.preloading_thread.start()

    def _create_placeholder_image(self, initial: str, size: int) -> ctk.CTkImage:
        placeholder = Image.new('RGBA', (size, size), (80, 80, 80, 255))
        draw = ImageDraw.Draw(placeholder)
        try:
            font_size = int(size * 0.6)
            font = ImageFont.truetype("arial", font_size)
        except IOError:
            font = ImageFont.load_default()
        draw.text((size / 2, size / 2), initial, font=font, anchor="mm", fill=(220, 220, 220))
        return ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=(size, size))

    def _ensure_database_is_ready_and_healthy(self):
        try:
            create_tables()
            is_healthy, message = self.maintenance_controller.run_database_health_check()
            if not is_healthy:
                messagebox.showerror("Erreur Critique de Base de Données",
                                     f"L'intégrité de la base de données est compromise.\n"
                                     f"Raison : {message}\n\n"
                                     "Veuillez contacter l'administrateur pour restaurer une sauvegarde.\n"
                                     "L'application va se fermer.")
                sys.exit(1)
        except Exception as e:
            messagebox.showerror("Erreur Critique de Base de Données",
                                 f"Impossible d'initialiser ou de vérifier la base de données.\nErreur: {e}\n\nL'application va se fermer.")
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
                            _log.info(f"Nettoyage du dossier temporaire orphelin : {folder_path}")
        except Exception as e:
            _log.error(f"Erreur lors du nettoyage des dossiers temporaires orphelins : {e}", exc_info=True)

    def _run_startup_tasks(self):
        def task():
            _log.info("Lancement des tâches de démarrage...")
            self._cleanup_orphaned_temp_folders()
            rc_temp = RemboursementController(utilisateur_actuel="system")
            rc_temp.archive_old_requests()
            backup_status = self.maintenance_controller.run_automatic_backup()
            _log.info(f"Statut de la sauvegarde automatique : {backup_status}")
            _log.info("Tâches de démarrage terminées.")

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
        self._preload_data()

    def show_main_view(self):
        # Le préchargement pour l'utilisateur est maintenant lancé à la connexion
        # La vue principale peut donc être créée directement
        self.main_view = MainView(
            master=self.root,
            nom_utilisateur=self.current_user,
            app_controller=self,
            remboursement_controller_factory=self._remboursement_controller_factory,
            preloaded_pfp_cache=self.preloaded_pfp_cache
        )
        self.root.title(f"Gestion Remboursements - {self.current_user}")
        self._preload_data()  # Relancer pour la vue principale

    def request_restart(self, reason: str):
        if messagebox.askyesno("Redémarrage Requis",
                               f"{reason}\n\nUn redémarrage de l'application est nécessaire pour appliquer tous les changements.\nVoulez-vous redémarrer maintenant ?"):
            self.on_logout(restart=True)

    def on_logout(self, restart=False):
        if self.main_view:
            self.main_view.stop_polling()

        if restart:
            self.root.on_attempt_close(is_restart=True)
        else:
            if self.is_application_busy():
                self.show_toast("Veuillez attendre la fin des opérations en cours...", "warning")
            else:
                self.show_login_view()

    def show_admin_warning_popup(self):
        self.show_toast("Vous êtes connecté en tant qu'administrateur.\nCertaines actions sont irréversibles.",
                        "warning")