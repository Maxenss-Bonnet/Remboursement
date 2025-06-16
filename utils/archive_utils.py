# utils/archive_utils.py
import os
import shutil
from typing import Tuple


def create_archive_for_demande(dossier_source: str, dossier_archive: str, nom_dossier_demande: str) -> Tuple[bool, str]:
    """
    Crée une archive ZIP à partir du dossier source et la place dans le dossier d'archive.
    Supprime le dossier source si l'archivage réussit.

    Args:
        dossier_source (str): Le chemin complet du dossier à archiver.
        dossier_archive (str): Le chemin du répertoire où stocker l'archive.
        nom_dossier_demande (str): Le nom du dossier de la demande, qui servira de nom à l'archive.

    Returns:
        Tuple[bool, str]: Un tuple contenant un booléen de succès et un message.
    """
    if not os.path.isdir(dossier_source):
        return False, f"Le dossier source n'existe pas : {dossier_source}"

    os.makedirs(dossier_archive, exist_ok=True)

    chemin_archive_zip = os.path.join(dossier_archive, nom_dossier_demande)

    try:
        # Créer l'archive (shutil créera un .zip)
        shutil.make_archive(base_name=chemin_archive_zip,
                            format='zip',
                            root_dir=dossier_source)

        # Si la création de l'archive réussit, supprimer le dossier original
        shutil.rmtree(dossier_source)

        return True, f"Archive créée avec succès : {chemin_archive_zip}.zip"
    except Exception as e:
        # En cas d'erreur, s'assurer que l'archive potentiellement incomplète est supprimée
        if os.path.exists(f"{chemin_archive_zip}.zip"):
            os.remove(f"{chemin_archive_zip}.zip")
        return False, f"Erreur lors de la création de l'archive : {e}"