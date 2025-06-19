import os
import sys

# Ajoute le chemin du projet au PYTHONPATH pour permettre les imports relatifs
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from utils.database_manager import get_db_connection


def supprimer_demandes_fictives():
    """
    Identifie et supprime les demandes de test de la base de données
    en se basant sur le préfixe 'FTEST-' dans la référence de facture.
    """
    print("--- Script de nettoyage des données de test ---")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"ERREUR: Impossible de se connecter à la base de données : {e}")
        return

    # 1. Compter combien de demandes de test existent
    try:
        cursor.execute("SELECT COUNT(*) FROM remboursements WHERE reference_facture LIKE 'FTEST-%'")
        count = cursor.fetchone()[0]

        if count == 0:
            print("Aucune demande de test trouvée. Le nettoyage n'est pas nécessaire.")
            conn.close()
            return

        print(f"ATTENTION : {count} demande(s) de test ont été trouvées et vont être supprimées.")

        # 2. Demander la confirmation de l'utilisateur
        confirmation = input("Voulez-vous vraiment continuer ? (oui/non) : ").lower()

        if confirmation not in ['oui', 'o']:
            print("Opération annulée par l'utilisateur.")
            conn.close()
            return

        # 3. Procéder à la suppression
        print("Suppression en cours...")
        cursor.execute("DELETE FROM remboursements WHERE reference_facture LIKE 'FTEST-%'")

        # Valider la transaction
        conn.commit()

        # Récupérer le nombre de lignes supprimées
        lignes_supprimees = cursor.rowcount

        print(f"Succès : {lignes_supprimees} demande(s) de test ont été supprimées de la base de données.")

    except Exception as e:
        print(f"Une erreur est survenue durant l'opération : {e}")
        conn.rollback()  # Annuler les changements en cas d'erreur
    finally:
        conn.close()


if __name__ == "__main__":
    supprimer_demandes_fictives()