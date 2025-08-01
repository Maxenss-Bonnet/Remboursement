# Gestion des Remboursements

![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)

## Description

Ce projet est une application de bureau conçue pour gérer et suivre les demandes de remboursement au sein de l'entreprise. Elle vise à remplacer les processus manuels basés sur des fichiers Excel en offrant une solution centralisée, multi-utilisateurs et sécurisée, avec un workflow de validation clair et une traçabilité complète.

## Fonctionnalités Principales

-   **Gestion des Demandes :** Création, modification et suivi des demandes de remboursement.
-   **Workflow de Validation :** Un processus de validation en plusieurs étapes (Comptabilité, Direction) avec des statuts clairs pour chaque demande.
-   **Gestion des Utilisateurs :** Différents rôles (Utilisateur, Comptabilité, Direction, Admin) avec des permissions spécifiques.
-   **Administration :** Un panneau d'administration pour gérer les utilisateurs, configurer l'application et effectuer des sauvegardes.
-   **Visualisation de Documents :** Visionneuse de PDF intégrée pour consulter les factures et autres pièces jointes.
-   **Notifications :** Système de notifications pour informer les utilisateurs des changements de statut.
-   **Archivage :** Fonctionnalité pour archiver les anciennes demandes et maintenir la base de données performante.

## Architecture du Projet

L'application est construite sur une architecture **Modèle-Vue-Contrôleur (MVC)** pour garantir une séparation claire des préoccupations et faciliter la maintenance :

-   **Modèles (`/models`) :** Gèrent les données de l'application, la logique métier et les interactions avec la base de données (SQLite). Ils encapsulent les règles de validation et le workflow des remboursements.
-   **Vues (`/views`) :** Composent l'interface utilisateur graphique avec laquelle les utilisateurs interagissent. Construites avec le framework `CustomTkinter`, elles sont responsables de l'affichage des données et de la capture des actions de l'utilisateur.
-   **Contrôleurs (`/controllers`) :** Agissent comme un pont entre les Modèles et les Vues. Ils reçoivent les entrées de l'utilisateur depuis les Vues, les traitent en utilisant la logique des Modèles, et mettent à jour les Vues en conséquence.

## Installation et Lancement

### Prérequis

-   [Python 3.9+](https://www.python.org/downloads/)
-   [Git](https://git-scm.com/downloads)

### Étapes d'installation

1.  **Clonez le dépôt :**
    ```bash
    git clone <URL_DU_DEPOT>
    cd Gestion-des-Remboursements
    ```

2.  **Créez et activez un environnement virtuel :**
    ```bash
    # Pour Windows
    python -m venv venv
    .\venv\Scripts\activate

    # Pour macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Installez les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```

### Lancement de l'application

Une fois l'installation terminée, lancez l'application avec la commande suivante :
```bash
python app.py
```

## Génération de l'Exécutable

Pour distribuer l'application en tant que fichier exécutable unique (`.exe`) qui n'exige pas l'installation de Python ou des dépendances sur la machine cible, vous pouvez utiliser `PyInstaller`.

Exécutez la commande suivante à la racine du projet :
```bash
pyinstaller --name="Gestion Remboursements" --windowed --onefile --icon="assets/app_icon.ico" app.py
```
L'exécutable sera généré dans le sous-dossier `dist`.

## Documentation Complète

Pour une compréhension plus approfondie du projet, veuillez consulter les documents suivants :

-   [Consulter la Documentation Technique](https://docs.google.com/document/d/1HIvCOQ9TCSJUL8HSrty9yRtnLkq8A_ixqQSrT48LHrg/edit?usp=sharing)
-   [Consulter le Manuel d'Utilisation](https://docs.google.com/document/d/1dgBCOMLEQoBefkS0CEpGwQwAgd5vfaaEyrULsKfCOBw/edit?usp=sharing)