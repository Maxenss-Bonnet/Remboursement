import getpass
from models.schemas import Utilisateur
from models.user_model import ajouter_utilisateur_data, obtenir_utilisateur_par_login_data
from utils.password_utils import generer_hachage_mdp
from utils.database_manager import create_tables


def setup_initial_user():
    """
    Configure le premier utilisateur (admin) de l'application si aucun utilisateur n'existe.
    """
    print("Vérification de la configuration initiale des utilisateurs...")

    try:
        print("Initialisation de la base de données et création des tables si nécessaire...")
        create_tables()
        print("Base de données prête.")
    except Exception as e:
        print(f"ERREUR CRITIQUE: Impossible d'initialiser la base de données : {e}")
        return

    admin_user = obtenir_utilisateur_par_login_data("admin")

    if admin_user:
        print("Un utilisateur 'admin' existe déjà. Aucune action n'est requise.")
        return

    print("\n--- Création du compte administrateur initial ---")
    print("Aucun utilisateur 'admin' trouvé. Procédons à sa création.")

    while True:
        password = getpass.getpass("Entrez le mot de passe pour le compte 'admin': ")
        if not password:
            print("Le mot de passe ne peut pas être vide.")
            continue

        password_confirm = getpass.getpass("Confirmez le mot de passe: ")
        if password == password_confirm:
            break
        else:
            print("Les mots de passe ne correspondent pas. Veuillez réessayer.")

    hashed_password = generer_hachage_mdp(password)

    admin_user_data = Utilisateur(
        login="admin",
        hashed_password=hashed_password,
        email="admin@example.com",
        roles=["admin"],
        theme_color="System",
        default_filter="Toutes les demandes"
    )

    success, message = ajouter_utilisateur_data(admin_user_data)

    if success:
        print("\nLe compte 'admin' a été créé avec succès.")
        print("Vous pouvez maintenant lancer l'application principale.")
    else:
        print(f"\nERREUR: Impossible de créer le compte 'admin': {message}")


if __name__ == "__main__":
    setup_initial_user()