import customtkinter as ctk
import webbrowser
from config.settings import ROLES_UTILISATEURS
from views.mixins.animation_mixin import AnimationMixin

COULEUR_ACTIVE_POUR_UTILISATEUR = "#1E4D2B"
COULEUR_DEMANDE_TERMINEE = "#2E4374"
COULEUR_DEMANDE_ANNULEE = "#6A040F"

# Descriptions détaillées extraites du document "Notice d'utilisation"
ROLE_DESCRIPTIONS_DETAILLES = {
    "demandeur": """Votre mission est de créer et soumettre une demande de remboursement pour une dépense que vous avez engagée.

Comment créer une nouvelle demande ?
Cliquez sur le bouton ➕ Nouvelle Demande . Une nouvelle fenêtre s'ouvre.

💡 ASTUCE MAGIQUE !
Avant de remplir les champs, joignez votre facture en PDF en premier en cliquant sur 📎 Joindre un fichier. Si le PDF contient les informations, l'application peut remplir automatiquement pour vous les champs "Prénom", "Nom" et "Référence facture" ! Un vrai gain de temps !

Remplissez (ou vérifiez) les informations :
- Prénom du demandeur / Nom du demandeur
- Référence facture : Le numéro ou la référence unique de la facture.
- Montant total : Le montant exact TTC de la dépense.
- Description : Soyez clair (ex: "Déjeuner client M. Dupont", "Achat fournitures de bureau").

Validez en cliquant sur Créer la demande. Une fois créée, votre demande a le statut Soumise et part à l'étape suivante.

Que faire si ma demande est Rejetée ?
Un commentaire vous expliquera pourquoi. Vous pourrez alors cliquer sur l'icône "Resoumettre" 🔁 pour la corriger et la renvoyer dans le circuit.""",

    "comptable_tresorerie": """Votre mission est d'effectuer une première vérification des demandes soumises.
Vous avez deux options :
✅ Valider : Vous confirmez que la demande est prête pour la validation finale. Le statut passe à En cours de validation et la demande est transmise au "Validateur Chef".
❌ Rejeter : Si la demande n'est pas conforme, vous la rejetez en laissant un commentaire. Le statut passe à Rejetée et la demande est retournée au "Demandeur".""",

    "validateur_chef": """Votre mission est d'approuver ou de refuser définitivement les dépenses.
Vous avez deux options :
👍 Approuver : Tout est en ordre. La demande est validée. Le statut passe à Validée par chef et la demande est transmise au service suivant pour paiement.
👎 Rejeter : La dépense n'est pas autorisée. Laissez un commentaire pour expliquer la raison. Le statut passe à Rejetée et la demande est retournée au "Demandeur".""",

    "comptable_fournisseur": """Votre mission est de traiter les demandes approuvées pour effectuer le remboursement.
📝 Faire un constat d'acceptation : Cliquez sur ce bouton pour générer un document interne. Le statut passe à Constat d'acceptation créé.
💰 Marquer comme "Payée" : Une fois le virement effectué, cliquez sur ce bouton pour clôturer la demande. Le statut passe à Payée.""",

    "visualiseur_seul": ROLES_UTILISATEURS.get("visualiseur_seul", {}).get("description", "Aucune description détaillée."),

    "admin": """En tant qu'administrateur, vous ne disposez pas d'un panneau de contrôle unique, mais de boutons et de menus supplémentaires qui apparaissent dans l'application. Ces options avancées vous donnent des droits étendus pour gérer les utilisateurs, la configuration et la maintenance de l'application.

🧑‍🤝‍🧑 Gestion des Utilisateurs
C'est ici que vous gérez les accès à l'application.
- Ajouter un utilisateur : Cliquez sur ➕ Ajouter un utilisateur. Remplissez les informations et attribuez-lui un rôle.
- Modifier un utilisateur : Sélectionnez un utilisateur et cliquez sur ✏️ Modifier l'utilisateur pour changer ses informations ou son rôle.
- Supprimer un utilisateur : Attention : Cette action est définitive et irréversible. Sélectionnez l'utilisateur et cliquez sur ➖ Supprimer l'utilisateur.

💾 Maintenance et Sauvegardes
Cette section est cruciale pour la sécurité de vos données.
- Lancer une sauvegarde (Backup) : Crée une archive .zip complète de la base de données et des pièces jointes.
- Restaurer une sauvegarde : Attention : Action irréversible qui remplacera toutes les données actuelles !
- Réorganiser la base de données (Vacuum) : Optimise le fichier de la base de données et peut réduire sa taille.
- Purger les anciennes archives : Supprime les fichiers d'archives et de sauvegardes (.zip) anciens pour libérer de l'espace.

🗄️ Gestion des Archives
- Archivage Automatique : Les demandes payées depuis plus d'un an sont archivées automatiquement.
- Archivage Manuel : Le bouton Archiver sur chaque demande est réservé aux administrateurs pour archiver manuellement des demandes "Payées".
- Consulter les archives : Permet d'ouvrir une archive .zip pour consulter les demandes qu'elle contient."""
}


