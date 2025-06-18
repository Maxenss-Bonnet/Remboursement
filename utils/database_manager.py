import sqlite3
import os
import time
import random
from functools import wraps
import threading
import queue

from config.settings import SHARED_DATA_BASE_PATH

DATABASE_FILE = os.path.join(SHARED_DATA_BASE_PATH, "remboursements.db")

# File d'attente globale pour les opérations d'écriture sur la base de données
# Cela garantit que les écritures sont sérialisées, évitant les conflits de verrouillage.
_write_queue = queue.Queue()
_queue_lock = threading.Lock() # Protège l'accès à la file d'attente elle-même
_stop_queue_processor = threading.Event() # Événement pour arrêter le thread


def _db_writer_thread():
    """
    Thread qui traite les opérations d'écriture de la file d'attente.
    """
    while not _stop_queue_processor.is_set():
        try:
            # Récupère une tâche de la file d'attente avec un timeout
            # pour permettre l'arrêt du thread si _stop_queue_processor est activé.
            task_func, task_args, task_kwargs, result_queue = _write_queue.get(timeout=0.5)
            try:
                # Exécute la fonction de la tâche
                result = task_func(*task_args, **task_kwargs)
                result_queue.put((True, result))
            except Exception as e:
                # En cas d'erreur, place l'exception dans la file de résultat
                result_queue.put((False, e))
            finally:
                _write_queue.task_done()
        except queue.Empty:
            # La file est vide, attend un peu avant de vérifier à nouveau
            pass
        except Exception as e:
            print(f"Erreur inattendue dans le thread d'écriture BDD : {e}")


# Démarrer le thread d'écriture au lancement du module
# C'est important qu'il soit démarré une seule fois.
_writer_thread_instance = threading.Thread(target=_db_writer_thread, daemon=True)
_writer_thread_instance.start()


def stop_db_writer_thread():
    """
    Arrête le thread d'écriture de la base de données.
    Appeler lors de la fermeture de l'application.
    """
    _stop_queue_processor.set()
    _writer_thread_instance.join(timeout=2) # Attendre un peu que le thread se termine
    if _writer_thread_instance.is_alive():
        print("Avertissement: Le thread d'écriture de la BDD n'a pas pu être arrêté proprement.")


def _execute_in_queue(func):
    """
    Décorateur pour les fonctions de modèle qui modifient la BDD.
    Il place l'exécution de la fonction dans une file d'attente pour sérialiser les écritures.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Chaque appel met une tâche dans la file et attend son résultat
        result_queue = queue.Queue(1) # File de taille 1 pour le résultat de cette tâche spécifique
        _write_queue.put((func, args, kwargs, result_queue))
        success, result = result_queue.get() # Bloque jusqu'à ce que le résultat soit disponible

        if not success:
            # Si une exception s'est produite dans le thread, la propager
            raise result
        return result
    return wrapper


def handle_db_locks(func):
    """
    Décorateur pour gérer les erreurs de verrouillage de la base de données SQLite.
    (Principalement pour les lectures qui peuvent être bloquées par un checkpoint WAL)
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


def get_db_connection():
    """Crée et retourne une connexion à la base de données optimisée."""
    # Le timeout est maintenant plus généreux car les écritures sont sérialisées
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
    """Crée les tables de la base de données si elles n'existent pas."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table des utilisateurs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utilisateurs (
        login TEXT PRIMARY KEY,
        hashed_password TEXT NOT NULL,
        email TEXT UNIQUE,
        theme_color TEXT,
        default_filter TEXT,
        profile_picture_path TEXT
    )""")

    # Table des rôles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        role_id INTEGER PRIMARY KEY AUTOINCREMENT,
        role_name TEXT UNIQUE NOT NULL
    )""")

    # Table de liaison utilisateurs <-> rôles
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS utilisateur_roles (
        login TEXT,
        role_id INTEGER,
        PRIMARY KEY (login, role_id),
        FOREIGN KEY (login) REFERENCES utilisateurs (login) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE CASCADE
    )""")

    # Table principale des remboursements
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

    # Table pour l'historique des statuts
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

    # Table pour les pièces jointes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pieces_jointes (
        pj_id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_demande TEXT NOT NULL,
        type_pj TEXT NOT NULL,
        chemin_relatif TEXT NOT NULL,
        date_ajout TEXT NOT NULL,
        FOREIGN KEY (id_demande) REFERENCES remboursements (id_demande) ON DELETE CASCADE
    )""")

    # Création des index pour l'optimisation des performances
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_statut ON remboursements (statut);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_date_modif ON remboursements (date_derniere_modification);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_nom ON remboursements (nom);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_ref_facture ON remboursements (reference_facture);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_is_archived ON remboursements (is_archived);")
    # Index composite pour accélérer la recherche des demandes à archiver au démarrage
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_archivage ON remboursements (is_archived, statut, date_derniere_modification);")
    # Index pour les recherches sur les tables de relations
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_historique_id_demande ON historique (id_demande);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pieces_jointes_id_demande ON pieces_jointes (id_demande);")

    # Nouveaux index suggérés
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_montant_demande ON remboursements (montant_demande);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_remboursements_date_creation ON remboursements (date_creation);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_historique_id_demande_date ON historique (id_demande, date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pieces_jointes_id_demande_date_ajout ON pieces_jointes (id_demande, date_ajout);")

    conn.commit()
    conn.close()