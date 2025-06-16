# controllers/auth_controller.py
import smtplib
import os
from models import user_model
from utils import password_utils
from config.settings import (
    ROLES_UTILISATEURS,
    ASSIGNABLE_ROLES,
    save_email_config_to_ini,
    SMTP_CONFIG,
    load_smtp_config,
    PROFILE_PICTURES_DIR
)
from models.schemas import Utilisateur, UtilisateurUpdate


class AuthController:
    def __init__(self):
        pass

    def tenter_connexion(self, nom_utilisateur: str, mot_de_passe_saisi: str) -> str | None:
        """Tente de connecter un utilisateur en vérifiant son mot de passe contre la BDD."""
        user = user_model.obtenir_utilisateur_par_login_data(nom_utilisateur)
        if user and password_utils.verifier_mdp(mot_de_passe_saisi, user.hashed_password):
            return nom_utilisateur
        return None

    def modifier_mot_de_passe(self, nom_utilisateur: str, ancien_mdp: str, nouveau_mdp: str) -> bool:
        """Modifie le mot de passe d'un utilisateur après vérification de l'ancien."""
        user = user_model.obtenir_utilisateur_par_login_data(nom_utilisateur)
        if not user or not password_utils.verifier_mdp(ancien_mdp, user.hashed_password):
            return False

        update_data = UtilisateurUpdate(password=nouveau_mdp)
        success, _ = user_model.mettre_a_jour_utilisateur_data(nom_utilisateur, update_data)
        return success

    def demarrer_procedure_reset_mdp(self, nom_utilisateur: str) -> tuple[bool, str | None, str | None]:
        """Démarre la procédure de réinitialisation de mot de passe par email."""
        # Note: La logique des codes de réinitialisation nécessiterait une table dédiée.
        # Pour cet exemple, nous nous basons sur l'email de l'utilisateur.
        user = user_model.obtenir_utilisateur_par_login_data(nom_utilisateur)
        if not user or not user.email:
            return False, None, "Utilisateur non trouvé ou email non configuré."

        from utils import email_utils
        code_reset = "12345"  # Ceci est un placeholder, une vraie logique de code serait nécessaire.
        if email_utils.envoyer_email_reset(user.email, nom_utilisateur, code_reset):
            return True, user.email, None
        else:
            print(f"Échec de l'envoi de l'email. Code pour {nom_utilisateur}: {code_reset}")
            return False, user.email, f"L'envoi de l'email a échoué. Code pour test: {code_reset}"

    def verifier_code_et_reinitialiser_mdp(self, nom_utilisateur: str, code_saisi: str, nouveau_mdp: str) -> tuple[
        bool, str | None]:
        if code_saisi == "12345":  # Placeholder
            update_data = UtilisateurUpdate(password=nouveau_mdp)
            success, _ = user_model.mettre_a_jour_utilisateur_data(nom_utilisateur, update_data)
            if success:
                return True, "Mot de passe réinitialisé avec succès."
            else:
                return False, "Erreur lors de la mise à jour du mot de passe."
        else:
            return False, "Code de réinitialisation invalide ou expiré."

    def get_user_data(self, login: str):
        """Récupère l'objet Pydantic d'un utilisateur."""
        return user_model.obtenir_utilisateur_par_login_data(login)

    def update_user_profile(self, login: str, new_email: str, old_password: str | None, new_password: str | None,
                            preferences: dict) -> tuple[bool, str]:
        """Met à jour le profil d'un utilisateur."""
        user = user_model.obtenir_utilisateur_par_login_data(login)
        if not user:
            return False, "Utilisateur non trouvé."

        if new_password:
            if not old_password or not password_utils.verifier_mdp(old_password, user.hashed_password):
                return False, "L'ancien mot de passe est incorrect."

        old_pfp_path = user.profile_picture_path
        new_pfp_path = preferences.get("profile_picture_path")

        if old_pfp_path and old_pfp_path != new_pfp_path:
            try:
                full_old_path = os.path.join(PROFILE_PICTURES_DIR, old_pfp_path)
                if os.path.exists(full_old_path):
                    os.remove(full_old_path)
            except OSError as e:
                print(f"Erreur lors de la suppression de l'ancienne photo de profil : {e}")

        update_data = UtilisateurUpdate(
            email=new_email,
            password=new_password if new_password else None,
            theme_color=preferences.get("theme_color"),
            default_filter=preferences.get("default_filter"),
            profile_picture_path=new_pfp_path
        )
        return user_model.mettre_a_jour_utilisateur_data(login, update_data)

    def remove_user_profile_picture(self, login: str) -> tuple[bool, str]:
        """Supprime la photo de profil d'un utilisateur."""
        user = user_model.obtenir_utilisateur_par_login_data(login)
        if not user:
            return False, "Utilisateur non trouvé."

        old_pfp_path = user.profile_picture_path
        if old_pfp_path:
            try:
                full_old_path = os.path.join(PROFILE_PICTURES_DIR, old_pfp_path)
                if os.path.exists(full_old_path):
                    os.remove(full_old_path)
            except OSError as e:
                return False, f"Erreur lors de la suppression du fichier image : {e}"

        update_data = UtilisateurUpdate(profile_picture_path="")
        return user_model.mettre_a_jour_utilisateur_data(login, update_data)

    def get_all_users_for_management(self) -> list[dict]:
        """Récupère tous les utilisateurs (sauf admin) pour la vue de gestion."""
        tous_les_utilisateurs = user_model.obtenir_tous_les_utilisateurs_data()
        liste_utilisateurs = []
        for user in tous_les_utilisateurs:
            if user.login != "admin":
                user_info = {
                    "login": user.login,
                    "email": user.email or "N/A",
                    "roles": user.roles
                }
                liste_utilisateurs.append(user_info)
        return sorted(liste_utilisateurs, key=lambda u: u["login"])

    def admin_delete_user(self, nom_utilisateur_a_supprimer: str) -> tuple[bool, str]:
        """Supprime un utilisateur (action admin)."""
        if nom_utilisateur_a_supprimer == "admin":
            return False, "Le compte administrateur principal 'admin' ne peut pas être supprimé."
        return user_model.supprimer_utilisateur_data(nom_utilisateur_a_supprimer)

    def admin_create_user(self, login: str, email: str, mot_de_passe: str, roles: list[str]) -> tuple[bool, str]:
        """Crée un utilisateur (action admin)."""
        if not all([login, email, mot_de_passe]):
            return False, "Login, email et mot de passe sont requis."
        if not login.strip() or not email.strip() or not mot_de_passe.strip():
            return False, "Login, email et mot de passe ne peuvent pas être vides."
        if login == "admin":
            return False, "Le login 'admin' est réservé."

        new_user = Utilisateur(
            login=login,
            hashed_password=password_utils.generer_hachage_mdp(mot_de_passe),
            email=email,
            roles=sorted(list(set(role for role in roles if role in ASSIGNABLE_ROLES)))
        )
        return user_model.ajouter_utilisateur_data(new_user)

    def admin_update_user_details(self, login_original: str, nouveau_login: str, new_email: str, new_roles: list[str],
                                  nouveau_mot_de_passe: str | None) -> tuple[bool, str]:
        """Met à jour un utilisateur (action admin)."""
        if login_original != nouveau_login:
            return False, "Le changement de login n'est pas supporté. Supprimez et recréez l'utilisateur si nécessaire."

        if not all([login_original, new_email]):
            return False, "Login et email sont requis."

        if login_original == "admin" and "admin" not in new_roles:
            new_roles.append("admin")

        valid_roles = sorted(list(set(role for role in new_roles if role in ASSIGNABLE_ROLES or role == "admin")))

        update_data = UtilisateurUpdate(
            email=new_email,
            roles=valid_roles,
            password=nouveau_mot_de_passe if nouveau_mot_de_passe else None
        )
        return user_model.mettre_a_jour_utilisateur_data(login_original, update_data)

    def get_role_descriptions_with_users(self) -> dict:
        """Récupère la description des rôles avec les utilisateurs assignés."""
        descriptions = ROLES_UTILISATEURS.copy()
        tous_utilisateurs = user_model.obtenir_tous_les_utilisateurs_data()

        for role_key in descriptions:
            descriptions[role_key]["utilisateurs_actuels"] = []

        for user in tous_utilisateurs:
            for role in user.roles:
                if role in descriptions:
                    descriptions[role]["utilisateurs_actuels"].append(user.login)

        for role_key in descriptions:
            descriptions[role_key]["utilisateurs_actuels"] = sorted(
                list(set(descriptions[role_key]["utilisateurs_actuels"])))

        return descriptions

    def get_assignable_roles(self) -> list[str]:
        return ASSIGNABLE_ROLES

    def get_smtp_config(self) -> dict:
        load_smtp_config()
        return SMTP_CONFIG.copy()

    def save_smtp_config(self, new_config_data: dict) -> tuple[bool, str]:
        return save_email_config_to_ini(new_config_data)

    def test_smtp_connection(self, config_to_test: dict) -> tuple[bool, str]:
        try:
            if config_to_test.get('use_ssl'):
                server = smtplib.SMTP_SSL(config_to_test['server'], int(config_to_test['port']), timeout=10)
            else:
                server = smtplib.SMTP(config_to_test['server'], int(config_to_test['port']), timeout=10)
                if config_to_test.get('use_tls'):
                    server.starttls()

            server.login(config_to_test['email_sender'], config_to_test['password'])
            server.quit()
            return True, "Connexion réussie."
        except Exception as e:
            return False, str(e)