class HelpView(ctk.CTkToplevel, AnimationMixin):
    def __init__(self, master, current_user_name: str, user_roles: list):
        super().__init__(master)
        AnimationMixin.__init__(self, master)

        self.current_user_name = current_user_name
        self.user_roles = user_roles

        self.title("Aide - Gestion des Remboursements")
        self.geometry("800x700")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(550, 450)
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(expand=True, fill="both")
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        scrollable_frame = ctk.CTkScrollableFrame(main_frame)
        scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        scrollable_frame.grid_columnconfigure(0, weight=1)

        intro_label = ctk.CTkLabel(scrollable_frame,
                                   text="Bienvenue dans l'Application de Gestion des Remboursements !",
                                   font=ctk.CTkFont(size=18, weight="bold"))
        intro_label.pack(pady=(0, 10), anchor="w", fill="x")

        intro_text = (
            "Cette application vous permet de suivre et de gérer le processus de remboursement des trop-perçus "
            "clients. Chaque utilisateur a des actions spécifiques en fonction de son rôle.")
        ctk.CTkLabel(scrollable_frame, text=intro_text, wraplength=720, justify="left").pack(anchor="w",
                                                                                             pady=(0, 15),
                                                                                             fill="x")

        self._creer_legende(scrollable_frame)

        ctk.CTkLabel(scrollable_frame, text="Fonctionnalités selon votre/vos rôle(s) :",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(15, 5), anchor="w")

        displayed_roles_help = set()

        # Afficher les rôles normaux en premier
        for role in sorted(self.user_roles):
            if role != 'admin' and role in ROLE_DESCRIPTIONS_DETAILLES and role not in displayed_roles_help:
                self._display_role_help(scrollable_frame, role)
                displayed_roles_help.add(role)

        # Afficher l'aide pour l'admin à la fin s'il a ce rôle
        if "admin" in self.user_roles and "admin" not in displayed_roles_help:
            self._display_role_help(scrollable_frame, "admin")
            displayed_roles_help.add("admin")

        if not displayed_roles_help:
            ctk.CTkLabel(scrollable_frame,
                         text="Aucune fonctionnalité spécifique à votre rôle principal n'est détaillée ici, "
                              "vous avez probablement un accès général ou de visualisation.",
                         wraplength=720, justify="left").pack(anchor="w", pady=(0, 15))

        # --- Boutons en bas ---
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=1, column=0, sticky="ew", padx=15, pady=10)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)

        ctk.CTkButton(button_frame, text="Ouvrir la notice complète en ligne", command=self._open_online_notice,
                      fg_color="#1D8348").grid(row=0, column=0, sticky="w", padx=5)

        ctk.CTkButton(button_frame, text="Fermer", command=self.close_animated, width=100).grid(row=0, column=2,
                                                                                                sticky="e",
                                                                                                padx=5)
        self.fade_in()

    def _display_role_help(self, parent, role):
        role_title = role.replace('_', ' ').title()
        ctk.CTkLabel(parent, text=f"En tant que {role_title} :",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 2), anchor="w")

        description_text = ROLE_DESCRIPTIONS_DETAILLES.get(role, "Aucune description détaillée disponible.")
        desc_label = ctk.CTkLabel(parent, text=description_text, wraplength=700, justify="left")
        desc_label.pack(fill="x", padx=(10, 0), pady=(0, 10), anchor="w")

    def _open_online_notice(self):
        """Ouvre le lien du Google Docs dans le navigateur par défaut."""
        try:
            webbrowser.open("https://docs.google.com/document/d/1dgBCOMLEQoBefkS0CEpGwQwAgd5vfaaEyrULsKfCOBw/edit?usp=sharing")
        except Exception as e:
            # Gérer le cas où le navigateur ne peut pas être ouvert
            print(f"Erreur lors de l'ouverture du lien : {e}")

    def _creer_legende(self, parent_frame):
        legende_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
        legende_frame.pack(fill="x", pady=(10, 15), anchor="w")

        ctk.CTkLabel(legende_frame, text="Légende des couleurs des demandes :",
                     font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))

        legend_items = [
            ("Action Requise par Vous", COULEUR_ACTIVE_POUR_UTILISATEUR),
            ("Demande Terminée", COULEUR_DEMANDE_TERMINEE),
            ("Demande Annulée", COULEUR_DEMANDE_ANNULEE),
        ]
        for texte, couleur_fond in legend_items:
            item_legende = ctk.CTkFrame(legende_frame, fg_color="transparent")
            item_legende.pack(side="left", padx=5)
            ctk.CTkFrame(item_legende, width=15, height=15, fg_color=couleur_fond, border_width=1).pack(
                side="left")
            ctk.CTkLabel(item_legende, text=texte, font=ctk.CTkFont(size=11)).pack(side="left", padx=3)