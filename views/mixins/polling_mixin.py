import os
import time
import logging
from config.settings import DATABASE_FILE

_log = logging.getLogger(__name__)

POLLING_INTERVAL_MS_ACTIVE = 5000
POLLING_INTERVAL_MS_IDLE = 30000
IDLE_THRESHOLD_SECONDS = 120


class PollingMixin:
    def __init__(self):
        self._polling_job_id = None
        self._last_known_db_mtime = 0
        self.last_user_interaction_time = time.time()

    def _reset_idle_timer(self, event=None):
        self.last_user_interaction_time = time.time()

    def start_polling(self):
        self.stop_polling()
        # Démarrer le polling après un court délai pour laisser l'interface se charger
        self.after(500, self._check_for_data_updates)

    def stop_polling(self):
        if self._polling_job_id:
            try:
                self.after_cancel(self._polling_job_id)
            except ValueError:
                # Peut arriver si le job est déjà annulé ou n'existe plus
                pass
            self._polling_job_id = None

    def _check_for_data_updates(self):
        try:
            # Vérifier la date de modification du fichier de la base de données
            current_mtime = os.path.getmtime(DATABASE_FILE) if os.path.exists(DATABASE_FILE) else 0

            if self._last_known_db_mtime == 0:
                self._last_known_db_mtime = current_mtime
            elif current_mtime != self._last_known_db_mtime:
                _log.info("Changement détecté sur le fichier de BDD. Rafraîchissement de la liste.")
                self._last_known_db_mtime = current_mtime
                if hasattr(self, 'afficher_liste_demandes'):
                    self.afficher_liste_demandes(force_refresh=True)

            # Adapter l'intervalle de polling en fonction de l'inactivité de l'utilisateur
            idle_time = time.time() - self.last_user_interaction_time
            next_poll_interval = POLLING_INTERVAL_MS_IDLE if idle_time > IDLE_THRESHOLD_SECONDS else POLLING_INTERVAL_MS_ACTIVE

            self._polling_job_id = self.after(next_poll_interval, self._check_for_data_updates)
        except Exception as e:
            _log.error(f"Erreur lors du polling de la base de données : {e}")
            # En cas d'erreur, on retente avec l'intervalle long
            if self.winfo_exists():
                self._polling_job_id = self.after(POLLING_INTERVAL_MS_IDLE, self._check_for_data_updates)