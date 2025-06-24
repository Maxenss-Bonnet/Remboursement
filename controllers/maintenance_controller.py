import smtplib
import os
import datetime
import shutil
import logging
from config.settings import (
    save_email_config_to_ini,
    SMTP_CONFIG,
    load_smtp_config,
    DATABASE_FILE,
    SHARED_DATA_BASE_PATH
)
from utils.database_manager import get_db_connection
from models import remboursement_data

_log = logging.getLogger(__name__)


class MaintenanceController:
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

    def optimiser_base_de_donnees_data(self) -> tuple[bool, str]:
        return remboursement_data.optimiser_base_de_donnees_data()