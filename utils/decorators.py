import time
import logging
from functools import wraps

_log = logging.getLogger(__name__)


def retry_on_network_error(retries=3, delay=2, allowed_exceptions=(IOError, OSError)):
    """
    Décorateur pour réessayer une fonction en cas d'erreur réseau.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except allowed_exceptions as e:
                    _log.warning(
                        f"Erreur réseau dans '{func.__name__}': {e}. Tentative {i + 1}/{retries} dans {delay}s...")
                    if i < retries - 1:
                        time.sleep(delay)
                    else:
                        _log.error(f"Échec de l'opération '{func.__name__}' après {retries} tentatives.")
                        raise  # Relève l'exception après le dernier échec
        return wrapper
    return decorator