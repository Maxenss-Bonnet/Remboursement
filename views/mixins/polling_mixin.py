import os
import time
import logging
import threading
from tkinter import TclError

from config.settings import DATABASE_FILE, DB_REFRESH_FLAG_FILE
from utils.network_monitor import is_path_accessible

_log = logging.getLogger(__name__)

POLLING_INTERVAL_MS_ACTIVE = 2500
POLLING_INTERVAL_MS_IDLE = 30000
IDLE_THRESHOLD_SECONDS = 120


class PollingMixin:
    def __init__(self):
        self._polling_job_id = None
        self._last_processed_db_mtime = 0
        self.last_user_interaction_time = time.time()
        self._update_check_thread = None
        self._stop_polling_event = threading.Event()

    def _reset_idle_timer(self, event=None):
        self.last_user_interaction_time = time.time()

    def start_polling(self):
        self.stop_polling()
        self._stop_polling_event.clear()
        self.after(500, self._poll_scheduler)

    def stop_polling(self):
        self._stop_polling_event.set()
        if self._polling_job_id:
            try:
                self.after_cancel(self._polling_job_id)
            except (ValueError, TclError):
                pass
            self._polling_job_id = None
        if self._update_check_thread and self._update_check_thread.is_alive():
            self._update_check_thread.join(timeout=0.5)

    def _poll_scheduler(self):
        """Planifie la prochaine vérification en arrière-plan."""
        if self._stop_polling_event.is_set():
            return

        try:
            if self._update_check_thread is None or not self._update_check_thread.is_alive():
                self._update_check_thread = threading.Thread(target=self._background_update_check, daemon=True)
                self._update_check_thread.start()

            idle_time = time.time() - self.last_user_interaction_time
            next_poll_interval = POLLING_INTERVAL_MS_IDLE if idle_time > IDLE_THRESHOLD_SECONDS else POLLING_INTERVAL_MS_ACTIVE
            self._polling_job_id = self.after(next_poll_interval, self._poll_scheduler)
        except Exception as e:
            _log.error(f"Erreur dans le planificateur de polling : {e}", exc_info=True)
            if self.winfo_exists() and not self._stop_polling_event.is_set():
                 self._polling_job_id = self.after(POLLING_INTERVAL_MS_IDLE, self._poll_scheduler)

    def _background_update_check(self):
        """Effectue les vérifications I/O dans un thread séparé pour ne pas bloquer l'UI."""
        try:
            # On vérifie d'abord si le chemin principal est accessible avant toute opération
            if not is_path_accessible(os.path.dirname(DATABASE_FILE)):
                return

            # Vérification du fichier drapeau (flag file)
            if os.path.exists(DB_REFRESH_FLAG_FILE):
                try:
                    with open(DB_REFRESH_FLAG_FILE, 'r') as f:
                        flag_timestamp = float(f.read())
                    os.remove(DB_REFRESH_FLAG_FILE)
                    _log.info(f"Signal de rafraîchissement (drapeau) détecté. Rafraîchissement demandé.")
                    if self.winfo_exists(): self.after(0, self._trigger_ui_refresh)
                    return
                except (IOError, OSError, ValueError):
                    pass

            # Vérification de la date de modification de la BDD
            current_mtime = os.path.getmtime(DATABASE_FILE)
            if self._last_processed_db_mtime == 0:
                self._last_processed_db_mtime = current_mtime
            elif current_mtime > self._last_processed_db_mtime:
                _log.info("Changement détecté sur le fichier BDD (mtime). Rafraîchissement demandé.")
                self._last_processed_db_mtime = current_mtime
                if self.winfo_exists(): self.after(0, self._trigger_ui_refresh)

        except (OSError, IOError):
            _log.debug(f"Erreur d'accès réseau durant le polling (attendu si déconnecté).")
        except Exception as e:
            _log.error(f"Erreur inattendue dans le thread de polling: {e}", exc_info=True)

    def _trigger_ui_refresh(self):
        """Appelle la fonction de rafraîchissement de manière sûre depuis le thread UI."""
        if hasattr(self, 'afficher_liste_demandes') and self.winfo_exists():
            self.afficher_liste_demandes(force_refresh=True, show_loader=False)