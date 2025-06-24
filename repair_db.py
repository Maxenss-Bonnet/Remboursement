import sqlite3
import os
import sys
import shutil
import datetime

# Ajoute le chemin du projet au PYTHONPATH pour permettre les imports relatifs
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

try:
    from config.settings import DATABASE_FILE
except ImportError:
    print("Erreur: Impossible d'importer la configuration. Assurez-vous que le script est à la racine du projet.")
    # Fallback au cas où le chemin est différent lors de l'exécution
    db_path_guess = os.path.join(os.path.dirname(__file__), "donnees_partagees_mock", "remboursements.db")
    if os.path.exists(db_path_guess):
        DATABASE_FILE = db_path_guess
    else:
        DATABASE_FILE = None


def get_correct_schema():
    """ Retourne les définitions SQL correctes pour les tables à réparer. """
    historique_sql = """
    CREATE TABLE historique_reparee (
        historique_id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_demande TEXT NOT NULL,
        statut TEXT,
        date TEXT NOT NULL,
        par_utilisateur TEXT,
        commentaire TEXT,
        FOREIGN KEY (id_demande) REFERENCES remboursements (id_demande) ON DELETE CASCADE,
        FOREIGN KEY (par_utilisateur) REFERENCES utilisateurs (login) ON DELETE SET NULL
    )
    """

    pieces_jointes_sql = """
    CREATE TABLE pieces_jointes_reparee (
        pj_id INTEGER PRIMARY KEY AUTOINCREMENT,
        id_demande TEXT NOT NULL,
        type_pj TEXT NOT NULL,
        chemin_relatif TEXT NOT NULL,
        date_ajout TEXT NOT NULL,
        FOREIGN KEY (id_demande) REFERENCES remboursements (id_demande) ON DELETE CASCADE
    )
    """
    return historique_sql, pieces_jointes_sql


def repair_database_schema():
    """
    Répare le schéma de la base de données en recréant les tables avec
    les bonnes clés étrangères.
    """
    if not DATABASE_FILE or not os.path.exists(DATABASE_FILE):
        print(f"Erreur: Fichier de base de données introuvable. Vérifiez le chemin : {DATABASE_FILE}")
        return

    print("--- Outil de Réparation de Schéma de Base de Données ---")

    backup_path = DATABASE_FILE + f'.backup-reparation-{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}'
    try:
        print(f"1. Création d'une sauvegarde de sécurité : {backup_path}")
        shutil.copy2(DATABASE_FILE, backup_path)
        print("   -> Sauvegarde créée avec succès.")
    except Exception as e:
        print(f"ERREUR CRITIQUE : Impossible de créer la sauvegarde. Opération annulée. Erreur : {e}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        print("\n2. Début du processus de réparation...")
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("BEGIN TRANSACTION;")

        historique_sql, pieces_jointes_sql = get_correct_schema()

        # --- Réparation de la table 'historique' ---
        print("   - Réparation de la table 'historique'...")
        cursor.execute(historique_sql)
        cursor.execute("INSERT INTO historique_reparee SELECT * FROM historique;")
        cursor.execute("DROP TABLE historique;")
        cursor.execute("ALTER TABLE historique_reparee RENAME TO historique;")
        print("     -> Table 'historique' réparée.")

        # --- Réparation de la table 'pieces_jointes' ---
        print("   - Réparation de la table 'pieces_jointes'...")
        cursor.execute(pieces_jointes_sql)
        cursor.execute("INSERT INTO pieces_jointes_reparee SELECT * FROM pieces_jointes;")
        cursor.execute("DROP TABLE pieces_jointes;")
        cursor.execute("ALTER TABLE pieces_jointes_reparee RENAME TO pieces_jointes;")
        print("     -> Table 'pieces_jointes' réparée.")

        print("\n3. Finalisation des modifications...")
        conn.commit()
        print("   -> Modifications enregistrées.")

        print("\n4. Vérification de l'intégrité de la base de données...")
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        if result[0] == "ok":
            print("   -> Vérification d'intégrité réussie. La base de données est saine.")
        else:
            print(f"   -> ATTENTION: La vérification a échoué avec le message : {result[0]}")

        print("\n**************************************")
        print("* RÉPARATION TERMINÉE          *")
        print("**************************************")
        print("Le problème devrait être résolu. Vous pouvez relancer l'application principale.")

    except Exception as e:
        print(f"\nUNE ERREUR CRITIQUE EST SURVENUE DURANT LA RÉPARATION: {e}")
        if conn:
            print("Annulation de toutes les modifications (rollback)...")
            conn.rollback()
        print("Votre base de données n'a PAS été modifiée. Vous pouvez utiliser la sauvegarde créée pour restaurer si besoin.")
    finally:
        if conn:
            cursor.execute("PRAGMA foreign_keys = ON;")
            conn.close()


if __name__ == "__main__":
    repair_database_schema()