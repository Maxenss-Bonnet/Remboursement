import os
import time
import logging
import threading
from config.settings import DATABASE_FILE
from utils.database_manager import DB_REFRESH_FLAG_FILE

_log = logging.getLogger(__name__)

POLLING_INTERVAL_MS_ACTIVE = 1500
POLLING_INTERVAL_MS_IDLE = 30000
IDLE_THRESHOLD_SECONDS = 120
FLAG_MAX_AGE_SECONDS = 20


class PollingMixin:
    def __init__(self):
        self._polling_job_id = None
        self._last_processed_flag_timestamp = 0
        self.last_user_interaction_time = time.time()
        self._mtime_check_thread = None

    def _reset_idle_timer(self, event=None):
        self.last_user_interaction_time = time.time()

    def start_polling(self):
        self.stop_polling()
        self.after(500, self._check_for_data_updates)

    def stop_polling(self):
        if self._polling_job_id:
            try:
                self.after_cancel(self._polling_job_id)
            except ValueError:
                pass
            self._polling_job_id = None
        if self._mtime_check_thread and self._mtime_check_thread.is_alive():
            # Il n'est pas critique d'attendre la fin de ce thread
            pass

    def _check_for_data_updates(self):
        try:
            refresh_triggered_by_flag = self._check_flag_file()

            # CORRECTION : La vérification de la BDD est maintenant asynchrone pour ne pas freezer l'UI
            if not refresh_triggered_by_flag:
                # On lance la vérification en arrière-plan uniquement si un précédent n'est pas déjà en cours
                if self._mtime_check_thread is None or not self._mtime_check_thread.is_alive():
                    self._mtime_check_thread = threading.Thread(target=self._check_db_mtime_async, daemon=True)
                    self._mtime_check_thread.start()

            idle_time = time.time() - self.last_user_interaction_time
            next_poll_interval = POLLING_INTERVAL_MS_IDLE if idle_time > IDLE_THRESHOLD_SECONDS else POLLING_INTERVAL_MS_ACTIVE
            self._polling_job_id = self.after(next_poll_interval, self._check_for_data_updates)

        except Exception as e:
            _log.error(f"Erreur lors du polling : {e}", exc_info=True)
            if self.winfo_exists():
                self._polling_job_id = self.after(POLLING_INTERVAL_MS_IDLE, self._check_for_data_updates)

    def _check_flag_file(self) -> bool:
        """Vérifie le fichier drapeau et déclenche le rafraîchissement si nécessaire. Renvoie True si un rafraîchissement a été déclenché."""
        if os.path.exists(DB_REFRESH_FLAG_FILE):
            try:
                with open(DB_REFRESH_FLAG_FILE, 'r') as f:
                    flag_timestamp = float(f.read())

                if flag_timestamp > self._last_processed_flag_timestamp:
                    _log.info(f"Signal de rafraîchissement (drapeau) détecté (ts: {flag_timestamp}).")
                    if hasattr(self, 'afficher_liste_demandes'):
                        self.afficher_liste_demandes(force_refresh=True, show_loader=False)
                    self._last_processed_flag_timestamp = flag_timestamp
                    return True

                if time.time() - flag_timestamp > FLAG_MAX_AGE_SECONDS:
                    _log.info(f"Nettoyage du signal de rafraîchissement drapeau obsolète.")
                    os.remove(DB_REFRESH_FLAG_FILE)

            except (IOError, OSError, ValueError) as e:
                _log.warning(f"Impossible de traiter le fichier drapeau : {e}. Tentative de nettoyage.")
                try:
                    os.remove(DB_REFRESH_FLAG_FILE)
                except OSError:
                    pass
        return False

    def _check_db_mtime_async(self):
        """Vérifie la date de modification de la BDD dans un thread séparé."""
        try:
            if os.path.exists(DATABASE_FILE):
                current_mtime = os.path.getmtime(DATABASE_FILE)
                if self._last_processed_flag_timestamp == 0:
                    self._last_processed_flag_timestamp = current_mtime
                elif current_mtime > self._last_processed_flag_timestamp:
                    _log.info("Changement détecté sur le fichier BDD (mtime). Rafraîchissement.")
                    if hasattr(self, 'afficher_liste_demandes') and self.winfo_exists():
                        # On demande au thread UI de lancer le rafraîchissement
                        self.after(0, lambda: self.afficher_liste_demandes(force_refresh=True, show_loader=False))
                    self._last_processed_flag_timestamp = current_mtime
        except (OSError, IOError) as e:
            # Erreur normale si le disque est déconnecté, on ne log que si c'est inattendu.
            _log.debug(f"Erreur d'accès à la BDD pour mtime check (attendu si déconnecté): {e}")
        except Exception as e:
            _log.error(f"Erreur inattendue lors de la vérification de mtime BDD: {e}", exc_info=True)