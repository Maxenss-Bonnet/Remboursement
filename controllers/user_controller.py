import os
import logging
from models import user_model
from utils import password_utils
from config.settings import (
    ROLES_UTILISATEURS,
    ASSIGNABLE_ROLES,
    PROFILE_PICTURES_DIR
)
from models.schemas import Utilisateur, UtilisateurUpdate
from utils.cache_manager import CacheManager

_log = logging.getLogger(__name__)


class UserController:
    def get_user_data(self, login: str):
        return user_model.obtenir_utilisateur_par_login_data(login)

    def get_all_users(self):
        return user_model.obtenir_tous_les_utilisateurs_data()

    def update_user_profile(self, login: str, new_email: str, old_password: str | None, new_password: str | None,
                            preferences: dict, cache_manager: CacheManager) -> tuple[bool, str]:
        user = user_model.obtenir_utilisateur_par_login_data(login)
        if not user:
            return False, "Utilisateur non trouvé."

        if new_password:
            if not old_password or not password_utils.verifier_mdp(old_password, user.hashed_password):
                return False, "L'ancien mot de passe est incorrect."

        old_pfp_path = user.profile_picture_path
        new_pfp_path = preferences.get("profile_picture_path")

        pfp_changed = old_pfp_path != new_pfp_path

        if old_pfp_path and pfp_changed:
            try:
                full_old_path = os.path.join(PROFILE_PICTURES_DIR, old_pfp_path)
                if os.path.exists(full_old_path):
                    os.remove(full_old_path)
            except OSError as e:
                _log.error(f"Erreur lors de la suppression de l'ancienne photo de profil : {e}", exc_info=True)

        update_data = UtilisateurUpdate(
            email=new_email,
            password=new_password if new_password else None,
            theme_color=preferences.get("theme_color"),
            default_filter=preferences.get("default_filter"),
            profile_picture_path=new_pfp_path
        )
        success, message = user_model.mettre_a_jour_utilisateur_data(login, update_data)

        if success and pfp_changed:
            cache_manager.invalidate_pfp_cache(login)

        return success, message

    def remove_user_profile_picture(self, login: str, cache_manager: CacheManager) -> tuple[bool, str]:
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
        success, message = user_model.mettre_a_jour_utilisateur_data(login, update_data)

        if success:
            cache_manager.invalidate_pfp_cache(login)

        return success, message

    def get_all_users_for_management(self) -> list[dict]:
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
        if nom_utilisateur_a_supprimer == "admin":
            return False, "Le compte administrateur principal 'admin' ne peut pas être supprimé."
        return user_model.supprimer_utilisateur_data(nom_utilisateur_a_supprimer)

    def admin_create_user(self, login: str, email: str, mot_de_passe: str, roles: list[str]) -> tuple[bool, str]:
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