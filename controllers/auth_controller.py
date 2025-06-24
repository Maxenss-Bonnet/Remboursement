import random
import string
import datetime

from models import user_model
from utils import password_utils
from models.schemas import UtilisateurUpdate
from controllers.user_controller import UserController


class AuthController:
    def __init__(self):
        self.reset_codes = {}
        self.user_controller = UserController()

    def tenter_connexion(self, nom_utilisateur: str, mot_de_passe_saisi: str) -> str | None:
        user = self.user_controller.get_user_data(nom_utilisateur)
        if user and password_utils.verifier_mdp(mot_de_passe_saisi, user.hashed_password):
            return nom_utilisateur
        return None

    def modifier_mot_de_passe(self, nom_utilisateur: str, ancien_mdp: str, nouveau_mdp: str) -> bool:
        user = self.user_controller.get_user_data(nom_utilisateur)
        if not user or not password_utils.verifier_mdp(ancien_mdp, user.hashed_password):
            return False

        update_data = UtilisateurUpdate(password=nouveau_mdp)
        success, _ = user_model.mettre_a_jour_utilisateur_data(nom_utilisateur, update_data)
        return success

    def demarrer_procedure_reset_mdp(self, nom_utilisateur: str) -> tuple[bool, str | None, str | None]:
        user = self.user_controller.get_user_data(nom_utilisateur)
        if not user or not user.email:
            return False, None, "Utilisateur non trouvé ou email non configuré."

        from utils import email_utils
        code_reset = ''.join(random.choices(string.digits, k=6))
        expiry_time = datetime.datetime.now() + datetime.timedelta(minutes=5)
        self.reset_codes[nom_utilisateur] = (code_reset, expiry_time)

        if email_utils.envoyer_email_reset(user.email, nom_utilisateur, code_reset):
            return True, user.email, None
        else:
            print(f"Échec de l'envoi de l'email. Code pour {nom_utilisateur}: {code_reset}")
            return False, user.email, f"L'envoi de l'email a échoué. Code pour test: {code_reset}"

    def verifier_code_et_reinitialiser_mdp(self, nom_utilisateur: str, code_saisi: str, nouveau_mdp: str) -> tuple[
        bool, str | None]:
        if nom_utilisateur not in self.reset_codes:
            return False, "Aucune demande de réinitialisation en cours pour cet utilisateur."

        stored_code, expiry_time = self.reset_codes[nom_utilisateur]

        if datetime.datetime.now() > expiry_time:
            del self.reset_codes[nom_utilisateur]
            return False, "Le code de réinitialisation a expiré."

        if code_saisi == stored_code:
            update_data = UtilisateurUpdate(password=nouveau_mdp)
            success, _ = user_model.mettre_a_jour_utilisateur_data(nom_utilisateur, update_data)
            del self.reset_codes[nom_utilisateur]
            if success:
                return True, "Mot de passe réinitialisé avec succès."
            else:
                return False, "Erreur lors de la mise à jour du mot de passe."
        else:
            return False, "Code de réinitialisation invalide."