import sqlite3
import logging
from typing import List, Optional, Tuple
from models.schemas import Utilisateur, UtilisateurUpdate
from utils.database_manager import db_connection, execute_in_queue, handle_db_locks
from utils.password_utils import generer_hachage_mdp

_log = logging.getLogger(__name__)


@handle_db_locks
def obtenir_tous_les_utilisateurs_data() -> List[Utilisateur]:
    """Récupère tous les utilisateurs et leurs rôles depuis la base de données."""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT u.login,
                              u.hashed_password,
                              u.email,
                              u.theme_color,
                              u.default_filter,
                              u.profile_picture_path,
                              GROUP_CONCAT(r.role_name) as roles
                       FROM utilisateurs u
                                LEFT JOIN utilisateur_roles ur ON u.login = ur.login
                                LEFT JOIN roles r ON ur.role_id = r.role_id
                       GROUP BY u.login
                       """)
        users_rows = cursor.fetchall()

    utilisateurs = []
    for row in users_rows:
        user_data = dict(row)
        user_data['roles'] = user_data['roles'].split(',') if user_data['roles'] else []
        utilisateurs.append(Utilisateur(**user_data))

    return utilisateurs


@handle_db_locks
def obtenir_utilisateur_par_login_data(login: str) -> Optional[Utilisateur]:
    """Récupère un utilisateur spécifique par son login."""
    users = obtenir_tous_les_utilisateurs_data()
    for user in users:
        if user.login == login:
            return user
    return None


@execute_in_queue
def ajouter_utilisateur_data(user_create: Utilisateur) -> Tuple[bool, str]:
    """Ajoute un nouvel utilisateur à la base de données."""
    with db_connection() as conn:
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT login FROM utilisateurs WHERE login = ?", (user_create.login,))
                if cursor.fetchone():
                    return False, "Le login de l'utilisateur existe déjà."

                cursor.execute("""
                               INSERT INTO utilisateurs (login, hashed_password, email, theme_color, default_filter,
                                                         profile_picture_path)
                               VALUES (?, ?, ?, ?, ?, ?)
                               """, (
                                   user_create.login,
                                   user_create.hashed_password,
                                   user_create.email,
                                   user_create.theme_color,
                                   user_create.default_filter,
                                   user_create.profile_picture_path
                               ))

                for role_name in user_create.roles:
                    cursor.execute("INSERT OR IGNORE INTO roles (role_name) VALUES (?)", (role_name,))
                    cursor.execute("SELECT role_id FROM roles WHERE role_name = ?", (role_name,))
                    role_id = cursor.fetchone()['role_id']
                    cursor.execute("INSERT INTO utilisateur_roles (login, role_id) VALUES (?, ?)",
                                   (user_create.login, role_id))

            return True, "Utilisateur ajouté avec succès."
        except sqlite3.Error as e:
            _log.error(f"Erreur lors de l'ajout de l'utilisateur {user_create.login}", exc_info=True)
            return False, f"Erreur de base de données : {e}"


@execute_in_queue
def mettre_a_jour_utilisateur_data(login: str, user_update: UtilisateurUpdate) -> Tuple[bool, str]:
    """Met à jour les informations d'un utilisateur existant."""
    with db_connection() as conn:
        try:
            with conn:
                cursor = conn.cursor()

                update_fields = user_update.model_dump(exclude_unset=True)

                if 'password' in update_fields and update_fields['password']:
                    update_fields['hashed_password'] = generer_hachage_mdp(update_fields.pop('password'))
                elif 'password' in update_fields:
                    del update_fields['password']

                if 'roles' in update_fields:
                    new_roles = update_fields.pop('roles')
                    cursor.execute("DELETE FROM utilisateur_roles WHERE login = ?", (login,))
                    for role_name in new_roles:
                        cursor.execute("INSERT OR IGNORE INTO roles (role_name) VALUES (?)", (role_name,))
                        cursor.execute("SELECT role_id FROM roles WHERE role_name = ?", (role_name,))
                        role_id = cursor.fetchone()['role_id']
                        cursor.execute("INSERT INTO utilisateur_roles (login, role_id) VALUES (?, ?)", (login, role_id))

                if update_fields:
                    set_clause = ", ".join([f"{key} = ?" for key in update_fields.keys()])
                    params = list(update_fields.values())
                    params.append(login)

                    cursor.execute(f"UPDATE utilisateurs SET {set_clause} WHERE login = ?", tuple(params))

            return True, "Utilisateur mis à jour avec succès."
        except sqlite3.Error as e:
            _log.error(f"Erreur lors de la mise à jour de l'utilisateur {login}", exc_info=True)
            return False, f"Erreur de base de données : {e}"


@execute_in_queue
def supprimer_utilisateur_data(login: str) -> Tuple[bool, str]:
    """Supprime un utilisateur de la base de données."""
    with db_connection() as conn:
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM utilisateurs WHERE login = ?", (login,))
                if cursor.rowcount == 0:
                    return False, "Utilisateur non trouvé."
            return True, "Utilisateur supprimé avec succès."
        except sqlite3.Error as e:
            _log.error(f"Erreur lors de la suppression de l'utilisateur {login}", exc_info=True)
            return False, f"Erreur de base de données : {e}"