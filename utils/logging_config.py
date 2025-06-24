# utils/logging_config.py
import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging():
    """
    Configure la journalisation pour l'application.
    - Écrit les logs de niveau INFO et supérieur dans un fichier rotatif.
    - Affiche les logs de niveau WARNING et supérieur dans la console.
    - Intercepte les exceptions non gérées pour les logger avant de quitter.
    """
    try:
        # Définir le chemin du fichier de log dans un dossier local pour garantir les droits d'écriture.
        log_dir = os.path.join(os.path.expanduser('~'), '.GestionRemboursements', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, 'app.log')

        # Formatter pour les logs
        log_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(threadName)s] - %(name)s (%(funcName)s): %(message)s'
        )

        # Handler pour le fichier (5MB par fichier, 3 fichiers de sauvegarde)
        file_handler = RotatingFileHandler(log_file_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
        file_handler.setFormatter(log_formatter)
        file_handler.setLevel(logging.INFO)

        # Handler pour la console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        # --- MODIFICATION ICI ---
        console_handler.setLevel(logging.DEBUG)

        # Configurer le logger root
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # On met aussi le root à DEBUG pour être sûr que rien n'est filtré en amont

        # Vider les anciens handlers pour éviter les duplications si la fonction est appelée plusieurs fois
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Gérer les exceptions non interceptées pour les logger
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            root_logger.critical("Exception non interceptée :", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = handle_exception

        root_logger.info("Le système de journalisation a été configuré avec succès.")
        root_logger.info(f"Les logs sont enregistrés dans : {log_file_path}")

    except Exception as e:
        print(f"ERREUR CRITIQUE: Impossible de configurer la journalisation : {e}", file=sys.stderr)