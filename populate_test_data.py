import os
import datetime
import uuid
import random
import re
from tqdm import tqdm

# Ajoute le chemin du projet au PYTHONPATH pour permettre les imports relatifs
import sys

sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from models.schemas import Remboursement, HistoriqueStatut
from models.remboursement_data import creer_demande_data
from utils.database_manager import create_tables
from config.settings import (
    STATUT_CREEE, STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE, STATUT_PAIEMENT_EFFECTUE,
    STATUT_ANNULEE
)

# --- CONFIGURATION ---
NOMBRE_DEMANDES_A_CREER = 100
UTILISATEUR_CREATEUR = "p.neri"  # Utilisateur qui sera marqué comme créateur des demandes

# --- DONNÉES FICTIVES ---
NOMS = ["MARTIN", "BERNARD", "DUBOIS", "THOMAS", "ROBERT", "RICHARD", "PETIT", "DURAND"]
PRENOMS = ["Marie", "Jean", "Sophie", "Pierre", "Camille", "Nicolas", "Julie", "Lucas"]
STATUTS_POSSIBLES = [
    STATUT_CREEE,
    STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE,
    STATUT_PAIEMENT_EFFECTUE,
    STATUT_ANNULEE
]


def _sanitize_for_filename(text: str) -> str:
    """Petite fonction utilitaire pour nettoyer les noms de fichiers."""
    return re.sub(r'[\\/*?:"<>|]', "_", text).replace(" ", "_")


def creer_demandes_fictives(nombre_a_creer: int):
    """
    Fonction principale pour générer et insérer les demandes dans la BDD.
    """
    print(f"Lancement de la création de {nombre_a_creer} demandes de test...")

    # S'assure que les tables existent dans la base de données
    try:
        create_tables()
        print("Vérification des tables de la base de données... OK.")
    except Exception as e:
        print(f"ERREUR: Impossible d'initialiser la base de données : {e}")
        return

    for i in tqdm(range(nombre_a_creer), desc="Création des demandes"):
        # Génération des données aléatoires
        nom_patient = random.choice(NOMS)
        prenom_patient = random.choice(PRENOMS)
        montant = round(random.uniform(20.5, 850.99), 2)
        statut_actuel = random.choice(STATUTS_POSSIBLES)

        # Génère une date aléatoire sur les 2 dernières années
        jours_en_arriere = random.randint(1, 730)
        date_creation = datetime.datetime.now() - datetime.timedelta(days=jours_en_arriere)

        id_unique = f"D{date_creation.strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:4]}"
        ref_facture = f"FTEST-{date_creation.year}-{random.randint(1000, 9999)}"
        ref_facture_dossier = f"{_sanitize_for_filename(ref_facture)}_{id_unique}"
        description = f"Demande de test N°{i + 1} pour {prenom_patient} {nom_patient}."

        # Création de l'objet Remboursement (schéma Pydantic)
        demande = Remboursement(
            id_demande=id_unique,
            nom=nom_patient,
            prenom=prenom_patient,
            reference_facture=ref_facture,
            reference_facture_dossier=ref_facture_dossier,
            description=description,
            montant_demande=montant,
            chemins_factures_stockees=[],  # Vide, comme demandé
            chemins_rib_stockes=[],  # Vide, comme demandé
            chemins_trop_percu_stockees=[],  # Vide, comme demandé
            statut=statut_actuel,
            cree_par=UTILISATEUR_CREATEUR,
            date_creation=date_creation,
            derniere_modification_par=UTILISATEUR_CREATEUR,
            date_derniere_modification=date_creation + datetime.timedelta(hours=random.randint(1, 24)),
            historique_statuts=[
                HistoriqueStatut(
                    statut=statut_actuel,
                    date=date_creation,
                    par_utilisateur=UTILISATEUR_CREATEUR,
                    commentaire=description
                )
            ],
            # Si le statut est "terminé", on met une date de paiement
            date_paiement_effectue=date_creation + datetime.timedelta(
                days=7) if statut_actuel == STATUT_PAIEMENT_EFFECTUE else None,
            is_archived=True if random.random() < 0.1 else False  # 10% de chance d'être archivé
        )

        # Insertion dans la base de données via la couche d'accès aux données
        succes, message = creer_demande_data(demande)
        if not succes:
            print(f"\nErreur lors de la création de la demande {i + 1}: {message}")

    print(f"\nCréation de {nombre_a_creer} demandes terminée.")


if __name__ == "__main__":
    creer_demandes_fictives(NOMBRE_DEMANDES_A_CREER)