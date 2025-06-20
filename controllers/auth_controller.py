import smtplib
import os
import random
import string
import datetime
import shutil
import logging
from models import user_model
from utils import password_utils
from config.settings import (
    ROLES_UTILISATEURS,
    ASSIGNABLE_ROLES,
    save_email_config_to_ini,
    SMTP_CONFIG,
    load_smtp_config,
    PROFILE_PICTURES_DIR,
    DATABASE_FILE,
    SHARED_DATA_BASE_PATH
)
from models.schemas import Utilisateur, UtilisateurUpdate
from utils.cache_manager import CacheManager
from utils.database_manager import get_db_connection

_log = logging.getLogger(__name__)


class AuthController:
    def __init__(self):
        self.reset_codes = {}

    def tenter_connexion(self, nom_utilisateur: str, mot_de_passe_saisi: str) -> str | None:
        user = user_model.obtenir_utilisateur_par_login_data(nom_utilisateur)
        if user and password_utils.verifier_mdp(mot_de_passe_saisi, user.hashed_password):
            return nom_utilisateur
        return None

    def modifier_mot_de_passe(self, nom_utilisateur: str, ancien_mdp: str, nouveau_mdp: str) -> bool:
        user = user_model.obtenir_utilisateur_par_login_data(nom_utilisateur)
        if not user or not password_utils.verifier_mdp(ancien_mdp, user.hashed_password):
            return False

        update_data = UtilisateurUpdate(password=nouveau_mdp)
        success, _ = user_model.mettre_a_jour_utilisateur_data(nom_utilisateur, update_data)
        return success

    def demarrer_procedure_reset_mdp(self, nom_utilisateur: str) -> tuple[bool, str | None, str | None]:
        user = user_model.obtenir_utilisateur_par_login_data(nom_utilisateur)
        if not user or not user.email:
            return False, None, "Utilisateur non trouvé ou email non configuré."

        from utils import email_utils
        code_reset = ''.join(random.choices(string.digits, k=6))
        expiry_time = datetime.datetime.now() + datetime.timedelta(minutes=5)
        self.reset_codes[nom_utilisateur] = (code_reset, expiry_time)

        if email_utils.envoyer_email_reset(user.email, nom_utilisateur, code_reset):
            return True, user.email, None
        else:
            print(f"Échec de l'envoi de l'email. Code pour {nom_utilisateur}: {code_reset}")
            return False, user.email, f"L'envoi de l'email a échoué. Code pour test: {code_reset}"

    def verifier_code_et_reinitialiser_mdp(self, nom_utilisateur: str, code_saisi: str, nouveau_mdp: str) -> tuple[
        bool, str | None]:
        if nom_utilisateur not in self.reset_codes:
            return False, "Aucune demande de réinitialisation en cours pour cet utilisateur."

        stored_code, expiry_time = self.reset_codes[nom_utilisateur]

        if datetime.datetime.now() > expiry_time:
            del self.reset_codes[nom_utilisateur]
            return False, "Le code de réinitialisation a expiré."

        if code_saisi == stored_code:
            update_data = UtilisateurUpdate(password=nouveau_mdp)
            success, _ = user_model.mettre_a_jour_utilisateur_data(nom_utilisateur, update_data)
            del self.reset_codes[nom_utilisateur]
            if success:
                return True, "Mot de passe réinitialisé avec succès."
            else:
                return False, "Erreur lors de la mise à jour du mot de passe."
        else:
            return False, "Code de réinitialisation invalide."

    def get_user_data(self, login: str):
        return user_model.obtenir_utilisateur_par_login_data(login)

    def get_all_users(self):
        return user_model.obtenir_tous_les_utilisateurs_data()

    def update_user_profile(self, login: str, new_email: str, old_password: str | None, new_password: str | None,
                            preferences: dict, cache_manager: CacheManager) -> tuple[bool, str]:
        user = user_model.obtenir_utilisateur_par_login_data(login)
        if not user:
            return False, "Utilisateur non trouvé."

        if new_password:
            if not old_password or not password_utils.verifier_mdp(old_password, user.hashed_password):
                return False, "L'ancien mot de passe est incorrect."

        old_pfp_path = user.profile_picture_path
        new_pfp_path = preferences.get("profile_picture_path")

        pfp_changed = old_pfp_path != new_pfp_path

        if old_pfp_path and pfp_changed:
            try:
                full_old_path = os.path.join(PROFILE_PICTURES_DIR, old_pfp_path)
                if os.path.exists(full_old_path):
                    os.remove(full_old_path)
            except OSError as e:
                _log.error(f"Erreur lors de la suppression de l'ancienne photo de profil : {e}", exc_info=True)

        update_data = UtilisateurUpdate(
            email=new_email,
            password=new_password if new_password else None,
            theme_color=preferences.get("theme_color"),
            default_filter=preferences.get("default_filter"),
            profile_picture_path=new_pfp_path
        )
        success, message = user_model.mettre_a_jour_utilisateur_data(login, update_data)

        if success and pfp_changed:
            cache_manager.invalidate_pfp_cache(login)

        return success, message

    def remove_user_profile_picture(self, login: str, cache_manager: CacheManager) -> tuple[bool, str]:
        user = user_model.obtenir_utilisateur_par_login_data(login)
        if not user:
            return False, "Utilisateur non trouvé."

        old_pfp_path = user.profile_picture_path
        if old_pfp_path:
            try:
                full_old_path = os.path.join(PROFILE_PICTURES_DIR, old_pfp_path)
                if os.path.exists(full_old_path):
                    os.remove(full_old_path)
            except OSError as e:
                return False, f"Erreur lors de la suppression du fichier image : {e}"

        update_data = UtilisateurUpdate(profile_picture_path="")
        success, message = user_model.mettre_a_jour_utilisateur_data(login, update_data)

        if success:
            cache_manager.invalidate_pfp_cache(login)

        return success, message

    def get_all_users_for_management(self) -> list[dict]:
        tous_les_utilisateurs = user_model.obtenir_tous_les_utilisateurs_data()
        liste_utilisateurs = []
        for user in tous_les_utilisateurs:
            if user.login != "admin":
                user_info = {
                    "login": user.login,
                    "email": user.email or "N/A",
                    "roles": user.roles
                }
                liste_utilisateurs.append(user_info)
        return sorted(liste_utilisateurs, key=lambda u: u["login"])

    def admin_delete_user(self, nom_utilisateur_a_supprimer: str) -> tuple[bool, str]:
        if nom_utilisateur_a_supprimer == "admin":
            return False, "Le compte administrateur principal 'admin' ne peut pas être supprimé."
        return user_model.supprimer_utilisateur_data(nom_utilisateur_a_supprimer)

    def admin_create_user(self, login: str, email: str, mot_de_passe: str, roles: list[str]) -> tuple[bool, str]:
        if not all([login, email, mot_de_passe]):
            return False, "Login, email et mot de passe sont requis."
        if not login.strip() or not email.strip() or not mot_de_passe.strip():
            return False, "Login, email et mot de passe ne peuvent pas être vides."
        if login == "admin":
            return False, "Le login 'admin' est réservé."

        new_user = Utilisateur(
            login=login,
            hashed_password=password_utils.generer_hachage_mdp(mot_de_passe),
            email=email,
            roles=sorted(list(set(role for role in roles if role in ASSIGNABLE_ROLES)))
        )
        return user_model.ajouter_utilisateur_data(new_user)

    def admin_update_user_details(self, login_original: str, nouveau_login: str, new_email: str, new_roles: list[str],
                                  nouveau_mot_de_passe: str | None) -> tuple[bool, str]:
        if login_original != nouveau_login:
            return False, "Le changement de login n'est pas supporté. Supprimez et recréez l'utilisateur si nécessaire."

        if not all([login_original, new_email]):
            return False, "Login et email sont requis."

        if login_original == "admin" and "admin" not in new_roles:
            new_roles.append("admin")

        valid_roles = sorted(list(set(role for role in new_roles if role in ASSIGNABLE_ROLES or role == "admin")))

        update_data = UtilisateurUpdate(
            email=new_email,
            roles=valid_roles,
            password=nouveau_mot_de_passe if nouveau_mot_de_passe else None
        )
        return user_model.mettre_a_jour_utilisateur_data(login_original, update_data)

    def get_role_descriptions_with_users(self) -> dict:
        descriptions = ROLES_UTILISATEURS.copy()
        tous_utilisateurs = user_model.obtenir_tous_les_utilisateurs_data()

        for role_key in descriptions:
            descriptions[role_key]["utilisateurs_actuels"] = []

        for user in tous_utilisateurs:
            for role in user.roles:
                if role in descriptions:
                    descriptions[role]["utilisateurs_actuels"].append(user.login)

        for role_key in descriptions:
            descriptions[role_key]["utilisateurs_actuels"] = sorted(
                list(set(descriptions[role_key]["utilisateurs_actuels"])))

        return descriptions

    def get_assignable_roles(self) -> list[str]:
        return ASSIGNABLE_ROLES

    def get_smtp_config(self) -> dict:
        load_smtp_config()
        return SMTP_CONFIG.copy()

    def save_smtp_config(self, new_config_data: dict) -> tuple[bool, str]:
        return save_email_config_to_ini(new_config_data)

    def test_smtp_connection(self, config_to_test: dict) -> tuple[bool, str]:
        try:
            if config_to_test.get('use_ssl'):
                server = smtplib.SMTP_SSL(config_to_test['server'], int(config_to_test['port']), timeout=10)
            else:
                server = smtplib.SMTP(config_to_test['server'], int(config_to_test['port']), timeout=10)
                if config_to_test.get('use_tls'):
                    server.starttls()

            server.login(config_to_test['email_sender'], config_to_test['password'])
            server.quit()
            return True, "Connexion réussie."
        except Exception as e:
            return False, str(e)

    def run_database_health_check(self) -> tuple[bool, str]:
        """Exécute PRAGMA integrity_check sur la BDD."""
        _log.info("Lancement du Health Check de la base de données...")
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            conn.close()
            if result[0] == "ok":
                _log.info("Health Check de la base de données : OK.")
                return True, "ok"
            else:
                _log.critical(f"Health Check de la base de données a échoué ! Résultat : {result[0]}")
                return False, f"La base de données pourrait être corrompue. Résultat : {result[0]}"
        except Exception as e:
            _log.critical("Erreur critique pendant le Health Check de la BDD.", exc_info=True)
            return False, str(e)

    def run_automatic_backup(self) -> str:
        """Crée une sauvegarde journalière si nécessaire et nettoie les anciennes."""
        try:
            backups, err = self.get_database_backups()
            if err:
                return f"Erreur lors de la récupération des sauvegardes : {err}"

            today_str = datetime.datetime.now().strftime("%Y-%m-%d")
            if any(f"backup_{today_str}" in backup_file for backup_file in backups):
                _log.info("Sauvegarde automatique déjà effectuée aujourd'hui.")
                return "Sauvegarde automatique déjà effectuée aujourd'hui."

            _log.info("Aucune sauvegarde automatique pour aujourd'hui. Création en cours...")
            success, msg = self.admin_backup_database(is_auto=True)
            if success:
                self.admin_cleanup_old_backups()
                return "Sauvegarde automatique créée."
            else:
                return f"Échec de la sauvegarde automatique : {msg}"
        except Exception as e:
            _log.error("Erreur dans le processus de sauvegarde automatique.", exc_info=True)
            return f"Erreur lors de la sauvegarde auto : {e}"

    def admin_backup_database(self, is_auto: bool = False) -> tuple[bool, str]:
        if not os.path.exists(DATABASE_FILE):
            return False, "Fichier de base de données introuvable."
        try:
            prefix = "auto_backup" if is_auto else "manual_backup"
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_filename = f"remboursements_{prefix}_{timestamp}.db"
            backup_filepath = os.path.join(SHARED_DATA_BASE_PATH, backup_filename)
            shutil.copy2(DATABASE_FILE, backup_filepath)
            return True, f"Sauvegarde créée avec succès : {backup_filename}"
        except Exception as e:
            return False, f"Erreur lors de la création de la sauvegarde : {e}"

    def get_database_backups(self) -> tuple[list[str], str | None]:
        try:
            files = os.listdir(SHARED_DATA_BASE_PATH)
            backup_files = [f for f in files if f.startswith("remboursements_") and f.endswith(".db")]
            return sorted(backup_files, reverse=True), None
        except Exception as e:
            return [], f"Erreur lors de la lecture des sauvegardes : {e}"

    def admin_restore_database(self, backup_filename: str) -> tuple[bool, str]:
        backup_filepath = os.path.join(SHARED_DATA_BASE_PATH, backup_filename)
        if not os.path.exists(backup_filepath):
            return False, "Le fichier de sauvegarde sélectionné n'existe pas."

        try:
            safe_rename_path = f"{DATABASE_FILE}.before_restore_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
            if os.path.exists(DATABASE_FILE):
                os.rename(DATABASE_FILE, safe_rename_path)

            shutil.copy2(backup_filepath, DATABASE_FILE)
            return True, "Restauration terminée. L'application va redémarrer."
        except Exception as e:
            if 'safe_rename_path' in locals() and os.path.exists(safe_rename_path):
                os.rename(safe_rename_path, DATABASE_FILE)
            return False, f"Erreur critique lors de la restauration : {e}"

    def admin_delete_backup(self, backup_filename: str) -> tuple[bool, str]:
        backup_filepath = os.path.join(SHARED_DATA_BASE_PATH, backup_filename)
        if not os.path.exists(backup_filepath):
            return False, "Le fichier de sauvegarde à supprimer n'existe plus."
        try:
            os.remove(backup_filepath)
            return True, f"La sauvegarde '{backup_filename}' a été supprimée."
        except OSError as e:
            return False, f"Erreur système lors de la suppression du fichier : {e}"

    def admin_cleanup_old_backups(self, keep_count: int = 7) -> str:
        """Conserve les 'keep_count' sauvegardes automatiques les plus récentes et supprime les autres."""
        try:
            all_backups, err = self.get_database_backups()
            if err:
                return f"Erreur: {err}"

            auto_backups = sorted([b for b in all_backups if b.startswith("remboursements_auto_backup_")], reverse=True)

            if len(auto_backups) > keep_count:
                to_delete = auto_backups[keep_count:]
                deleted_count = 0
                for backup_file in to_delete:
                    success, msg = self.admin_delete_backup(backup_file)
                    if success:
                        deleted_count += 1
                    else:
                        _log.warning(f"Impossible de supprimer l'ancienne sauvegarde {backup_file}: {msg}")
                return f"{deleted_count} ancienne(s) sauvegarde(s) automatique(s) supprimée(s)."
            return "Aucune ancienne sauvegarde automatique à supprimer."
        except Exception as e:
            _log.error("Erreur lors du nettoyage des anciennes sauvegardes.", exc_info=True)
            return f"Erreur lors du nettoyage: {e}"

    def admin_cleanup_restore_files(self) -> tuple[bool, str]:
        count = 0
        try:
            files = os.listdir(SHARED_DATA_BASE_PATH)
            for file in files:
                if file.startswith("remboursements.db.before_restore_"):
                    os.remove(os.path.join(SHARED_DATA_BASE_PATH, file))
                    count += 1
            if count > 0:
                return True, f"{count} fichier(s) de restauration temporaire ont été nettoyés."
            else:
                return True, "Aucun fichier de restauration temporaire à nettoyer."
        except OSError as e:
            return False, f"Erreur système lors du nettoyage : {e}"