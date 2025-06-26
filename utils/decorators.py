import time
import logging
from functools import wraps
from utils.network_monitor import wait_for_network
from utils.global_events import status_update_queue


_log = logging.getLogger(__name__)


def retry_on_network_error(retries=3, delay=2, infinite_retry_on_disconnect=False, allowed_exceptions=(IOError, OSError)):
    """
    Décorateur pour réessayer une fonction, en attendant la connexion réseau de manière proactive.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            remaining_retries = retries
            while True:
                # 1. Vérification proactive rapide avant chaque tentative.
                # C'est cette fonction qui gère l'attente et le feedback UI.
                wait_for_network(func.__name__)

                try:
                    # 2. Tentative d'exécution de l'opération.
                    return func(*args, **kwargs)

                except allowed_exceptions as e:
                    # 3. Échec (cas d'une coupure juste avant l'appel - fallback).
                    _log.warning(f"Erreur réseau 'réactive' dans '{func.__name__}': {e}.")

                    if not infinite_retry_on_disconnect:
                        remaining_retries -= 1
                        if remaining_retries <= 0:
                            _log.error(f"Échec final de l'opération '{func.__name__}' après {retries} tentatives.")
                            status_update_queue.put((f"Échec de l'opération '{func.__name__}'.", False))
                            raise e
                        time.sleep(delay)

                    # Si infinite_retry, la boucle `while` principale recommencera
                    # et `wait_for_network` prendra de nouveau la main.
        return wrapper
    return decorator