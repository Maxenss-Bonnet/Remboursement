import customtkinter as ctk
import os
import sys
import threading
import time
import shutil
from tkinter import messagebox
from PIL import Image, ImageDraw, ImageFont

from views.login_view import LoginView
from views.main_view import MainView
from controllers.auth_controller import AuthController
from controllers.remboursement_controller import RemboursementController
from controllers.password_reset_controller import PasswordResetController
from models import user_model
from utils.ui_utils import ToastManager, LoadingOverlay
from utils.database_manager import create_tables, is_db_writer_busy
from utils import global_task_tracker
from utils.cache_manager import CacheManager
from config.settings import REMBOURSEMENTS_ATTACHMENTS_DIR, ensure_shared_dirs_exist, load_smtp_config, \
    PROFILE_PICTURES_DIR
from utils.image_utils import get_or_create_circular_pfp


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
        self.preloaded_pfp_cache = None
        self.preloading_thread = None
        self.global_loading_overlay = LoadingOverlay(self.root)

    def run_initialization(self):
        load_smtp_config()
        ensure_shared_dirs_exist()
        self._ensure_database_is_ready()
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
                print(f"Erreur pendant la tâche de connexion : {e}")
                self.root.after(0, self.handle_login_failure)

        threading.Thread(target=task, daemon=True).start()

    def handle_login_failure(self):
        self.hide_global_loading()
        self.show_toast("Nom d'utilisateur ou mot de passe incorrect.", "error")
        if self.login_view:
            self.login_view.entry_mdp.delete(0, 'end')
            self.login_view.bouton_connexion.configure(state="normal")

    def transition_to_main_view(self, username: str):
        self.update_global_loading_text("Chargement du profil...")
        self.root.update_idletasks()

        self.current_user = username

        if self.login_view:
            self.login_view.destroy()
            self.login_view = None

        if self.preloading_thread is not None:
            self.preloading_thread.join(timeout=5)

        self.show_main_view()
        self._sync_user_cache()
        self.hide_global_loading()

    def show_global_loading(self, message: str):
        self.global_loading_overlay.set_message(message)
        self.global_loading_overlay.show()

    def update_global_loading_text(self, message: str):
        self.global_loading_overlay.set_message(message)

    def hide_global_loading(self):
        self.global_loading_overlay.hide()

    def is_application_busy(self) -> bool:
        """Vérifie si des tâches critiques sont en cours."""
        return global_task_tracker.is_busy() or is_db_writer_busy()

    def _preload_data(self):
        def _preloading_task():
            print("Pré-chargement des données en arrière-plan démarré...")
            try:
                all_users = self.auth_controller.get_all_users()
                pfp_cache = {}
                pfp_size = 20

                pfp_cache['default'] = self._create_placeholder_image("?", pfp_size)
                pfp_cache['Système'] = self._create_placeholder_image("S", pfp_size)
                pfp_cache['Utilisateur supprimé'] = self._create_placeholder_image("?", pfp_size)

                for user in all_users:
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
                self.preloaded_pfp_cache = pfp_cache
                print("Pré-chargement des données terminé avec succès.")
            except Exception as e:
                print(f"Erreur durant le pré-chargement des données : {e}")
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
        self._preload_data()

    def _sync_user_cache(self):
        if self.remboursement_controller is None:
            self._remboursement_controller_factory(self.current_user)
        if not self.remboursement_controller or not self.current_user:
            return

        def task():
            user_data = self.auth_controller.get_user_data(self.current_user)
            if not user_data:
                return

            all_demandes, _ = self.remboursement_controller.get_demandes_filtrees_triees(
                user_roles=user_data.roles,
                filter_choice="Toutes les demandes",
                sort_choice="Date de création (récent)",
                search_term="",
                is_archive_mode=False,
                archive_date_range=None,
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
        self.main_view = MainView(
            master=self.root,
            nom_utilisateur=self.current_user,
            app_controller=self,
            remboursement_controller_factory=self._remboursement_controller_factory,
            preloaded_pfp_cache=self.preloaded_pfp_cache
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
            self.root.on_attempt_close(is_restart=True)
        else:
            if self.is_application_busy():
                self.show_toast("Veuillez attendre la fin des opérations en cours...", "warning")
            else:
                self.show_login_view()

    def show_admin_warning_popup(self):
        self.show_toast("Vous êtes connecté en tant qu'administrateur.\nCertaines actions sont irréversibles.",
                        "warning")