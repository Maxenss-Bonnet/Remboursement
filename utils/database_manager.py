import sqlite3
import os
from config.settings import SHARED_DATA_BASE_PATH

DATABASE_FILE = os.path.join(SHARED_DATA_BASE_PATH, "remboursements.db")

def get_db_connection():
    """Crée et retourne une connexion à la base de données optimisée."""
    conn = sqlite3.connect(DATABASE_FILE, timeout=20)
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