import os
import time
import threading
import logging
from config.settings import SHARED_DATA_BASE_PATH, IS_DEPLOYMENT_MODE
from utils.global_events import status_update_queue, network_status_queue, loader_status_queue

_log = logging.getLogger(__name__)


def _check_path_blocking(path: str, result_container: dict):
    """Effectue la vérification I/O bloquante dans un thread séparé."""
    try:
        os.listdir(path)
        result_container['result'] = True
    except (OSError, IOError, PermissionError):
        result_container['result'] = False


def is_path_accessible(path: str, timeout: float = 2.5) -> bool:
    """Vérifie si un chemin est accessible dans un délai imparti pour éviter les blocages."""
    if not IS_DEPLOYMENT_MODE or not path:
        return True

    result_container = {}
    checker_thread = threading.Thread(target=_check_path_blocking, args=(path, result_container), daemon=True)
    checker_thread.start()
    checker_thread.join(timeout=timeout)

    if checker_thread.is_alive():
        return False  # Le thread est bloqué, donc le réseau est inaccessible/lent

    return result_container.get('result', False)


def wait_for_network(func_name: str = "Opération réseau"):
    """
    Fonction centrale qui gère la boucle d'attente active du réseau et la communication avec l'UI.
    Elle est désormais plus tolérante aux latences.
    """
    # Première vérification rapide. Si elle passe, on ne fait rien de plus.
    if is_path_accessible(SHARED_DATA_BASE_PATH, timeout=1.0):
        return

    # Si la première vérification échoue (possible latence), on fait une seconde plus patiente.
    if is_path_accessible(SHARED_DATA_BASE_PATH, timeout=3.0):
        _log.info(f"Latence détectée pour l'opération '{func_name}', mais la connexion est stable. Continuation.")
        return

    # Si même la vérification patiente échoue, on déclare la déconnexion.
    _log.warning(f"Opération '{func_name}' en pause. Déconnexion réseau confirmée.")
    is_currently_disconnected = True
    network_status_queue.put(False)
    status_update_queue.put(("Connexion réseau perdue. Tentative de reconnexion...", True))
    loader_status_queue.put("Connexion réseau perdue. En attente...")

    while not is_path_accessible(SHARED_DATA_BASE_PATH, timeout=3.0):
        time.sleep(1)

    if is_currently_disconnected:
        _log.info(f"Réseau détecté pour l'opération '{func_name}'. Reprise.")
        network_status_queue.put(True)
        status_update_queue.put(("Connexion rétablie.", False))
        loader_status_queue.put("Connexion rétablie, reprise de l'opération...")
        time.sleep(0.5)


class NetworkMonitor:
    def __init__(self, check_interval_seconds: int = 2):
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
        """Boucle principale de vérification de la connexion (détection passive)."""
        time.sleep(self._interval)
        while not self._stop_event.is_set():
            current_status = is_path_accessible(SHARED_DATA_BASE_PATH, timeout=2.0)

            if current_status != self._is_connected:
                self._is_connected = current_status
                status_str = "RECONNECTED" if self._is_connected else "DISCONNECTED"
                _log.info(f"Changement d'état de la connexion réseau détecté (moniteur passif) : {status_str}")
                network_status_queue.put(self._is_connected)

            time.sleep(self._interval)