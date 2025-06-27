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

from config.settings import SHARED_DATA_BASE_PATH, DATABASE_FILE, DB_LOCK_FILE, DB_REFRESH_FLAG_FILE
from utils.global_events import status_update_queue, network_status_queue


LOCK_TIMEOUT_SECONDS = 25.0

_write_queue = queue.Queue()
_stop_queue_processor = threading.Event()
_log = logging.getLogger(__name__)


def _is_network_available() -> bool:
    """Vérifie si le chemin de la BDD est accessible."""
    return os.path.isdir(os.path.dirname(DATABASE_FILE))


def _wait_for_network_reconnection():
    """Met en pause l'exécution en attendant que le réseau soit de nouveau accessible."""
    if _is_network_available():
        return

    network_status_queue.put(False)
    status_update_queue.put(("Connexion réseau perdue, l'opération reprendra automatiquement...", True))

    while not _is_network_available():
        if _stop_queue_processor.is_set():
            raise ConnectionAbortedError("Arrêt de l'application demandé.")
        time.sleep(1)

    network_status_queue.put(True)
    status_update_queue.put(("Connexion rétablie, reprise de l'opération en cours...", True))


def _db_writer_thread():
    hostname = socket.gethostname()

    while not _stop_queue_processor.is_set():
        try:
            task_func, task_args, task_kwargs, result_queue, retries = _write_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        lock_acquired = False
        try:
            # --- Boucle pour acquérir le verrou ---
            lock_wait_start = time.time()
            while not lock_acquired:
                if _stop_queue_processor.is_set(): return

                try:
                    _wait_for_network_reconnection()

                    with open(DB_LOCK_FILE, 'x') as f:
                        f.write(f"{os.getpid()}|{time.time()}|{hostname}")
                    lock_acquired = True
                    lock_wait_duration = time.time() - lock_wait_start
                    if lock_wait_duration > 1.0:
                        _log.info(f"Verrou acquis après {lock_wait_duration:.2f}s d'attente.")

                except FileExistsError:
                    status_update_queue.put(("Base de données occupée, en attente...", True))
                    try:
                        with open(DB_LOCK_FILE, 'r') as f:
                            content = f.read().strip()
                        lock_pid_str, lock_time_str, lock_hostname = content.split('|', 2)
                        if (time.time() - float(lock_time_str)) > LOCK_TIMEOUT_SECONDS or \
                           (lock_hostname == hostname and not psutil.pid_exists(int(lock_pid_str))):
                            _log.warning(f"Suppression d'un verrou expiré ou appartenant à un processus mort. Verrou créé il y a {time.time() - float(lock_time_str):.1f}s par {lock_hostname}.")
                            os.remove(DB_LOCK_FILE)
                    except (IOError, IndexError, ValueError):
                        if os.path.exists(DB_LOCK_FILE): os.remove(DB_LOCK_FILE)
                    time.sleep(random.uniform(0.5, 1.5))
                except ConnectionAbortedError as e:
                    result_queue.put((False, e))
                    return
                except (IOError, OSError) as e:
                    _log.error(f"Erreur réseau lors de la tentative de prise de verrou : {e}")
                    time.sleep(3)
                except Exception as e:
                    _log.error(f"Erreur inattendue lors de la prise de verrou : {e}", exc_info=True)
                    time.sleep(2)

            # --- Logique d'exécution de tâche robuste aux coupures ---
            func_name = task_func.__name__
            _log.info(f"Début de l'opération d'écriture en file : {func_name}")
            start_time = time.time()

            task_completed = False
            while not task_completed and retries > 0 and not _stop_queue_processor.is_set():
                try:
                    _wait_for_network_reconnection()

                    result = task_func(*task_args, **task_kwargs)
                    duration = time.time() - start_time
                    _log.info(f"Opération d'écriture '{func_name}' terminée avec succès en {duration:.4f}s.")
                    result_queue.put((True, result))
                    task_completed = True

                except sqlite3.OperationalError as e:
                    if "disk I/O error" in str(e) or "unable to open" in str(e) or "database is locked" in str(e):
                        retries -= 1
                        _log.warning(f"Erreur I/O disque sur '{func_name}'. Connexion probablement perdue. Nouvel essai... ({retries} restants)")
                        status_update_queue.put((f"Erreur réseau, nouvel essai dans 2s...", True))
                        time.sleep(2)
                    else:
                        _log.exception(f"Erreur sqlite inattendue pour '{func_name}'.")
                        result_queue.put((False, e))
                        task_completed = True
                except ConnectionAbortedError as e:
                    result_queue.put((False, e))
                    task_completed = True
                except Exception as e:
                    _log.exception(f"Erreur non gérée dans le thread d'écriture pour '{func_name}'.")
                    result_queue.put((False, e))
                    task_completed = True

            if not task_completed and retries == 0:
                _log.error(f"Échec final de la tâche '{func_name}' après plusieurs tentatives.")
                result_queue.put((False, Exception(f"Échec de l'opération BDD pour {func_name} après plusieurs tentatives.")))

        finally:
            if lock_acquired:
                try:
                    os.remove(DB_LOCK_FILE)
                except OSError as e:
                    _log.error(f"Impossible de supprimer le fichier de verrou : {e}", exc_info=True)

                temp_flag_path = f"{DB_REFRESH_FLAG_FILE}.{os.getpid()}.tmp"
                try:
                    with open(temp_flag_path, 'w') as f:
                        f.write(str(time.time()))
                    os.replace(temp_flag_path, DB_REFRESH_FLAG_FILE)
                except IOError as e:
                    _log.error(f"Impossible de créer le fichier de signal de rafraîchissement : {e}", exc_info=True)
                    if os.path.exists(temp_flag_path):
                        os.remove(temp_flag_path)

            status_update_queue.put(("Prêt", False))
            _write_queue.task_done()


