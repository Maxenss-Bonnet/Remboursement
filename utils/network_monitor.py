import os
import time
import threading
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from config.settings import SHARED_DATA_BASE_PATH, IS_DEPLOYMENT_MODE
from utils.global_events import network_status_queue

_log = logging.getLogger(__name__)

FAILURE_THRESHOLD = 2  # Détection plus rapide
CHECK_INTERVAL_SECONDS = 2.0  # Intervalle plus court
ACCESS_TIMEOUT_SECONDS = 2.0  # Timeout pour l'opération réseau

def is_path_accessible(path: str) -> bool:
    """
    Vérifie l'accès à un chemin réseau de manière non-bloquante avec un timeout.
    """
    if not IS_DEPLOYMENT_MODE:
        return True

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(os.listdir, path)
    try:
        # Attend le résultat pour un maximum de ACCESS_TIMEOUT_SECONDS
        future.result(timeout=ACCESS_TIMEOUT_SECONDS)
        return True
    except (TimeoutError, IOError, OSError, PermissionError):
        # Si le timeout est atteint ou une erreur d'accès survient, on considère le chemin inaccessible
        return False
    finally:
        # S'assure que le thread de l'executor est bien terminé
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

            time.sleep(self._interval)