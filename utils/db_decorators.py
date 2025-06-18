import sqlite3
import time
import random
from functools import wraps

def handle_db_locks(func):
    """
    Décorateur pour gérer les erreurs de verrouillage de la base de données SQLite.
    Réessaye une fonction plusieurs fois si une erreur "database is locked" est rencontrée.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        retries = 5
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if "locked" in str(e) or "busy" in str(e):
                    if i < retries - 1:
                        wait_time = random.uniform(0.2, 0.5)
                        print(f"Avertissement: Base de données verrouillée. Tentative {i + 1}/{retries} dans {wait_time:.2f}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print("Erreur: La base de données est restée verrouillée après plusieurs tentatives.")
                        raise e
                else:
                    raise e
    return wrapper