_writer_thread_instance = threading.Thread(target=_db_writer_thread, name="DBWriterThread", daemon=True)
_writer_thread_instance.start()


def stop_db_writer_thread():
    _log.info("Tentative d'arrêt du thread d'écriture de la BDD...")
    _stop_queue_processor.set()
    while not _write_queue.empty():
        try:
            _write_queue.get_nowait()
            _write_queue.task_done()
        except queue.Empty:
            break
    _writer_thread_instance.join(timeout=2)
    if _writer_thread_instance.is_alive():
        _log.warning("Le thread d'écriture de la BDD n'a pas pu être arrêté proprement.")
    else:
        _log.info("Thread d'écriture de la BDD arrêté.")


def is_db_writer_busy() -> bool:
    return not _write_queue.empty() or os.path.exists(DB_LOCK_FILE)


def execute_in_queue(func):
    """Décorateur pour exécuter une fonction dans la file d'attente d'écriture de la BDD."""
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
    """Décorateur pour gérer les lectures concurrentes et les problèmes de connexion."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        retries = 5
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                error_str = str(e).lower()
                is_network_error = "disk i/o error" in error_str or "unable to open" in error_str
                is_lock_error = "locked" in error_str or "busy" in error_str

                if is_network_error or is_lock_error:
                    if i < retries - 1:
                        wait_time = random.uniform(0.3, 0.8)
                        _log.warning(
                            f"Base de données indisponible. Erreur: '{error_str}'. Tentative {i + 1}/{retries} dans {wait_time:.2f}s pour {func.__name__}...")

                        if is_network_error:
                            network_status_queue.put(False)

                        time.sleep(wait_time)

                        if is_network_error:
                             network_status_queue.put(True)
                        continue
                    else:
                        _log.error(
                            f"La base de données est restée indisponible après plusieurs tentatives pour {func.__name__}.")
                        raise ConnectionError("La base de données est inaccessible. Vérifiez la connexion réseau.") from e
                else:
                    raise e
            except Exception as e:
                _log.error(f"Erreur inattendue dans handle_db_locks pour {func.__name__}", exc_info=True)
                raise e
    return wrapper



def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA cache_size = -8192;")
    cursor.execute("PRAGMA mmap_size = 268435456;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA temp_store = MEMORY;")
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
            FOREIGN KEY (derniere_modification_par) REFERENCES utilisateurs (login)ON DELETE SET NULL
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

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_statut ON remboursements (statut);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_remboursements_date_modif ON remboursements (date_derniere_modification);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_nom ON remboursements (nom);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_remboursements_ref_facture ON remboursements (reference_facture);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_is_archived ON remboursements (is_archived);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_historique_id_demande ON historique (id_demande);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pieces_jointes_id_demande ON pieces_jointes (id_demande);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_remboursements_filtre_general ON remboursements (is_archived, date_derniere_modification DESC);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_remboursements_filtre_statut ON remboursements (is_archived, statut, date_derniere_modification DESC);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_remboursements_recherche ON remboursements (nom, prenom, reference_facture);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_montant_demande ON remboursements (montant_demande);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_date_creation ON remboursements (date_creation);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_historique_id_demande_date ON historique (id_demande, date);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_pieces_jointes_id_demande_date_ajout ON pieces_jointes (id_demande, date_ajout);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_cree_par ON remboursements (cree_par);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_remboursements_filtre_general ON remboursements (is_archived, date_derniere_modification DESC);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_remboursements_filtre_statut ON remboursements (is_archived, statut, date_derniere_modification DESC);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_remboursements_recherche ON remboursements (nom, prenom, reference_facture);")
        conn.commit()