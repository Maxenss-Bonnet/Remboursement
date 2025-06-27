import os
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from config.settings import SHARED_DATA_BASE_PATH, IS_DEPLOYMENT_MODE
from utils.global_events import network_status_queue

_log = logging.getLogger(__name__)

FAILURE_THRESHOLD = 4
CHECK_INTERVAL_SECONDS = 3.0
ACCESS_TIMEOUT_SECONDS = 2.5


def is_path_accessible(path: str) -> bool:
    """
    Vérifie l'accès à un chemin réseau de manière non-bloquante avec un timeout.
    Utilise os.path.exists qui est plus léger que os.listdir.
    """
    if not IS_DEPLOYMENT_MODE:
        return True

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(os.path.exists, path)
    try:
        return future.result(timeout=ACCESS_TIMEOUT_SECONDS)
    except (TimeoutError, IOError, OSError, PermissionError):
        return False
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


class NetworkMonitor:
    def __init__(self):
        self._interval = CHECK_INTERVAL_SECONDS
        self._thread = None
        self._stop_event = threading.Event()
        self._is_connected = True
        self._consecutive_failures = 0

    def start(self):
        """Démarre le thread de surveillance du réseau."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._is_connected = is_path_accessible(SHARED_DATA_BASE_PATH)
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="NetworkMonitorThread")
            self._thread.start()
            _log.info(f"Moniteur réseau démarré (intervalle: {self._interval}s, seuil: {FAILURE_THRESHOLD} échecs).")

    def stop(self):
        """Arrête le thread de surveillance."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        _log.info("Moniteur réseau arrêté.")

    def _monitor_loop(self):
        """Boucle principale de vérification de la connexion."""
        while not self._stop_event.is_set():
            current_status = is_path_accessible(SHARED_DATA_BASE_PATH)

            if current_status:
                self._consecutive_failures = 0
                if not self._is_connected:
                    self._is_connected = True
                    _log.info("Réseau détecté : RECONNECTÉ")
                    network_status_queue.put(True)
            else:
                self._consecutive_failures += 1
                if self._is_connected and self._consecutive_failures >= FAILURE_THRESHOLD:
                    self._is_connected = False
                    _log.warning(f"Réseau non détecté : DÉCONNECTÉ (après {self._consecutive_failures} échecs)")
                    network_status_queue.put(False)

            # Attente intelligente : si déconnecté, vérifie plus fréquemment.
            sleep_interval = 0.75 if not self._is_connected else self._interval
            self._stop_event.wait(sleep_interval)