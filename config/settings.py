import os
import configparser
import sys

def get_application_base_path():
    """ Obtient le chemin de base de l'application, fonctionne pour le dev et pour l'exécutable PyInstaller. """
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        # Retourne le dossier parent du dossier 'config'
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

APP_ROOT_PATH = get_application_base_path()
CONFIG_DIR = os.path.join(APP_ROOT_PATH, "config")
os.makedirs(CONFIG_DIR, exist_ok=True)

# --- CONFIGURATION DES CHEMINS DE DONNÉES ---
PATH_CONFIG_FILE = os.path.join(CONFIG_DIR, "path_config.ini")

def load_custom_path() -> str | None:
    """Charge le chemin personnalisé depuis path_config.ini."""
    if not os.path.exists(PATH_CONFIG_FILE):
        return None
    config = configparser.ConfigParser()
    try:
        config.read(PATH_CONFIG_FILE, encoding='utf-8')
        custom_path = config.get('Path', 'shared_data_base_path', fallback=None)
        return custom_path
    except Exception:
        return None

def save_custom_path(path: str) -> bool:
    """Sauvegarde le chemin personnalisé dans path_config.ini."""
    config = configparser.ConfigParser()
    config['Path'] = {'shared_data_base_path': path}
    try:
        with open(PATH_CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        return True
    except IOError:
        return False

# Charge le chemin personnalisé ou utilise le chemin par défaut.
SHARED_DATA_BASE_PATH_DEFAULT = "Z:\\REMBOURSEMENT"
SHARED_DATA_BASE_PATH = load_custom_path() or SHARED_DATA_BASE_PATH_DEFAULT

# MODE DÉVELOPPEMENT LOCAL (décommenter pour tester en local)
# DEV_MODE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "donnees_partagees_mock")
# SHARED_DATA_BASE_PATH = DEV_MODE_PATH

IS_DEPLOYMENT_MODE = not SHARED_DATA_BASE_PATH.endswith("donnees_partagees_mock")

# --- Sous-dossiers de données (dérivés de SHARED_DATA_BASE_PATH) ---
REMBOURSEMENTS_BASE_DIR = os.path.join(SHARED_DATA_BASE_PATH, "remboursements")
REMBOURSEMENTS_ATTACHMENTS_DIR = os.path.join(REMBOURSEMENTS_BASE_DIR, "fichiers")
PROFILE_PICTURES_DIR = os.path.join(SHARED_DATA_BASE_PATH, "assets", "profile_pictures")
REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR = os.path.join(REMBOURSEMENTS_BASE_DIR, "archive", "fichiers")

# --- Fichiers de configuration et de statut ---
DATABASE_FILE = os.path.join(SHARED_DATA_BASE_PATH, "remboursements.db")
DB_LOCK_FILE = os.path.join(SHARED_DATA_BASE_PATH, "remboursements.db.lock")
DB_REFRESH_FLAG_FILE = os.path.join(SHARED_DATA_BASE_PATH, "refresh_required.flag")
CONFIG_EMAIL_FILE = os.path.join(CONFIG_DIR, "config_email.ini")
SMTP_CONFIG = {}


# --- Statuts des demandes de remboursement ---
STATUT_ANNULEE = "0. Demande Annulée"
STATUT_CREEE = "1. Créée (en attente constat trop-perçu)"
STATUT_REFUSEE_CONSTAT_TP = "1b. Refusée par Compta. Trésorerie (action P. Neri)"
STATUT_TROP_PERCU_CONSTATE = "2. Trop-perçu constaté (en attente validation)"
STATUT_VALIDEE = "3. Validée (en attente de paiement)"
STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO = "3b. Refusée - Validation (action M. Lupo)"
STATUT_PAIEMENT_EFFECTUE = "4. Paiement effectué (Terminée)"

# --- Rôles Utilisateurs et Descriptions Détaillées ---
ROLES_UTILISATEURS = {
    "demandeur": {
        "description": "Responsable de l'initiation des demandes de remboursement pour les clients.\n"
                       "Actions possibles :\n"
                       "  - Créer une nouvelle demande de remboursement.\n"
                       "  - Joindre la facture du client (optionnel) et le RIB (obligatoire).\n"
                       "  - Rédiger une description initiale de la demande.\n"
                       "  - Annuler une demande qui lui a été retournée après un refus.",
        "utilisateurs_actuels": []
    },
    "comptable_tresorerie": {
        "description": "Chargé de vérifier le trop-perçu sur les comptes de l'hôpital.\n"
                       "Actions possibles :\n"
                       "  - Consulter les demandes en attente de constat.\n"
                       "  - Ajouter une pièce jointe (capture d'écran du trop-perçu, preuve comptable).\n"
                       "  - Ajouter un commentaire.\n"
                       "  - Accepter le constat et envoyer la demande pour validation.\n"
                       "  - Refuser le constat (avec commentaire) et renvoyer la demande au demandeur initial (P. Neri).\n"
                       "  - Corriger et resoumettre un constat après un refus de la validation.",
        "utilisateurs_actuels": []
    },
    "validateur_chef": {
        "description": "Valide les demandes après le constat du trop-perçu.\n"
                       "Actions possibles :\n"
                       "  - Consulter les demandes avec trop-perçu constaté.\n"
                       "  - Vérifier la capture d'écran du trop-perçu et la présence du RIB.\n"
                       "  - Ajouter un commentaire (optionnel pour validation, obligatoire pour refus).\n"
                       "  - Valider la demande et l'envoyer pour paiement.\n"
                       "  - Refuser la validation (avec commentaire) et renvoyer la demande au comptable trésorerie (M. Lupo) pour correction.",
        "utilisateurs_actuels": []
    },
    "comptable_fournisseur": {
        "description": "Effectue le paiement final des demandes validées.\n"
                       "Actions possibles :\n"
                       "  - Consulter les demandes validées et en attente de paiement.\n"
                       "  - Confirmer que le paiement a été effectué.\n"
                       "  - Ajouter un commentaire (optionnel) lors de la confirmation du paiement.",
        "utilisateurs_actuels": []
    },
    "visualiseur_seul": {
        "description": "Peut uniquement consulter la liste des demandes et leurs détails.\n"
                       "Actions possibles :\n"
                       "  - Voir toutes les demandes et leur statut actuel.\n"
                       "  - Consulter les pièces jointes (factures, RIBs, preuves de trop-perçu).\n"
                       "  - Ne peut effectuer aucune action de modification ou de changement de statut.",
        "utilisateurs_actuels": []
    },
    "admin": {
        "description": "Dispose de tous les droits des autres rôles, plus des droits d'administration spécifiques.\n"
                       "Actions possibles (en plus des autres rôles) :\n"
                       "  - Supprimer n'importe quelle demande de remboursement.\n"
                       "  - Gérer les comptes utilisateurs (créer, modifier, supprimer - sauf son propre compte 'admin').\n"
                       "  - Assigner/Modifier les rôles des autres utilisateurs.",
        "utilisateurs_actuels": []
    }
}
ASSIGNABLE_ROLES = ["demandeur", "comptable_tresorerie", "validateur_chef", "comptable_fournisseur", "visualiseur_seul"]


def load_smtp_config():
    global SMTP_CONFIG
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_EMAIL_FILE):
        config.read(CONFIG_EMAIL_FILE, encoding='utf-8')
        if 'SMTP' in config:
            SMTP_CONFIG = dict(config.items('SMTP'))
            if 'port' in SMTP_CONFIG:
                try:
                    SMTP_CONFIG['port'] = int(SMTP_CONFIG['port'])
                except ValueError:
                    SMTP_CONFIG['port'] = 587
            for key in ['use_tls', 'use_ssl']:
                if key in SMTP_CONFIG:
                    SMTP_CONFIG[key] = str(SMTP_CONFIG[key]).lower() in ('true', '1', 't', 'on', 'yes')
    if not SMTP_CONFIG:
        print("ATTENTION: Fichier de configuration email manquant ou invalide. Les fonctionnalités d'email seront désactivées.")
        SMTP_CONFIG = {}

def save_email_config_to_ini(new_config: dict) -> tuple[bool, str]:
    config = configparser.ConfigParser()
    config['SMTP'] = new_config
    try:
        with open(CONFIG_EMAIL_FILE, 'w', encoding='utf-8') as configfile:
            config.write(configfile)
        load_smtp_config()
        return True, "Configuration enregistrée avec succès."
    except IOError as e:
        return False, f"Erreur lors de l'écriture du fichier de configuration : {e}"

def ensure_shared_dirs_exist():
    # Vérifie si le chemin de base lui-même est accessible avant de créer les sous-dossiers.
    if not os.path.exists(SHARED_DATA_BASE_PATH):
        # Le chemin de base n'existe pas, on ne peut rien faire.
        # L'erreur sera gérée au démarrage de l'application.
        return

    dirs_to_create = [
        REMBOURSEMENTS_ATTACHMENTS_DIR,
        PROFILE_PICTURES_DIR,
        REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR
    ]
    for directory in dirs_to_create:
        os.makedirs(directory, exist_ok=True)