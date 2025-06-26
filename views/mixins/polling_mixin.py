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
            pass

    def _check_for_data_updates(self):
        """
        Planifie périodiquement une vérification en arrière-plan des mises à jour des données.
        La vérification réelle est effectuée dans un thread séparé pour éviter de geler l'interface utilisateur.
        """
        try:
            idle_time = time.time() - self.last_user_interaction_time
            next_poll_interval = POLLING_INTERVAL_MS_IDLE if idle_time > IDLE_THRESHOLD_SECONDS else POLLING_INTERVAL_MS_ACTIVE

            if self._mtime_check_thread is None or not self._mtime_check_thread.is_alive():
                self._mtime_check_thread = threading.Thread(target=self._background_update_check, daemon=True, name="UpdateCheckThread")
                self._mtime_check_thread.start()

            self._polling_job_id = self.after(next_poll_interval, self._check_for_data_updates)

        except Exception as e:
            _log.error(f"Erreur dans le planificateur de polling : {e}", exc_info=True)
            if self.winfo_exists():
                self._polling_job_id = self.after(POLLING_INTERVAL_MS_IDLE, self._check_for_data_updates)

    def _background_update_check(self):
        """
        Effectue les vérifications du système de fichiers (fichier drapeau, heure de modification de la BDD) en arrière-plan.
        Si une mise à jour est nécessaire, elle planifie le rafraîchissement de l'interface utilisateur sur le thread principal.
        """
        try:
            # 1. Vérifier d'abord le fichier drapeau de rafraîchissement (signal prioritaire)
            if os.path.exists(DB_REFRESH_FLAG_FILE):
                try:
                    with open(DB_REFRESH_FLAG_FILE, 'r') as f:
                        flag_timestamp = float(f.read())

                    if time.time() - flag_timestamp > FLAG_MAX_AGE_SECONDS:
                        os.remove(DB_REFRESH_FLAG_FILE)

                    elif flag_timestamp > self._last_processed_flag_timestamp:
                        _log.info(f"Signal de rafraîchissement (drapeau) détecté (ts: {flag_timestamp}).")
                        self._last_processed_flag_timestamp = flag_timestamp
                        if hasattr(self, 'afficher_liste_demandes') and self.winfo_exists():
                            self.after(0, lambda: self.afficher_liste_demandes(force_refresh=True, show_loader=False))
                        return  # Rafraîchissement déclenché, inutile de vérifier mtime

                except (IOError, OSError, ValueError):
                    try:
                        os.remove(DB_REFRESH_FLAG_FILE)
                    except OSError:
                        pass

            # 2. Si aucun drapeau, vérifier l'heure de modification du fichier de la base de données
            if os.path.exists(DATABASE_FILE):
                current_mtime = os.path.getmtime(DATABASE_FILE)
                if self._last_processed_flag_timestamp == 0:  # Première exécution
                    self._last_processed_flag_timestamp = current_mtime
                elif current_mtime > self._last_processed_flag_timestamp:
                    _log.info("Changement détecté sur le fichier BDD (mtime). Rafraîchissement.")
                    self._last_processed_flag_timestamp = current_mtime
                    if hasattr(self, 'afficher_liste_demandes') and self.winfo_exists():
                        self.after(0, lambda: self.afficher_liste_demandes(force_refresh=True, show_loader=False))

        except (OSError, IOError) as e:
            _log.debug(f"Erreur d'accès réseau pendant la vérification en arrière-plan (attendu si déconnecté): {e}")
        except Exception as e:
            _log.error(f"Erreur inattendue dans _background_update_check: {e}", exc_info=True)