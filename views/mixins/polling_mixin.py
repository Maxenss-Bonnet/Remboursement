import os
import time
import logging
from config.settings import DATABASE_FILE
from utils.database_manager import DB_REFRESH_FLAG_FILE

_log = logging.getLogger(__name__)

# AMÉLIORATION : Intervalles de polling plus agressifs pour une meilleure réactivité
POLLING_INTERVAL_MS_ACTIVE = 1500  # <- Réduit de 5000ms à 1500ms
POLLING_INTERVAL_MS_IDLE = 30000
IDLE_THRESHOLD_SECONDS = 120
FLAG_MAX_AGE_SECONDS = 20


class PollingMixin:
    def __init__(self):
        self._polling_job_id = None
        # AMÉLIORATION : Renommé pour plus de clarté, stocke le timestamp du dernier drapeau traité
        self._last_processed_flag_timestamp = 0
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
            # AMÉLIORATION : La logique se concentre sur le fichier drapeau pour la réactivité
            # La vérification du fichier de BDD principal devient une sécurité secondaire.
            refresh_triggered_by_flag = False

            if os.path.exists(DB_REFRESH_FLAG_FILE):
                try:
                    # Lire le timestamp du drapeau
                    with open(DB_REFRESH_FLAG_FILE, 'r') as f:
                        flag_timestamp_str = f.read()
                    flag_timestamp = float(flag_timestamp_str)

                    # Rafraîchir seulement si ce drapeau est plus récent que le dernier qu'on a traité
                    if flag_timestamp > self._last_processed_flag_timestamp:
                        _log.info(
                            f"Nouveau signal de rafraîchissement détecté (ts: {flag_timestamp}). Lancement du rafraîchissement.")
                        if hasattr(self, 'afficher_liste_demandes'):
                            self.afficher_liste_demandes(force_refresh=True, show_loader=False)

                        # Mémoriser le timestamp de ce drapeau pour ne pas rafraîchir à nouveau pour le même signal
                        self._last_processed_flag_timestamp = flag_timestamp
                        refresh_triggered_by_flag = True

                    # Nettoyage du fichier drapeau s'il est trop vieux (laissé par une app qui a planté par exemple)
                    if time.time() - flag_timestamp > FLAG_MAX_AGE_SECONDS:
                        _log.info(
                            f"Nettoyage du signal de rafraîchissement obsolète (âge: {time.time() - flag_timestamp:.2f}s).")
                        os.remove(DB_REFRESH_FLAG_FILE)

                except (IOError, OSError, ValueError) as e:
                    _log.warning(
                        f"Impossible de lire ou de supprimer le fichier drapeau : {e}. Tentative de nettoyage.")
                    try:
                        os.remove(DB_REFRESH_FLAG_FILE)
                    except OSError:
                        pass

            # Fallback : si aucun drapeau n'a été traité, vérifier la date de modification de la BDD
            # C'est une sécurité si le mécanisme de drapeau échoue.
            if not refresh_triggered_by_flag:
                if os.path.exists(DATABASE_FILE):
                    current_mtime = os.path.getmtime(DATABASE_FILE)
                    if self._last_processed_flag_timestamp == 0:
                        self._last_processed_flag_timestamp = current_mtime
                    # On utilise mtime comme un timestamp de drapeau s'il est plus récent
                    elif current_mtime > self._last_processed_flag_timestamp:
                        _log.info("Changement détecté sur le fichier BDD (mtime). Rafraîchissement de la liste.")
                        if hasattr(self, 'afficher_liste_demandes'):
                            self.afficher_liste_demandes(force_refresh=True, show_loader=False)
                        self._last_processed_flag_timestamp = current_mtime

            # Logique pour ajuster l'intervalle de polling (actif/inactif)
            idle_time = time.time() - self.last_user_interaction_time
            next_poll_interval = POLLING_INTERVAL_MS_IDLE if idle_time > IDLE_THRESHOLD_SECONDS else POLLING_INTERVAL_MS_ACTIVE

            self._polling_job_id = self.after(next_poll_interval, self._check_for_data_updates)

        except Exception as e:
            _log.error(f"Erreur lors du polling de la base de données : {e}", exc_info=True)
            if self.winfo_exists():
                self._polling_job_id = self.after(POLLING_INTERVAL_MS_IDLE, self._check_for_data_updates)