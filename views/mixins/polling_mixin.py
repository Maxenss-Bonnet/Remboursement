import os
import time
import logging
from config.settings import DATABASE_FILE
from utils.database_manager import DB_REFRESH_FLAG_FILE

_log = logging.getLogger(__name__)

POLLING_INTERVAL_MS_ACTIVE = 5000
POLLING_INTERVAL_MS_IDLE = 30000
IDLE_THRESHOLD_SECONDS = 120
FLAG_MAX_AGE_SECONDS = 20


class PollingMixin:
    def __init__(self):
        self._polling_job_id = None
        self._last_known_db_mtime = 0
        self.last_user_interaction_time = time.time()

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

    def _check_for_data_updates(self):
        try:
            refresh_triggered = False

            if os.path.exists(DB_REFRESH_FLAG_FILE):
                try:
                    with open(DB_REFRESH_FLAG_FILE, 'r') as f:
                        flag_timestamp_str = f.read()

                    flag_timestamp = float(flag_timestamp_str)

                    if flag_timestamp > self._last_known_db_mtime:
                        _log.info(
                            f"Signal de rafraîchissement (.flag) détecté à {flag_timestamp}. Lancement du rafraîchissement.")
                        if hasattr(self, 'afficher_liste_demandes'):
                            self.afficher_liste_demandes(force_refresh=True, show_loader=False)

                        self._last_known_db_mtime = flag_timestamp
                        refresh_triggered = True

                    if time.time() - flag_timestamp > FLAG_MAX_AGE_SECONDS:
                        _log.info(
                            f"Nettoyage du signal de rafraîchissement (.flag) obsolète (âge: {time.time() - flag_timestamp:.2f}s).")
                        os.remove(DB_REFRESH_FLAG_FILE)

                except (IOError, OSError, ValueError) as e:
                    _log.warning(f"Impossible de lire ou de supprimer le fichier .flag : {e}")
                    try:
                        os.remove(DB_REFRESH_FLAG_FILE)
                    except OSError:
                        pass

            if not refresh_triggered:
                current_mtime = os.path.getmtime(DATABASE_FILE) if os.path.exists(DATABASE_FILE) else 0
                if self._last_known_db_mtime == 0:
                    self._last_known_db_mtime = current_mtime
                elif current_mtime > self._last_known_db_mtime:
                    _log.info("Changement détecté sur le fichier de BDD (mtime). Rafraîchissement de la liste.")
                    self._last_known_db_mtime = current_mtime
                    if hasattr(self, 'afficher_liste_demandes'):
                        self.afficher_liste_demandes(force_refresh=True, show_loader=False)

            idle_time = time.time() - self.last_user_interaction_time
            next_poll_interval = POLLING_INTERVAL_MS_IDLE if idle_time > IDLE_THRESHOLD_SECONDS else POLLING_INTERVAL_MS_ACTIVE

            self._polling_job_id = self.after(next_poll_interval, self._check_for_data_updates)

        except Exception as e:
            _log.error(f"Erreur lors du polling de la base de données : {e}", exc_info=True)
            if self.winfo_exists():
                self._polling_job_id = self.after(POLLING_INTERVAL_MS_IDLE, self._check_for_data_updates)