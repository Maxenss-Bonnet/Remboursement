import sqlite3
import os
import time
import random
import socket
from functools import wraps
import threading
import queue
import logging
from contextlib import contextmanager

import psutil

from config.settings import SHARED_DATA_BASE_PATH, DATABASE_FILE
from utils.global_events import status_update_queue
from utils.network_monitor import is_path_accessible, wait_for_network

DB_LOCK_FILE = os.path.join(SHARED_DATA_BASE_PATH, "remboursements.db.lock")
DB_REFRESH_FLAG_FILE = os.path.join(SHARED_DATA_BASE_PATH, "refresh_required.flag")
LOCK_TIMEOUT_SECONDS = 60.0

_write_queue = queue.Queue()
_stop_queue_processor = threading.Event()
_log = logging.getLogger(__name__)


def _db_writer_thread():
    hostname = socket.gethostname()

    while not _stop_queue_processor.is_set():
        try:
            task_func, task_args, task_kwargs, result_queue, retries = _write_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        wait_for_network(f"Tâche BDD: {task_func.__name__}")

        lock_acquired = False
        try:
            start_lock_wait = time.time()
            while not lock_acquired:
                if _stop_queue_processor.is_set(): return

                try:
                    with open(DB_LOCK_FILE, 'x') as f:
                        f.write(f"{os.getpid()}|{time.time()}|{hostname}")
                    lock_acquired = True
                except FileExistsError:
                    if time.time() - start_lock_wait > LOCK_TIMEOUT_SECONDS:
                        _log.warning(f"Timeout en attente du verrou BDD. Forçage de la suppression du verrou.")
                        try: os.remove(DB_LOCK_FILE)
                        except OSError: pass
                        start_lock_wait = time.time()
                    status_update_queue.put(("Base de données occupée, en attente...", True))
                    time.sleep(random.uniform(0.5, 1.5))
                except (IOError, OSError) as e:
                    _log.error(f"Erreur réseau lors de la tentative de prise de verrou : {e}")
                    time.sleep(2)

            task_completed = False
            while not task_completed and retries > 0 and not _stop_queue_processor.is_set():
                try:
                    result = task_func(*task_args, **task_kwargs)
                    result_queue.put((True, result))
                    task_completed = True
                except sqlite3.OperationalError as e:
                    _log.warning(f"Erreur BDD: '{e}'. Nouvel essai... ({retries - 1} restants)")
                    retries -= 1
                    time.sleep(2)
                except Exception as e:
                    _log.exception(f"Erreur non gérée dans le thread d'écriture pour '{task_func.__name__}'.")
                    result_queue.put((False, e)); task_completed = True

            if not task_completed and retries == 0:
                _log.error(f"Échec final de la tâche '{task_func.__name__}' après plusieurs tentatives.")
                result_queue.put((False, Exception(f"Échec de l'opération BDD pour {task_func.__name__}.")))

        finally:
            if lock_acquired:
                try:
                    os.remove(DB_LOCK_FILE)
                    with open(DB_REFRESH_FLAG_FILE, 'w') as f:
                        f.write(str(time.time()))
                except OSError as e:
                    _log.error(f"Impossible de gérer les fichiers de lock/flag : {e}", exc_info=True)
            status_update_queue.put(("Prêt", False))
            _write_queue.task_done()


_writer_thread_instance = threading.Thread(target=_db_writer_thread, name="DBWriterThread", daemon=True)
_writer_thread_instance.start()


def stop_db_writer_thread():
    _log.info("Tentative d'arrêt du thread d'écriture de la BDD...")
    _stop_queue_processor.set()
    if _writer_thread_instance.is_alive():
        _writer_thread_instance.join(timeout=2)
    if _writer_thread_instance.is_alive():
        _log.warning("Le thread d'écriture de la BDD n'a pas pu être arrêté proprement.")
    else:
        _log.info("Thread d'écriture de la BDD arrêté.")


def is_db_writer_busy() -> bool:
    return not _write_queue.empty() or os.path.exists(DB_LOCK_FILE)


def execute_in_queue(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result_queue = queue.Queue(1)
        _write_queue.put((func, args, kwargs, result_queue, 3))
        success, result = result_queue.get()
        if not success:
            raise result
        return result
    return wrapper


def handle_db_locks(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        wait_for_network(f"Opération de lecture BDD: {func.__name__}")
        retries = 5
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                if "locked" in str(e) or "busy" in str(e):
                    if i < retries - 1:
                        _log.warning(f"Base de données verrouillée pour la lecture ({func.__name__}). Tentative {i + 1}/{retries}...")
                        time.sleep(random.uniform(0.3, 0.8))
                        continue
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


@contextmanager
def db_connection():
    conn = None
    try:
        conn = get_db_connection()
        yield conn
    finally:
        if conn:
            conn.close()


def create_tables():
    with db_connection() as conn:
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

        # --- INDEX ---
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_statut ON remboursements (statut);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_date_modif ON remboursements (date_derniere_modification);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_nom ON remboursements (nom);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_ref_facture ON remboursements (reference_facture);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_is_archived ON remboursements (is_archived);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_historique_id_demande ON historique (id_demande);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pieces_jointes_id_demande ON pieces_jointes (id_demande);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_filtre_general ON remboursements (is_archived, date_derniere_modification DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_filtre_statut ON remboursements (is_archived, statut, date_derniere_modification DESC);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_recherche ON remboursements (nom, prenom, reference_facture);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_montant_demande ON remboursements (montant_demande);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_date_creation ON remboursements (date_creation);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_historique_id_demande_date ON historique (id_demande, date);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pieces_jointes_id_demande_date_ajout ON pieces_jointes (id_demande, date_ajout);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_cree_par ON remboursements (cree_par);")

        conn.commit()