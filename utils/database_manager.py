import sqlite3
import os
import time
import random
from functools import wraps
import threading
import queue
import logging

from config.settings import SHARED_DATA_BASE_PATH

DATABASE_FILE = os.path.join(SHARED_DATA_BASE_PATH, "remboursements.db")

_write_queue = queue.Queue()
_stop_queue_processor = threading.Event()
_log = logging.getLogger(__name__)


def _db_writer_thread():
    """Thread qui traite les opérations d'écriture sur la BDD de manière séquentielle."""
    while not _stop_queue_processor.is_set():
        try:
            task_func, task_args, task_kwargs, result_queue = _write_queue.get(timeout=0.5)
            func_name = task_func.__name__
            _log.info(f"Début de l'opération d'écriture en file : {func_name}")
            start_time = time.time()
            try:
                result = task_func(*task_args, **task_kwargs)
                duration = time.time() - start_time
                _log.info(f"Opération d'écriture '{func_name}' terminée avec succès en {duration:.4f}s.")
                result_queue.put((True, result))
            except Exception as e:
                _log.exception(f"Erreur dans le thread d'écriture de la BDD lors de l'exécution de la tâche '{func_name}'.")
                result_queue.put((False, e))
            finally:
                _write_queue.task_done()
        except queue.Empty:
            pass
        except Exception as e:
            _log.critical(f"Erreur inattendue dans le thread d'écriture BDD : {e}")


_writer_thread_instance = threading.Thread(target=_db_writer_thread, name="DBWriterThread", daemon=True)
_writer_thread_instance.start()


def stop_db_writer_thread():
    """Arrête proprement le thread d'écriture de la BDD."""
    _log.info("Tentative d'arrêt du thread d'écriture de la BDD...")
    _stop_queue_processor.set()
    _write_queue.join()
    _writer_thread_instance.join(timeout=2)
    if _writer_thread_instance.is_alive():
        _log.warning("Le thread d'écriture de la BDD n'a pas pu être arrêté proprement.")
    else:
        _log.info("Thread d'écriture de la BDD arrêté.")


def is_db_writer_busy() -> bool:
    """Vérifie si la file d'attente d'écriture de la BDD contient des opérations."""
    return not _write_queue.empty()


def execute_in_queue(func):
    """
    Décorateur pour exécuter une fonction dans la file d'attente d'écriture séquentielle.
    Cela garantit qu'une seule écriture se produit à la fois sur la BDD.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        result_queue = queue.Queue(1)
        _write_queue.put((func, args, kwargs, result_queue))
        success, result = result_queue.get()

        if not success:
            raise result
        return result
    return wrapper


def handle_db_locks(func):
    """
    Décorateur pour gérer les erreurs de verrouillage SQLite, principalement pour les lectures.
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
                        _log.warning(f"Base de données verrouillée. Tentative {i + 1}/{retries} dans {wait_time:.2f}s pour la fonction {func.__name__}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        _log.error(f"La base de données est restée verrouillée après plusieurs tentatives pour {func.__name__}.")
                        raise e
                else:
                    raise e
    return wrapper


def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE, timeout=30)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA cache_size = -4096;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()

    return conn

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utilisateurs (
        login TEXT PRIMARY KEY,
        hashed_password TEXT NOT NULL,
        email TEXT UNIQUE,
        theme_color TEXT,
        default_filter TEXT,
        profile_picture_path TEXT
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        role_id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name TEXT UNIQUE NOT NULL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utilisateur_roles (
        login TEXT,
        role_id INTEGER,
        PRIMARY KEY (login, role_id),
        FOREIGN KEY (login) REFERENCES utilisateurs (login) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE CASCADE
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS remboursements (
        id_demande TEXT PRIMARY KEY,
        nom TEXT,
        prenom TEXT,
        reference_facture TEXT NOT NULL,
        reference_facture_dossier TEXT,
        description TEXT,
        montant_demande REAL NOT NULL,
        statut TEXT NOT NULL,
        cree_par TEXT,
        date_creation TEXT NOT NULL,
        derniere_modification_par TEXT,
        date_derniere_modification TEXT NOT NULL,
        date_paiement_effectue TEXT,
        is_archived INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (cree_par) REFERENCES utilisateurs (login) ON DELETE SET NULL,
        FOREIGN KEY (derniere_modification_par) REFERENCES utilisateurs (login) ON DELETE SET NULL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historique (
        historique_id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_demande TEXT NOT NULL,
        statut TEXT,
        date TEXT NOT NULL,
        par_utilisateur TEXT,
        commentaire TEXT,
        FOREIGN KEY (id_demande) REFERENCES remboursements (id_demande) ON DELETE CASCADE,
        FOREIGN KEY (par_utilisateur) REFERENCES utilisateurs (login) ON DELETE SET NULL
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pieces_jointes (
        pj_id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_demande TEXT NOT NULL,
        type_pj TEXT NOT NULL,
        chemin_relatif TEXT NOT NULL,
        date_ajout TEXT NOT NULL,
        FOREIGN KEY (id_demande) REFERENCES remboursements (id_demande) ON DELETE CASCADE
    )""")

    # --- Index existants et nouveaux index composites ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_statut ON remboursements (statut);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_date_modif ON remboursements (date_derniere_modification);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_nom ON remboursements (nom);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_ref_facture ON remboursements (reference_facture);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_is_archived ON remboursements (is_archived);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_historique_id_demande ON historique (id_demande);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pieces_jointes_id_demande ON pieces_jointes (id_demande);")

    # --- NOUVEAUX INDEX POUR L'OPTIMISATION ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_filtre_general ON remboursements (is_archived, date_derniere_modification DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_filtre_statut ON remboursements (is_archived, statut, date_derniere_modification DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_recherche ON remboursements (nom, prenom, reference_facture);")

    # --- ANCIENS INDEXS CONSERVÉS ---
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_montant_demande ON remboursements (montant_demande);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_date_creation ON remboursements (date_creation);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_historique_id_demande_date ON historique (id_demande, date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pieces_jointes_id_demande_date_ajout ON pieces_jointes (id_demande, date_ajout);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_cree_par ON remboursements (cree_par);")


    conn.commit()
    conn.close()