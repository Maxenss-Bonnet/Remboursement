import customtkinter as ctk
import logging
from views.mixins.animation_mixin import AnimationMixin
from views.mixins.task_runner_mixin import TaskRunnerMixin
from config.settings import (
    STATUT_CREEE, STATUT_TROP_PERCU_CONSTATE,
    STATUT_REFUSEE_CONSTAT_TP, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_VALIDEE
)

_log = logging.getLogger(__name__)


class EmailReminderDialog(ctk.CTkToplevel, AnimationMixin, TaskRunnerMixin):
    def __init__(self, master, app_controller, remboursement_controller):
        super().__init__(master)
        AnimationMixin.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        
        self.transient(master)
        self.grab_set()
        self.title("Envoyer un rappel e-mail")
        self.geometry("600x500")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_animated)
        
        self.app_controller = app_controller
        self.remboursement_controller = remboursement_controller
        self.master = master
        
        # Récupérer tous les utilisateurs
        self.all_users = self.app_controller.get_all_users_from_cache()
        
        # Déterminer le destinataire par défaut
        self.default_recipient = self._determine_default_recipient()
        
        self._create_widgets()
        self.fade_in()
    
    def _determine_default_recipient(self):
        """Détermine le destinataire par défaut basé sur les demandes en attente."""
        # Récupérer toutes les demandes en cours
        all_demandes, _ = self.remboursement_controller.get_demandes_filtrees_triees(
            user_roles=["admin"],  # Récupérer toutes les demandes
            filter_choice="En cours",
            sort_choice="Date de création (récent)",
            search_term="",
            search_scope="Tout",
            is_archive_mode=False,
            archive_date_range=None
        )
        
        # Analyser les statuts et déterminer les rôles nécessaires
        role_counts = {
            "comptable_tresorerie": 0,
            "validateur_chef": 0,
            "comptable_fournisseur": 0,
            "demandeur": {}  # Dictionnaire pour compter par créateur
        }
        
        for demande in all_demandes:
            if demande.statut in [STATUT_CREEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO]:
                role_counts["comptable_tresorerie"] += 1
            elif demande.statut == STATUT_TROP_PERCU_CONSTATE:
                role_counts["validateur_chef"] += 1
            elif demande.statut == STATUT_VALIDEE:
                role_counts["comptable_fournisseur"] += 1
            elif demande.statut == STATUT_REFUSEE_CONSTAT_TP:
                creator = demande.cree_par
                if creator:
                    role_counts["demandeur"][creator] = role_counts["demandeur"].get(creator, 0) + 1
        
        # Trouver le rôle avec le plus de demandes en attente
        max_count = 0
        target_role = None
        target_user = None
        
        for role, count in role_counts.items():
            if role == "demandeur":
                for user, user_count in count.items():
                    if user_count > max_count:
                        max_count = user_count
                        target_role = "demandeur"
                        target_user = user
            else:
                if count > max_count:
                    max_count = count
                    target_role = role
                    target_user = None
        
        # Si un rôle spécifique est trouvé, chercher un utilisateur avec ce rôle
        if target_role and not target_user:
            for user in self.all_users:
                if target_role in user.roles:
                    return user
        elif target_user:
            for user in self.all_users:
                if user.login == target_user:
                    return user
        
        # Par défaut, retourner le premier utilisateur non-admin
        for user in self.all_users:
            if "admin" not in user.roles:
                return user
        
        return self.all_users[0] if self.all_users else None
    
    def _create_widgets(self):
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Titre
        ctk.CTkLabel(
            main_frame, 
            text="Envoyer un rappel par e-mail", 
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(0, 20))
        
        # Dropdown destinataire
        ctk.CTkLabel(main_frame, text="Destinataire :").pack(anchor="w", pady=(0, 5))
        
        # Créer la liste des options pour le dropdown
        self.user_options = []
        self.user_dict = {}
        for user in self.all_users:
            roles_str = ", ".join(user.roles)
            option_text = f"{user.login} ({roles_str})"
            self.user_options.append(option_text)
            self.user_dict[option_text] = user
        
        self.recipient_var = ctk.StringVar()
        self.recipient_dropdown = ctk.CTkOptionMenu(
            main_frame,
            values=self.user_options,
            variable=self.recipient_var,
            command=self._on_recipient_changed,
            width=300
        )
        self.recipient_dropdown.pack(pady=(0, 20))
        
        # Définir le destinataire par défaut
        if self.default_recipient:
            default_option = f"{self.default_recipient.login} ({', '.join(self.default_recipient.roles)})"
            if default_option in self.user_options:
                self.recipient_var.set(default_option)
        
        # Zone de texte pour le message
        ctk.CTkLabel(main_frame, text="Message :").pack(anchor="w", pady=(0, 5))
        
        self.message_textbox = ctk.CTkTextbox(main_frame, height=250)
        self.message_textbox.pack(fill="both", expand=True, pady=(0, 20))
        
        # Générer le message initial
        self._update_message_template()
        
        # Boutons
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack()
        
        self.send_button = ctk.CTkButton(
            button_frame, 
            text="Envoyer", 
            command=self._send_reminder,
            width=120
        )
        self.send_button.pack(side="left", padx=10)
        
        cancel_button = ctk.CTkButton(
            button_frame, 
            text="Annuler", 
            command=self.close_animated,
            fg_color="gray",
            width=120
        )
        cancel_button.pack(side="left", padx=10)
    
    def _on_recipient_changed(self, choice):
        """Met à jour le message lorsque le destinataire change."""
        self._update_message_template()
    
    def _update_message_template(self):
        """Met à jour le template du message en fonction du destinataire sélectionné."""
        selected_option = self.recipient_var.get()
        if not selected_option or selected_option not in self.user_dict:
            return
        
        selected_user = self.user_dict[selected_option]
        
        # Compter les demandes en attente pour cet utilisateur
        demandes_en_attente = 0
        role_str = "utilisateur"
        
        # Récupérer les demandes filtrées pour cet utilisateur
        all_demandes, _ = self.remboursement_controller.get_demandes_filtrees_triees(
            user_roles=selected_user.roles,
            filter_choice="En attente de mon action",
            sort_choice="Date de création (récent)",
            search_term="",
            search_scope="Tout",
            is_archive_mode=False,
            archive_date_range=None
        )
        
        # Filtrer pour ne garder que celles actives pour cet utilisateur
        for demande in all_demandes:
            if demande.is_active_for(selected_user.roles, selected_user.login):
                demandes_en_attente += 1
        
        # Déterminer le rôle principal pour le message
        if "comptable_tresorerie" in selected_user.roles:
            role_str = "Comptable Trésorerie"
        elif "validateur_chef" in selected_user.roles:
            role_str = "Validateur Chef"
        elif "comptable_fournisseur" in selected_user.roles:
            role_str = "Comptable Fournisseur"
        # Cas spécifique pour le créateur original de la demande
        elif any(demande.cree_par == selected_user.login for demande in all_demandes):
            role_str = "Créateur de la demande"
        elif "demandeur" in selected_user.roles:
            role_str = "Demandeur"
        elif "admin" in selected_user.roles:
            role_str = "Administrateur"

        # --- Génération du message ---
        sender_name = self.master.nom_utilisateur
        
        # En-tête du message
        professional_message_header = f"""Bonjour {selected_user.login},

Ce message est un rappel concernant les {demandes_en_attente} demande(s) de remboursement nécessitant votre attention en tant que {role_str}.

Voici le détail des demandes en attente :"""

        # Pied de page du message
        professional_message_footer = f"""

Nous vous remercions de bien vouloir traiter ces demandes dans les meilleurs délais.

Cordialement,
L'Application de Gestion des Remboursements"""

        # Assembler le message final sans le tableau texte
        final_message = f"{professional_message_header}{professional_message_footer}"
        
        # Mettre à jour la zone de texte
        self.message_textbox.delete("1.0", "end")
        self.message_textbox.insert("1.0", final_message)
    
    def _get_structured_demandes_data(self):
        """Récupère une liste de dictionnaires des demandes en attente pour l'email."""
        selected_option = self.recipient_var.get()
        if not selected_option or selected_option not in self.user_dict:
            return []
            
        selected_user = self.user_dict[selected_option]
        
        all_demandes, _ = self.remboursement_controller.get_demandes_filtrees_triees(
            user_roles=selected_user.roles,
            filter_choice="En attente de mon action",
            sort_choice="Date de création (récent)",
            search_term="",
            search_scope="Tout",
            is_archive_mode=False,
            archive_date_range=None
        )

        demandes_data = []
        for demande in all_demandes:
            if demande.is_active_for(selected_user.roles, selected_user.login):
                demandes_data.append({
                    "id": demande.id_demande[:13],
                    "date": demande.date_creation.strftime('%d-%m-%Y'),
                    "patient": f"{demande.nom} {demande.prenom}",
                    "montant": f"{demande.montant_demande:.2f} €"
                })
        return demandes_data

    def _send_reminder(self):
        """Envoie le rappel par email."""
        selected_option = self.recipient_var.get()
        if not selected_option or selected_option not in self.user_dict:
            self.app_controller.show_toast("Veuillez sélectionner un destinataire.", "error")
            return
        
        selected_user = self.user_dict[selected_option]
        message = self.message_textbox.get("1.0", "end-1c").strip()
        
        if not message:
            self.app_controller.show_toast("Le message ne peut pas être vide.", "error")
            return
        
        if not selected_user.email:
            self.app_controller.show_toast(f"L'utilisateur {selected_user.login} n'a pas d'adresse email configurée.", "error")
            return
        
        # Désactiver le bouton pendant l'envoi
        self.send_button.configure(state="disabled")
        
        # Récupérer les données structurées des demandes
        demandes_details = self._get_structured_demandes_data()

        def task():
            return self.remboursement_controller.envoyer_rappel_email(
                destinataire_email=selected_user.email,
                nom_destinataire=selected_user.login,
                message=message,
                demandes_details=demandes_details
            )
        
        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur lors de l'envoi : {error}", "error")
                self.send_button.configure(state="normal")
            else:
                success, msg = result
                if success:
                    self.app_controller.show_toast("Rappel envoyé avec succès !", "success")
                    self.close_animated()
                else:
                    self.app_controller.show_toast(f"Échec de l'envoi : {msg}", "error")
                    self.send_button.configure(state="normal")
        
        self.run_task(task, on_complete, "Envoi du rappel...") 