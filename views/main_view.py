import os
import customtkinter as ctk
import threading
from tkinter import messagebox, simpledialog
import datetime
from PIL import Image, ImageDraw, ImageFont

from config.settings import (
    DATABASE_FILE, STATUT_CREEE,
    STATUT_REFUSEE_CONSTAT_TP, STATUT_ANNULEE,
    STATUT_PAIEMENT_EFFECTUE, STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    PROFILE_PICTURES_DIR
)
from models import user_model
from views.document_viewer import DocumentViewerWindow
from views.remboursement_item_view import RemboursementItemView
from views.document_history_viewer import DocumentHistoryViewer
from views.admin_user_management_view import AdminUserManagementView
from views.help_view import HelpView
from views.profile_view import ProfileView
from utils.image_utils import create_circular_image
from views.mixins.task_runner_mixin import TaskRunnerMixin

POLLING_INTERVAL_MS = 5000
COULEUR_ACTIVE_POUR_UTILISATEUR = "#1E4D2B"
COULEUR_DEMANDE_TERMINEE = "#2E4374"
COULEUR_DEMANDE_ANNULEE = "#6A040F"


class MainView(ctk.CTkFrame, TaskRunnerMixin):
    def __init__(self, master, nom_utilisateur, app_controller, remboursement_controller_factory):
        ctk.CTkFrame.__init__(self, master, corner_radius=0, fg_color="transparent")
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.pack(fill="both", expand=True)

        self.master = master
        self.nom_utilisateur = nom_utilisateur
        self.app_controller = app_controller
        self.auth_controller = app_controller.auth_controller
        self.remboursement_controller = remboursement_controller_factory(self.nom_utilisateur)

        self.pfp_size = 80
        self._polling_job_id = None
        self._last_known_db_mtime = 0
        self.all_demandes_cache = []
        self.remboursement_widgets = {}
        self.no_demandes_label = None

        self._fetch_user_data_and_init_ui()

    def _fetch_user_data_and_init_ui(self):
        def task():
            return self.auth_controller.get_user_data(self.nom_utilisateur)

        def on_complete(user_data, error):
            if error or not user_data:
                self.app_controller.show_toast("Erreur critique au chargement des données utilisateur.", "error")
                self.app_controller.on_logout()
                return

            self.user_data = user_data
            self.user_roles = self.user_data.roles if self.user_data else []

            is_admin = "admin" in self.user_roles
            user_theme = self.user_data.theme_color or "blue"
            ctk.set_default_color_theme(user_theme)

            self.initial_theme = self.user_data.theme_color if self.user_data else "blue"
            self.current_sort = "Date de création (récent)"
            self.current_filter = self.user_data.default_filter if self.user_data else "Toutes les demandes"
            self.include_archives = ctk.BooleanVar(value=False)
            self.search_var = ctk.StringVar()

            self._creer_widgets()
            self.afficher_liste_demandes(force_reload=True)
            self.start_polling()

            if is_admin:
                self.app_controller.show_admin_warning_popup()

        self.run_task(task, on_complete, "Chargement du profil utilisateur...")

    def _creer_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))

        self.user_info_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        self.user_info_frame.pack(side="left", padx=5, pady=2)

        self.pfp_label = ctk.CTkLabel(self.user_info_frame, text="", width=self.pfp_size, height=self.pfp_size)
        self.pfp_label.pack(side="left")
        self.user_name_label = ctk.CTkLabel(self.user_info_frame, text="", font=ctk.CTkFont(size=18, weight="bold"))
        self.user_name_label.pack(side="left", padx=15)
        self._update_user_display()

        right_buttons_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        right_buttons_frame.pack(side="right")
        ctk.CTkButton(right_buttons_frame, text="Mon Profil", command=self._open_profile_view, width=100,
                      fg_color="gray").pack(side="left", padx=5)
        ctk.CTkButton(right_buttons_frame, text="Aide", command=self._open_help_view, width=70).pack(side="left",
                                                                                                     padx=5)
        ctk.CTkButton(right_buttons_frame, text="Déconnexion", command=self.app_controller.on_logout,
                      width=120).pack(
            side="left", padx=(5, 0))

        main_content_frame = ctk.CTkFrame(self)
        main_content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        main_content_frame.grid_columnconfigure(0, weight=1)
        main_content_frame.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(main_content_frame, text="Tableau de Bord - Remboursements",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, pady=(10, 10), sticky="n")

        actions_bar_frame = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        actions_bar_frame.grid(row=1, column=0, pady=(0, 5), padx=10, sticky="ew")

        if self.peut_creer_demande():
            ctk.CTkButton(actions_bar_frame, text="Nouvelle Demande",
                          command=self._ouvrir_fenetre_creation_demande).pack(side="left", pady=5, padx=(0, 10))

        self.bouton_rafraichir = ctk.CTkButton(actions_bar_frame, text="Rafraîchir (F5)",
                                               command=lambda: self.afficher_liste_demandes(force_reload=True),
                                               width=120)
        self.bouton_rafraichir.pack(side="left", pady=5, padx=10)
        self.notification_badge = ctk.CTkLabel(self.bouton_rafraichir, text="", fg_color="red", corner_radius=8,
                                               width=18, height=18, font=("Arial", 11, "bold"))
        self.winfo_toplevel().bind("<F5>", lambda event: self.afficher_liste_demandes(force_reload=True))

        if self.est_admin():
            ctk.CTkButton(actions_bar_frame, text="Gérer Utilisateurs",
                          command=self._open_admin_user_management_view,
                          fg_color="#555555", hover_color="#444444").pack(side="left", pady=5, padx=10)
            ctk.CTkButton(actions_bar_frame, text="Purger les Archives", command=self._action_admin_purge_archives,
                          fg_color="#9D0208", hover_color="#6A040F").pack(side="left", pady=5, padx=10)

        options_frame = ctk.CTkFrame(actions_bar_frame, fg_color="transparent")
        options_frame.pack(side="right", pady=5)
        ctk.CTkLabel(options_frame, text="Trier par:").pack(side="left", padx=(10, 5))
        sort_options = ["Date de création (récent)", "Date de création (ancien)", "Montant (décroissant)",
                        "Montant (croissant)", "Nom du patient (A-Z)"]
        self.sort_menu = ctk.CTkOptionMenu(options_frame, values=sort_options, command=self._set_sort, width=180)
        self.sort_menu.set(self.current_sort)
        self.sort_menu.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(options_frame, text="Filtrer par:").pack(side="left", padx=(10, 5))
        filter_options = ["Toutes les demandes", "En attente de mon action", "En cours", "Terminées et annulées"]
        self.filter_menu = ctk.CTkOptionMenu(options_frame, values=filter_options, command=self._set_filter,
                                             width=180)
        self.filter_menu.set(self.current_filter)
        self.filter_menu.pack(side="left")

        search_frame_parent = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        search_frame_parent.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        ctk.CTkLabel(search_frame_parent, text="Rechercher (Nom, Prénom, Réf.):",
                     font=ctk.CTkFont(size=12)).pack(
            side="left", padx=(0, 5))
        self.search_entry = ctk.CTkEntry(search_frame_parent, textvariable=self.search_var, width=300)
        self.search_entry.pack(side="left", padx=(0, 5), fill="x", expand=True)
        self.search_var.trace_add("write", lambda name, index, mode: self.afficher_liste_demandes(show_overlay=False))
        ctk.CTkButton(search_frame_parent, text="X", width=30, command=self._clear_search).pack(side="left",
                                                                                                padx=(5, 0))
        ctk.CTkCheckBox(search_frame_parent, text="Inclure les archives", variable=self.include_archives,
                        command=self._on_archive_toggle).pack(side="left", padx=20)

        self.scrollable_frame_demandes = ctk.CTkScrollableFrame(main_content_frame,
                                                                label_text="Liste des Demandes de Remboursement")
        self.scrollable_frame_demandes.grid(row=3, column=0, pady=(5, 5), padx=10, sticky="nsew")
        self.scrollable_frame_demandes.grid_columnconfigure(0, weight=1)

        legende_frame = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        legende_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(5, 10))
        ctk.CTkLabel(legende_frame, text="Légende:", font=ctk.CTkFont(weight="bold")).pack(side="left",
                                                                                           padx=(0, 10))
        legend_items = [("Action Requise", COULEUR_ACTIVE_POUR_UTILISATEUR),
                        ("Terminée", COULEUR_DEMANDE_TERMINEE),
                        ("Annulée", COULEUR_DEMANDE_ANNULEE)]
        for texte, couleur in legend_items:
            item = ctk.CTkFrame(legende_frame, fg_color="transparent")
            item.pack(side="left", padx=5)
            ctk.CTkFrame(item, width=15, height=15, fg_color=couleur, border_width=1).pack(side="left")
            ctk.CTkLabel(item, text=texte, font=ctk.CTkFont(size=11)).pack(side="left", padx=3)

    def _update_user_display(self, show_overlay=True):
        def task():
            if not self.user_data: return None
            pfp_path = self.user_data.profile_picture_path
            pfp_image = None
            if pfp_path and os.path.exists(os.path.join(PROFILE_PICTURES_DIR, pfp_path)):
                pfp_image = create_circular_image(os.path.join(PROFILE_PICTURES_DIR, pfp_path), self.pfp_size)
            return pfp_image

        def on_complete(pfp_image, error):
            if error or not self.user_data: return

            if not pfp_image:
                placeholder = Image.new('RGBA', (self.pfp_size, self.pfp_size), (80, 80, 80, 255))
                draw = ImageDraw.Draw(placeholder)
                try:
                    font = ImageFont.truetype("arial", 45)
                except IOError:
                    font = ImageFont.load_default()
                draw.text((self.pfp_size / 2, self.pfp_size / 2), self.nom_utilisateur[0].upper(), font=font,
                          anchor="mm")
                pfp_image = ctk.CTkImage(light_image=placeholder, dark_image=placeholder,
                                         size=(self.pfp_size, self.pfp_size))
            self.pfp_label.configure(image=pfp_image)
            self.pfp_label.image = pfp_image
            roles_str = f" (Rôles: {', '.join(self.user_roles)})" if self.user_roles else ""
            self.user_name_label.configure(text=f"{self.nom_utilisateur}{roles_str}")

        self.run_task(task, on_complete, "Mise à jour de l'affichage...", show_overlay=show_overlay)

    def _get_refreshed_and_sorted_data(self, force_reload):
        old_cache_dict = {d.id_demande: d for d in self.all_demandes_cache}

        if force_reload:
            self.all_demandes_cache = self.remboursement_controller.get_toutes_les_demandes(
                self.include_archives.get())

        search_term = self.search_var.get().lower().strip()
        if search_term:
            demandes_filtrees = [d for d in self.all_demandes_cache if
                                 search_term in (d.nom or '').lower() or
                                 search_term in (d.prenom or '').lower() or
                                 search_term in str(d.reference_facture).lower()]
        else:
            demandes_filtrees = self.all_demandes_cache

        if self.current_filter == "En attente de mon action":
            demandes_filtrees = [d for d in demandes_filtrees if self._is_active_for_user(d)]
        elif self.current_filter == "En cours":
            demandes_filtrees = [d for d in demandes_filtrees if
                                 d.statut not in [STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE]]
        elif self.current_filter == "Terminées et annulées":
            demandes_filtrees = [d for d in demandes_filtrees if
                                 d.statut in [STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE]]

        reverse_sort = self.current_sort in ["Date de création (récent)", "Montant (décroissant)"]

        def get_sort_key(demande):
            sort_field_map = {
                "Date de création (récent)": "date_creation",
                "Date de création (ancien)": "date_creation",
                "Montant (décroissant)": "montant_demande",
                "Montant (croissant)": "montant_demande",
                "Nom du patient (A-Z)": "nom"
            }
            sort_field = sort_field_map.get(self.current_sort, "date_creation")
            value = getattr(demande, sort_field, None)

            if isinstance(value, str): return value.lower()
            if value is None: return datetime.datetime.min if "date" in sort_field else ""
            return value

        demandes_triees = sorted(demandes_filtrees, key=get_sort_key, reverse=reverse_sort)

        modified_ids = set()
        if old_cache_dict and not force_reload:
            for demande in self.all_demandes_cache:
                if demande.id_demande in old_cache_dict:
                    old_demande = old_cache_dict[demande.id_demande]
                    if demande.date_derniere_modification != old_demande.date_derniere_modification:
                        modified_ids.add(demande.id_demande)

        return demandes_triees, modified_ids

    def _render_demandes_list_intelligently(self, result, error=None):
        if error:
            self.app_controller.show_toast(f"Erreur lors du rafraîchissement: {error}", "error")
            return

        demandes_a_afficher, modified_ids = result

        if self.no_demandes_label:
            self.no_demandes_label.destroy()
            self.no_demandes_label = None

        demandes_actuelles_ids = {d.id_demande for d in demandes_a_afficher}
        widgets_actuels_ids = set(self.remboursement_widgets.keys())

        ids_a_supprimer = widgets_actuels_ids - demandes_actuelles_ids
        for demande_id in ids_a_supprimer:
            widget = self.remboursement_widgets.pop(demande_id)
            widget.destroy()

        demandes_dict = {d.id_demande: d.model_dump() for d in demandes_a_afficher}

        for widget in self.remboursement_widgets.values():
            widget.pack_forget()

        for demande in demandes_a_afficher:
            demande_id = demande.id_demande
            if demande_id in self.remboursement_widgets:
                widget = self.remboursement_widgets[demande_id]
                if demande_id in modified_ids:
                    widget.flash_update(demandes_dict[demande_id])
                else:
                    widget.update_content(demandes_dict[demande_id])
            else:
                widget = RemboursementItemView(
                    master=self.scrollable_frame_demandes,
                    main_view_instance=self,
                    demande_data=demandes_dict[demande_id],
                    current_user_name=self.nom_utilisateur,
                    user_roles=self.user_roles,
                    app_controller=self.app_controller,
                    remboursement_controller=self.remboursement_controller,
                    refresh_list_callback=lambda show_overlay=False: self.afficher_liste_demandes(force_reload=True,
                                                                                                  show_overlay=show_overlay)
                )
                self.remboursement_widgets[demande_id] = widget

            widget.pack(pady=5, padx=5, fill="x", expand=True)

        if not self.remboursement_widgets:
            self.no_demandes_label = ctk.CTkLabel(self.scrollable_frame_demandes, text="Aucune demande à afficher.",
                                                  font=ctk.CTkFont(size=14, slant="italic"))
            self.no_demandes_label.pack(pady=20)

        self._update_notification_badge()
        self._trigger_cache_sync()

    def _trigger_cache_sync(self):
        def task():
            actionable_demandes = [d for d in self.all_demandes_cache if self._is_active_for_user(d)]
            self.app_controller.cache_manager.sync_cache_for_user(actionable_demandes)

        threading.Thread(target=task, daemon=True).start()

    def afficher_liste_demandes(self, force_reload=False, show_overlay=True):
        loading_message = "Chargement des données..." if force_reload else "Mise à jour de la vue..."

        def task():
            return self._get_refreshed_and_sorted_data(force_reload)

        self.run_task(
            task_function=task,
            on_complete=self._render_demandes_list_intelligently,
            loading_message=loading_message,
            show_overlay=show_overlay
        )

    def _update_notification_badge(self):
        count = sum(1 for d in self.all_demandes_cache if self._is_active_for_user(d))
        if count > 0:
            self.notification_badge.configure(text=str(count))
            self.notification_badge.place(in_=self.bouton_rafraichir, relx=1.0, rely=0.0, anchor="ne")
        else:
            self.notification_badge.place_forget()

    def _is_active_for_user(self, demande):
        return demande.is_active_for(self.user_roles, self.nom_utilisateur)

    def est_admin(self):
        return "admin" in self.user_roles

    def peut_creer_demande(self):
        return "demandeur" in self.user_roles

    def est_comptable_tresorerie(self):
        return "comptable_tresorerie" in self.user_roles

    def est_validateur_chef(self):
        return "validateur_chef" in self.user_roles

    def est_comptable_fournisseur(self):
        return "comptable_fournisseur" in self.user_roles

    def _set_sort(self, sort_choice):
        self.current_sort = sort_choice
        self.afficher_liste_demandes(show_overlay=False)

    def _set_filter(self, filter_choice):
        self.current_filter = filter_choice
        self.afficher_liste_demandes(show_overlay=False)

    def _clear_search(self):
        self.search_var.set("")
        self.afficher_liste_demandes(show_overlay=False)

    def _on_archive_toggle(self):
        self.afficher_liste_demandes(force_reload=True)

    def _open_help_view(self):
        HelpView(self, self.nom_utilisateur, self.user_roles)

    def _open_admin_user_management_view(self):
        AdminUserManagementView(self, self.auth_controller, self.app_controller)

    def stop_polling(self):
        if self._polling_job_id:
            self.after_cancel(self._polling_job_id)
            self._polling_job_id = None

    def start_polling(self):
        self.stop_polling()
        self.after(500, self._check_for_data_updates)

    def _check_for_data_updates(self):
        try:
            current_mtime = os.path.getmtime(DATABASE_FILE) if os.path.exists(DATABASE_FILE) else 0
            if self._last_known_db_mtime == 0:
                self._last_known_db_mtime = current_mtime
            elif current_mtime != self._last_known_db_mtime:
                self._last_known_db_mtime = current_mtime
                self.afficher_liste_demandes(force_reload=True, show_overlay=False)
        except Exception as e:
            print(f"Erreur lors du polling de la base de données : {e}")
        finally:
            if self.winfo_exists():
                self._polling_job_id = self.after(POLLING_INTERVAL_MS, self._check_for_data_updates)

    def _open_profile_view(self):
        dialog = ProfileView(self, self.auth_controller, self.app_controller, self.user_data.model_dump())
        self.wait_window(dialog)
        if hasattr(dialog, 'saved') and dialog.saved:
            self._on_profile_saved()

    def _on_profile_saved(self):
        def task():
            return self.auth_controller.get_user_data(self.nom_utilisateur)

        def on_complete(user_data, error):
            if error or not user_data: return
            self.user_data = user_data
            self._update_user_display(show_overlay=False)
            self.current_filter = self.user_data.default_filter
            self.filter_menu.set(self.current_filter)
            self.afficher_liste_demandes(force_reload=False, show_overlay=False)
            new_theme = self.user_data.theme_color
            if new_theme != self.initial_theme:
                self.app_controller.request_restart("Le changement de thème nécessite un redémarrage.")

        self.run_task(task, on_complete, "Mise à jour du profil...")

    def _ouvrir_fenetre_creation_demande(self):
        from views.dialogs.creation_demande_dialog import CreationDemandeDialog
        dialog = CreationDemandeDialog(self, self.remboursement_controller, self.app_controller)
        self.wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.afficher_liste_demandes(force_reload=True)

    def _action_voir_pj(self, demande_id, rel_path):
        cached_path = self.app_controller.cache_manager.get_cached_path(rel_path)
        if cached_path:
            DocumentViewerWindow(self, cached_path, f"Aperçu (Cache) - {os.path.basename(rel_path)}",
                                 temp_dir_to_clean=None)
            return

        def task():
            return self.remboursement_controller.get_viewable_attachment_path(demande_id, rel_path)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur à l'ouverture : {error}", "error")
                return

            chemin_pj, temp_dir = result
            if chemin_pj and os.path.exists(chemin_pj):
                DocumentViewerWindow(self, chemin_pj, f"Aperçu - {os.path.basename(rel_path)}",
                                     temp_dir_to_clean=temp_dir)
            else:
                self.app_controller.show_toast(f"Fichier non trouvé : {rel_path}", "error")

        self.run_task(task, on_complete, "Préparation du document...")

    def _action_telecharger_pj(self, demande_id, rel_path):
        def task():
            return self.remboursement_controller.get_viewable_attachment_path(demande_id, rel_path)

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur : {error}", "error")
                return

            chemin_pj, temp_dir = result
            if not chemin_pj:
                self.app_controller.show_toast(f"Fichier non trouvé ou impossible à extraire : {rel_path}", "error")
                return

            succes, message = self.remboursement_controller.telecharger_copie_piece_jointe(chemin_pj, temp_dir)
            if succes:
                self.app_controller.show_toast(message, 'success')
            elif "annulé" not in message.lower():
                self.app_controller.show_toast(message, 'error')

        self.run_task(task, on_complete, "Téléchargement...")

    def _action_voir_historique_docs(self, demande_data):
        DocumentHistoryViewer(
            self,
            demande_data=demande_data,
            remboursement_controller=self.remboursement_controller,
            app_controller=self.app_controller
        )

    def _action_admin_purge_archives(self):
        age_str = simpledialog.askstring("Purger les Archives",
                                         "Entrez l'âge minimum (en années) des archives à supprimer.", parent=self)
        if age_str:
            try:
                age_en_annees = int(age_str)
                if messagebox.askyesno("Confirmation Purge",
                                       f"Êtes-vous sûr de vouloir purger les archives de plus de {age_en_annees} an(s) ?\nCette action est IRRÉVERSIBLE.",
                                       icon='warning', parent=self):
                    def task():
                        return self.remboursement_controller.admin_purge_archives(age_en_annees)

                    def on_complete(result, error):
                        if error:
                            self.app_controller.show_toast(f"Erreur: {error}", "error")
                            return
                        nb_suppr, erreurs = result
                        msg = f"{nb_suppr} demande(s) ont été purgées."
                        if erreurs: msg += f"\nErreurs : {', '.join(erreurs)}"
                        self.app_controller.show_toast(msg, 'info')
                        self.afficher_liste_demandes(force_reload=True)

                    self.run_task(task, on_complete, "Purge des archives...")
            except ValueError:
                self.app_controller.show_toast("Veuillez entrer un nombre valide.", "error")

    def __del__(self):
        self.stop_polling()