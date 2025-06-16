import os
import json
import sqlite3
from tqdm import tqdm

from config.settings import USER_DATA_FILE, REMBOURSEMENTS_JSON_DIR
from models.schemas import Remboursement
from utils.database_manager import create_tables, get_db_connection


def migrate_users_and_roles():
    """Migre les utilisateurs et leurs rôles depuis le fichier JSON vers la BDD."""
    print("Début de la migration des utilisateurs et des rôles...")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            users_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Erreur: Impossible de lire le fichier utilisateurs.json. {e}")
        conn.close()
        return

    role_cache = {}
    for login, user_info in tqdm(users_data.items(), desc="Utilisateurs"):
        # Insérer l'utilisateur
        cursor.execute("""
            INSERT OR REPLACE INTO utilisateurs (login, hashed_password, email, theme_color, default_filter, profile_picture_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            login,
            user_info.get('hashed_password'),
            user_info.get('email'),
            user_info.get('theme_color'),
            user_info.get('default_filter'),
            user_info.get('profile_picture_path')
        ))

        # Supprimer les anciens rôles pour cet utilisateur pour éviter les doublons
        cursor.execute("DELETE FROM utilisateur_roles WHERE login = ?", (login,))

        # Gérer les rôles
        for role_name in user_info.get('roles', []):
            if role_name not in role_cache:
                cursor.execute("INSERT OR IGNORE INTO roles (role_name) VALUES (?)", (role_name,))
                cursor.execute("SELECT role_id FROM roles WHERE role_name = ?", (role_name,))
                role_id = cursor.fetchone()['role_id']
                role_cache[role_name] = role_id

            role_id = role_cache[role_name]
            cursor.execute("INSERT INTO utilisateur_roles (login, role_id) VALUES (?, ?)", (login, role_id))

    conn.commit()
    conn.close()
    print("Migration des utilisateurs et des rôles terminée avec succès.")


def migrate_remboursements():
    """Migre les demandes de remboursement depuis les fichiers JSON vers la BDD."""
    print("\nDébut de la migration des demandes de remboursement...")
    conn = get_db_connection()

    json_files = [f for f in os.listdir(REMBOURSEMENTS_JSON_DIR) if f.endswith('.json')]

    for filename in tqdm(json_files, desc="Demandes"):
        filepath = os.path.join(REMBOURSEMENTS_JSON_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                demande = Remboursement(**data)

            with conn:  # Utilisation d'un bloc 'with' pour gérer la transaction
                cursor = conn.cursor()

                # Insérer la demande principale
                cursor.execute("""
                    INSERT OR REPLACE INTO remboursements (
                        id_demande, nom, prenom, reference_facture, reference_facture_dossier,
                        description, montant_demande, statut, cree_par, date_creation,
                        derniere_modification_par, date_derniere_modification, date_paiement_effectue,
                        is_archived
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    demande.id_demande, demande.nom, demande.prenom, demande.reference_facture,
                    demande.reference_facture_dossier, demande.description, demande.montant_demande,
                    demande.statut, demande.cree_par, demande.date_creation,
                    demande.derniere_modification_par, demande.date_derniere_modification,
                    demande.date_paiement_effectue, 0  # 0 pour non archivé par défaut
                ))

                # Insérer l'historique
                for hist in demande.historique_statuts:
                    cursor.execute("""
                                   INSERT INTO historique (id_demande, statut, date, par_utilisateur, commentaire)
                                   VALUES (?, ?, ?, ?, ?)
                                   """,
                                   (demande.id_demande, hist.statut, hist.date, hist.par_utilisateur, hist.commentaire))

                # Insérer les pièces jointes
                for pj_path in demande.chemins_factures_stockees:
                    cursor.execute(
                        "INSERT INTO pieces_jointes (id_demande, type_pj, chemin_relatif, date_ajout) VALUES (?, ?, ?, ?)",
                        (demande.id_demande, 'facture', pj_path, demande.date_creation))
                for pj_path in demande.chemins_rib_stockes:
                    cursor.execute(
                        "INSERT INTO pieces_jointes (id_demande, type_pj, chemin_relatif, date_ajout) VALUES (?, ?, ?, ?)",
                        (demande.id_demande, 'rib', pj_path, demande.date_creation))
                for pj_path in demande.chemins_trop_percu_stockes:
                    cursor.execute(
                        "INSERT INTO pieces_jointes (id_demande, type_pj, chemin_relatif, date_ajout) VALUES (?, ?, ?, ?)",
                        (demande.id_demande, 'trop_percu', pj_path, demande.date_creation))

        except (FileNotFoundError, json.JSONDecodeError, TypeError) as e:
            print(f"\nErreur lors du traitement du fichier {filename}: {e}. Ce fichier sera ignoré.")
        except sqlite3.Error as e:
            print(f"\nErreur de base de données lors du traitement de {filename}: {e}. La transaction sera annulée.")

    conn.close()
    print("Migration des demandes de remboursement terminée.")


if __name__ == "__main__":
    print("--- Début du script de migration vers SQLite ---")

    # 1. Créer la structure de la base de données
    print("Étape 1/3: Création des tables de la base de données...")
    create_tables()
    print("Tables créées ou déjà existantes.")

    # 2. Migrer les utilisateurs
    print("\nÉtape 2/3: Migration des données utilisateurs...")
    migrate_users_and_roles()

    # 3. Migrer les demandes de remboursement
    print("\nÉtape 3/3: Migration des données de remboursement...")
    migrate_remboursements()

    print("\n--- Migration terminée ---")
    print("Vérifiez la console pour d'éventuels messages d'erreur.")
    print(f"Le fichier de base de données 'remboursements.db' a été créé/mis à jour.")