import os
import time
import threading
import logging
from config.settings import SHARED_DATA_BASE_PATH, IS_DEPLOYMENT_MODE
from utils.global_events import network_status_queue

_log = logging.getLogger(__name__)


def is_path_accessible(path: str) -> bool:
    """Vérifie si le chemin est accessible en lecture/écriture."""
    if not IS_DEPLOYMENT_MODE:
        return True
    try:
        if not os.path.isdir(path):
            return False
        # Test d'écriture simple pour valider la connexion
        test_file = os.path.join(path, f"connection_test_{os.getpid()}.tmp")
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except (IOError, OSError, PermissionError):
        return False


class NetworkMonitor:
    def __init__(self, check_interval_seconds: int = 5):
        self._interval = check_interval_seconds
        self._thread = None
        self._stop_event = threading.Event()
        self._is_connected = True

    def start(self):
        """Démarre le thread de surveillance du réseau."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="NetworkMonitorThread")
            self._thread.start()
            _log.info("Moniteur de connexion réseau démarré.")

    def stop(self):
        """Arrête le thread de surveillance."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        _log.info("Moniteur de connexion réseau arrêté.")

    def _monitor_loop(self):
        """Boucle principale de vérification de la connexion."""
        while not self._stop_event.is_set():
            current_status = is_path_accessible(SHARED_DATA_BASE_PATH)

            if current_status != self._is_connected:
                self._is_connected = current_status
                status_str = "RECONNECTED" if self._is_connected else "DISCONNECTED"
                _log.info(f"Changement d'état de la connexion réseau détecté : {status_str}")
                network_status_queue.put(self._is_connected)

            time.sleep(self._interval)