import os
import customtkinter as ctk
import threading
import logging
import math
import time
from tkinter import messagebox, simpledialog
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
from views.dialogs.archive_date_range_dialog import ArchiveDateRangeDialog
from utils.image_utils import get_or_create_circular_pfp
from views.mixins.task_runner_mixin import TaskRunnerMixin

POLLING_INTERVAL_MS_ACTIVE = 5000
POLLING_INTERVAL_MS_IDLE = 30000
IDLE_THRESHOLD_SECONDS = 120

COULEUR_ACTIVE_POUR_UTILISATEUR = "#1E4D2B"
COULEUR_DEMANDE_TERMINEE = "#2E4374"
COULEUR_DEMANDE_ANNULEE = "#6A040F"

_log = logging.getLogger(__name__)


class MainView(ctk.CTkFrame, TaskRunnerMixin):
    def __init__(self, master, nom_utilisateur, app_controller, remboursement_controller_factory,
                 preloaded_pfp_cache: dict):
        ctk.CTkFrame.__init__(self, master, corner_radius=0, fg_color="transparent")
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.pack(fill="both", expand=True)

        self.master = master
        self.nom_utilisateur = nom_utilisateur
        self.app_controller = app_controller
        self.auth_controller = app_controller.auth_controller
        self.remboursement_controller = remboursement_controller_factory(self.nom_utilisateur)

        self.pfp_size = 80
        self.pfp_cache = preloaded_pfp_cache
        self._polling_job_id = None
        self._last_known_db_mtime = 0
        self.demandes_en_cache = {}
        self.remboursement_widgets = {}
        self.no_demandes_label = None
        self._is_refreshing = False
        self.last_user_interaction_time = time.time()

        self.items_per_page = 20
        self.current_page = 1
        self.total_items = 0
        self.total_pages = 1
        self.pagination_frame = None

        self.is_archive_mode = False
        self.archive_date_range = None
        self.archive_mode_widgets = {}

        self._initialize_ui()

    def _initialize_ui(self):
        self.user_data = self.app_controller.get_user_from_cache(self.nom_utilisateur)
        if not self.user_data:
            self.app_controller.show_toast("Erreur critique au chargement des données utilisateur.", "error")
            self.app_controller.on_logout()
            return

        self.user_roles = self.user_data.roles
        is_admin = "admin" in self.user_roles
        user_theme = self.user_data.theme_color or "blue"
        ctk.set_default_color_theme(user_theme)

        self.initial_theme = self.user_data.theme_color
        self.current_sort = "Date de création (récent)"
        self.current_filter = self.user_data.default_filter
        self.search_var = ctk.StringVar()

        self._creer_widgets()
        self.afficher_liste_demandes(is_initial_load=True)
        self.start_polling()

        if is_admin:
            self.app_controller.show_admin_warning_popup()

    def _reset_idle_timer(self, event=None):
        self.last_user_interaction_time = time.time()

    def _create_placeholder_image(self, initial: str, size: int) -> ctk.CTkImage:
        placeholder = Image.new('RGBA', (size, size), (80, 80, 80, 255))
        draw = ImageDraw.Draw(placeholder)
        try:
            font_size = int(size * 0.6)
            font = ImageFont.truetype("arial", font_size)
        except IOError:
            font = ImageFont.load_default()
        draw.text((size / 2, size / 2), initial, font=font, anchor="mm", fill=(220, 220, 220))
        return ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=(size, size))

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
                                               command=lambda: self.afficher_liste_demandes(force_refresh=True),
                                               width=120)
        self.bouton_rafraichir.pack(side="left", pady=5, padx=10)
        self.notification_badge = ctk.CTkLabel(self.bouton_rafraichir, text="", fg_color="red", corner_radius=8,
                                               width=18, height=18, font=("Arial", 11, "bold"))
        self.winfo_toplevel().bind("<F5>", lambda event: self.afficher_liste_demandes(force_refresh=True))
        self.winfo_toplevel().bind("<Any-KeyPress>", self._reset_idle_timer)
        self.winfo_toplevel().bind("<Any-ButtonPress>", self._reset_idle_timer)
        self.winfo_toplevel().bind("<Motion>", self._reset_idle_timer)

        ctk.CTkButton(actions_bar_frame, text="Consulter les Archives", fg_color="gray50",
                      command=self._open_archive_dialog).pack(side="left", pady=5, padx=10)

        if self.est_admin():
            admin_buttons_frame = ctk.CTkFrame(actions_bar_frame, fg_color="transparent")
            admin_buttons_frame.pack(side="left", padx=20)
            ctk.CTkButton(admin_buttons_frame, text="Gérer Utilisateurs et BDD",
                          command=self._open_admin_user_management_view,
                          fg_color="#555555", hover_color="#444444").pack(side="left", padx=5)
            ctk.CTkButton(admin_buttons_frame, text="Purger les Archives", command=self._action_admin_purge_archives,
                          fg_color="#9D0208", hover_color="#6A040F").pack(side="left", padx=5)
            ctk.CTkButton(admin_buttons_frame, text="Maintenance BDD", command=self._action_admin_optimiser_bdd,
                          fg_color="#1F618D", hover_color="#154360").pack(side="left", padx=5)

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
        search_frame_parent.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(search_frame_parent, text="Rechercher (Nom, Prénom, Réf.):",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.search_entry = ctk.CTkEntry(search_frame_parent, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.search_entry.bind("<Return>", self._trigger_search_from_event)
        ctk.CTkButton(search_frame_parent, text="X", width=30, command=self._clear_search).grid(row=0, column=2,
                                                                                                sticky="w",
                                                                                                padx=(0, 20))

        self.archive_mode_widgets["label"] = ctk.CTkLabel(search_frame_parent, text="",
                                                          font=ctk.CTkFont(size=12, weight="bold"))
        self.archive_mode_widgets["button"] = ctk.CTkButton(search_frame_parent,
                                                            text="Quitter le mode Archive", text_color="white",
                                                            fg_color="#E53935", hover_color="#C62828",
                                                            command=self._quit_archive_mode)

        self.scrollable_frame_demandes = ctk.CTkScrollableFrame(main_content_frame,
                                                                label_text="Liste des Demandes de Remboursement")
        self.scrollable_frame_demandes.grid(row=3, column=0, pady=(5, 5), padx=10, sticky="nsew")
        self.scrollable_frame_demandes.grid_columnconfigure(0, weight=1)

        self.pagination_frame = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        self.pagination_frame.grid(row=4, column=0, pady=(5, 0), sticky="ew")

        legende_frame = ctk.CTkFrame(main_content_frame, fg_color="transparent")
        legende_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=(5, 10))
        ctk.CTkLabel(legende_frame, text="Légende:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 10))
        legend_items = [("Action Requise", COULEUR_ACTIVE_POUR_UTILISATEUR),
                        ("Terminée", COULEUR_DEMANDE_TERMINEE),
                        ("Annulée", COULEUR_DEMANDE_ANNULEE)]
        for texte, couleur in legend_items:
            item = ctk.CTkFrame(legende_frame, fg_color="transparent")
            item.pack(side="left", padx=5)
            ctk.CTkFrame(item, width=15, height=15, fg_color=couleur, border_width=1).pack(side="left")
            ctk.CTkLabel(item, text=texte, font=ctk.CTkFont(size=11)).pack(side="left", padx=3)

        self._update_ui_for_archive_mode()

    def _update_user_display(self):
        def task():
            if not self.user_data: return None
            pfp_path = self.user_data.profile_picture_path
            source_path = None
            if pfp_path and os.path.exists(os.path.join(PROFILE_PICTURES_DIR, pfp_path)):
                source_path = os.path.join(PROFILE_PICTURES_DIR, pfp_path)

            return get_or_create_circular_pfp(
                login=self.nom_utilisateur,
                source_path=source_path,
                size=self.pfp_size,
                cache_manager=self.app_controller.cache_manager
            )

        def on_complete(pfp_image, error):
            if error or not self.user_data: return

            if not pfp_image:
                pfp_image = self._create_placeholder_image(self.nom_utilisateur[0].upper(), self.pfp_size)

            self.pfp_label.configure(image=pfp_image)
            self.pfp_label.image = pfp_image
            roles_str = f" (Rôles: {', '.join(self.user_roles)})" if self.user_roles else ""
            self.user_name_label.configure(text=f"{self.nom_utilisateur}{roles_str}")

        self.run_task(task, on_complete, "Mise à jour de l'affichage...", show_overlay=False)

    def _render_demandes_list(self, result, error=None):
        try:
            if error:
                error_str = str(error).lower()
                if "unable to open database file" in error_str:
                    msg = "Connexion à la base de données impossible. Vérifiez votre connexion réseau (VPN, Wi-Fi)."
                    _log.critical(msg, exc_info=True)
                    self.app_controller.show_toast(msg, "error")
                else:
                    _log.error("Erreur lors du rafraîchissement de la liste.", exc_info=True)
                    self.app_controller.show_toast(f"Erreur lors du rafraîchissement: {error}", "error")
                return

            demandes_a_afficher, self.total_items = result
            self.total_pages = math.ceil(self.total_items / self.items_per_page) if self.items_per_page > 0 else 1
            if self.total_pages == 0: self.total_pages = 1
            if self.current_page > self.total_pages: self.current_page = self.total_pages

            if self.no_demandes_label:
                self.no_demandes_label.destroy()
                self.no_demandes_label = None

            new_data_map = {d.id_demande: d.model_dump() for d in demandes_a_afficher}
            new_ids = set(new_data_map.keys())
            current_ids = set(self.remboursement_widgets.keys())
            ids_to_remove = current_ids - new_ids
            ids_to_add = new_ids - current_ids
            ids_to_check = current_ids.intersection(new_ids)

            for demande_id in ids_to_remove:
                widget = self.remboursement_widgets.pop(demande_id, None)
                if widget and widget.winfo_exists():
                    widget.animate_out_and_destroy()

            widgets_to_animate_in = []
            for demande_id in ids_to_add:
                new_widget = RemboursementItemView(
                    master=self.scrollable_frame_demandes, main_view_instance=self,
                    demande_data=new_data_map[demande_id], current_user_name=self.nom_utilisateur,
                    user_roles=self.user_roles, app_controller=self.app_controller,
                    remboursement_controller=self.remboursement_controller,
                    refresh_list_callback=lambda: self.afficher_liste_demandes(force_refresh=True)
                )
                self.remboursement_widgets[demande_id] = new_widget
                widgets_to_animate_in.append(new_widget)

            for demande_id in ids_to_check:
                widget = self.remboursement_widgets.get(demande_id)
                if widget:
                    new_data = new_data_map[demande_id]
                    old_data = widget.demande_data
                    if new_data['date_derniere_modification'] != old_data['date_derniere_modification']:
                        widget.flash_update(new_data)
                    elif new_data != old_data:
                        widget.update_content(new_data)

            if not demandes_a_afficher:
                self.no_demandes_label = ctk.CTkLabel(self.scrollable_frame_demandes,
                                                      text="Aucune demande à afficher pour les critères sélectionnés.",
                                                      font=ctk.CTkFont(size=14, slant="italic"))
                self.no_demandes_label.grid(row=0, column=0, pady=20)
            else:
                for i, demande_model in enumerate(demandes_a_afficher):
                    widget = self.remboursement_widgets.get(demande_model.id_demande)
                    if widget:
                        widget.grid(row=i, column=0, pady=5, padx=5, sticky="ew")
                        if widget in widgets_to_animate_in:
                            widget.animate_in()

            self.demandes_en_cache = {d.id_demande: d.model_dump() for d in demandes_a_afficher}
            self._update_pagination_controls()
            self._update_notification_badge()

        finally:
            self._is_refreshing = False
            self.bouton_rafraichir.configure(state="normal")

    def afficher_liste_demandes(self, is_initial_load=False, force_refresh=False):
        if self._is_refreshing:
            return

        if is_initial_load:
            cache_key = f"{self.nom_utilisateur}_{self.current_filter}_default"
            cached_data = self.app_controller.cache_manager.get_demand_query_cache(cache_key)
            if cached_data:
                _log.info("Affichage de la liste initiale à partir du cache.")
                self._render_demandes_list(cached_data)

        self._is_refreshing = True
        self.bouton_rafraichir.configure(state="disabled")

        offset = (self.current_page - 1) * self.items_per_page

        def task():
            return self.remboursement_controller.get_demandes_filtrees_triees(
                user_roles=self.user_roles,
                filter_choice=self.current_filter,
                sort_choice=self.current_sort,
                search_term=self.search_var.get(),
                is_archive_mode=self.is_archive_mode,
                archive_date_range=self.archive_date_range,
                limit=self.items_per_page,
                offset=offset
            )

        self.run_task(task_function=task, on_complete=self._render_demandes_list, loading_message="",
                      show_overlay=False)

    def _update_pagination_controls(self):
        for widget in self.pagination_frame.winfo_children():
            widget.destroy()

        if self.total_items == 0:
            return

        self.pagination_frame.grid_columnconfigure((0, 2), weight=1)
        self.pagination_frame.grid_columnconfigure(1, weight=0)

        buttons_frame = ctk.CTkFrame(self.pagination_frame, fg_color="transparent")
        buttons_frame.grid(row=0, column=1, pady=5)

        info_label_text = f"Page {self.current_page} sur {self.total_pages} ({self.total_items} résultats)"
        info_label = ctk.CTkLabel(self.pagination_frame, text=info_label_text, font=ctk.CTkFont(size=12))
        info_label.grid(row=0, column=0, sticky="e", padx=20)

        btn_first = ctk.CTkButton(buttons_frame, text="<<", width=40, command=lambda: self._go_to_page(1))
        btn_first.pack(side="left", padx=2)
        if self.current_page <= 1: btn_first.configure(state="disabled")

        btn_prev = ctk.CTkButton(buttons_frame, text="<", width=40,
                                 command=lambda: self._go_to_page(self.current_page - 1))
        btn_prev.pack(side="left", padx=2)
        if self.current_page <= 1: btn_prev.configure(state="disabled")

        start_page = max(1, self.current_page - 2)
        end_page = min(self.total_pages, start_page + 4)
        if end_page - start_page < 4:
            start_page = max(1, end_page - 4)

        if start_page > 1:
            ctk.CTkLabel(buttons_frame, text="...").pack(side="left", padx=2)

        for page_num in range(start_page, end_page + 1):
            is_current = page_num == self.current_page
            btn_page = ctk.CTkButton(buttons_frame, text=str(page_num), width=30,
                                     fg_color="white" if is_current else "transparent",
                                     text_color="black" if is_current else None,
                                     command=lambda p=page_num: self._go_to_page(p))
            if is_current: btn_page.configure(state="disabled")
            btn_page.pack(side="left", padx=2)

        if end_page < self.total_pages:
            ctk.CTkLabel(buttons_frame, text="...").pack(side="left", padx=2)

        btn_next = ctk.CTkButton(buttons_frame, text=">", width=40,
                                 command=lambda: self._go_to_page(self.current_page + 1))
        btn_next.pack(side="left", padx=2)
        if self.current_page >= self.total_pages: btn_next.configure(state="disabled")

        btn_last = ctk.CTkButton(buttons_frame, text=">>", width=40, command=lambda: self._go_to_page(self.total_pages))
        btn_last.pack(side="left", padx=2)
        if self.current_page >= self.total_pages: btn_last.configure(state="disabled")

    def _go_to_page(self, page_number):
        if 1 <= page_number <= self.total_pages:
            self.current_page = page_number
            self.afficher_liste_demandes(force_refresh=True)

    def _update_notification_badge(self):
        count = sum(1 for d in self.demandes_en_cache.values() if self._is_active_for_user(d))
        if count > 0:
            self.notification_badge.configure(text=str(count))
            self.notification_badge.place(in_=self.bouton_rafraichir, relx=1.0, rely=0.0, anchor="ne")
        else:
            self.notification_badge.place_forget()

    def _is_active_for_user(self, demande_data: dict) -> bool:
        """ Détermine si la demande requiert une action de la part de l'utilisateur de cette MainView. """
        current_status = demande_data.get("statut")
        cree_par_user = demande_data.get("cree_par")
        if self.est_comptable_tresorerie() and current_status == STATUT_CREEE: return True
        if (
                self.nom_utilisateur == cree_par_user or self.est_admin()) and current_status == STATUT_REFUSEE_CONSTAT_TP: return True
        if (
                self.est_validateur_chef() or self.est_admin()) and current_status == STATUT_TROP_PERCU_CONSTATE: return True
        if (
                self.est_comptable_tresorerie() or self.est_admin()) and current_status == STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO: return True
        if (self.est_comptable_fournisseur() or self.est_admin()) and current_status == STATUT_VALIDEE: return True
        return False

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
        self.current_page = 1
        self.afficher_liste_demandes(force_refresh=True)

    def _set_filter(self, filter_choice):
        self.current_filter = filter_choice
        self.current_page = 1
        self.afficher_liste_demandes(force_refresh=True)

    def _trigger_search_from_event(self, event=None):
        self.current_page = 1
        self.afficher_liste_demandes(force_refresh=True)

    def _clear_search(self):
        self.search_var.set("")
        self.current_page = 1
        self.afficher_liste_demandes(force_refresh=True)

    def _update_ui_for_archive_mode(self):
        in_archive_mode = self.is_archive_mode
        self.filter_menu.configure(state="disabled" if in_archive_mode else "normal")
        self.sort_menu.configure(state="normal")

        if in_archive_mode:
            start, end = self.archive_date_range
            mode_text = f"Mode Archive ({start} - {end})"
            self.archive_mode_widgets["label"].configure(text=mode_text)
            self.archive_mode_widgets["label"].grid(row=0, column=3, sticky="w", padx=(20, 5))
            self.archive_mode_widgets["button"].grid(row=0, column=4, sticky="w")
        else:
            self.archive_mode_widgets["label"].grid_remove()
            self.archive_mode_widgets["button"].grid_remove()

    def _open_archive_dialog(self):
        dialog = ArchiveDateRangeDialog(self)
        date_range = dialog.get_range()

        if date_range:
            self.is_archive_mode = True
            self.archive_date_range = date_range
            self.current_page = 1
            self.search_var.set("")
            self._update_ui_for_archive_mode()
            self.afficher_liste_demandes(force_refresh=True)

    def _quit_archive_mode(self):
        self.is_archive_mode = False
        self.archive_date_range = None
        self.current_page = 1
        self._update_ui_for_archive_mode()
        self.afficher_liste_demandes(force_refresh=True)

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
                _log.info("Changement détecté sur le fichier de BDD. Rafraîchissement de la liste.")
                self._last_known_db_mtime = current_mtime
                self.afficher_liste_demandes(force_refresh=True)

            idle_time = time.time() - self.last_user_interaction_time
            next_poll_interval = POLLING_INTERVAL_MS_IDLE if idle_time > IDLE_THRESHOLD_SECONDS else POLLING_INTERVAL_MS_ACTIVE

            self._polling_job_id = self.after(next_poll_interval, self._check_for_data_updates)
        except Exception as e:
            _log.error(f"Erreur lors du polling de la base de données : {e}")
            if self.winfo_exists():
                self._polling_job_id = self.after(POLLING_INTERVAL_MS_IDLE, self._check_for_data_updates)

    def _open_profile_view(self):
        dialog = ProfileView(self, self.auth_controller, self.app_controller, self.user_data.model_dump(),
                             on_save_callback=self._on_profile_saved)
        self.wait_window(dialog)

    def _on_profile_saved(self):
        self.app_controller._load_user_cache()
        self.app_controller._preload_data()

        def task():
            current_user_data = self.app_controller.get_user_from_cache(self.nom_utilisateur)
            with self.app_controller.pfp_cache_lock:
                new_pfp_cache = self.app_controller.preloaded_pfp_cache

            main_pfp_source_path = None
            if current_user_data and current_user_data.profile_picture_path:
                path = os.path.join(PROFILE_PICTURES_DIR, current_user_data.profile_picture_path)
                if os.path.exists(path):
                    main_pfp_source_path = path
            main_pfp_image = get_or_create_circular_pfp(
                login=self.nom_utilisateur, source_path=main_pfp_source_path, size=self.pfp_size,
                cache_manager=self.app_controller.cache_manager
            )
            return current_user_data, new_pfp_cache, main_pfp_image

        def on_complete(result, error):
            if error or not result:
                self.app_controller.show_toast("Erreur critique lors de la mise à jour du profil.", "error")
                return

            new_user_data, new_pfp_cache, main_pfp_image = result
            self.user_data = new_user_data
            self.user_roles = self.user_data.roles if self.user_data else []
            self.pfp_cache = new_pfp_cache
            if not main_pfp_image:
                main_pfp_image = self._create_placeholder_image(self.nom_utilisateur[0].upper(), self.pfp_size)
            self.pfp_label.configure(image=main_pfp_image)
            roles_str = f" (Rôles: {', '.join(self.user_roles)})" if self.user_roles else ""
            self.user_name_label.configure(text=f"{self.nom_utilisateur}{roles_str}")
            self.current_filter = self.user_data.default_filter
            self.filter_menu.set(self.current_filter)
            self.afficher_liste_demandes(force_refresh=True)
            new_theme = self.user_data.theme_color
            if new_theme != self.initial_theme:
                self.app_controller.request_restart("Le changement de thème nécessite un redémarrage.")

        self.run_task(task, on_complete, "Mise à jour du profil...")

    def _ouvrir_fenetre_creation_demande(self):
        from views.dialogs.creation_demande_dialog import CreationDemandeDialog
        dialog = CreationDemandeDialog(self, self.remboursement_controller, self.app_controller)
        self.wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.afficher_liste_demandes(force_refresh=True)

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
                self.app_controller.cache_manager.add_to_cache(chemin_pj, rel_path)
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
                        if error: self.app_controller.show_toast(f"Erreur: {error}", "error"); return
                        nb_suppr, erreurs = result
                        msg = f"{nb_suppr} demande(s) ont été purgées."
                        if erreurs: msg += f"\nErreurs : {', '.join(erreurs)}"
                        self.app_controller.show_toast(msg, 'info')
                        self.afficher_liste_demandes(force_refresh=True)

                    self.run_task(task, on_complete, "Purge des archives...")
            except ValueError:
                self.app_controller.show_toast("Veuillez entrer un nombre valide.", "error")

    def _action_admin_optimiser_bdd(self):
        msg = ("Ceci va réorganiser la base de données pour réduire sa taille et améliorer les performances.\n\n"
               "ATTENTION : Cette opération est bloquante et peut prendre du temps. "
               "Veuillez vous assurer qu'aucun autre utilisateur n'est en train de travailler sur l'application.\n\n"
               "Voulez-vous continuer ?")
        if messagebox.askyesno("Optimisation BDD (VACUUM)", msg, icon='warning', parent=self):
            def task():
                return self.remboursement_controller.admin_optimiser_bdd()

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur: {error}", "error")
                    return
                success, message = result
                if success:
                    self.app_controller.show_toast(message, 'success')
                else:
                    self.app_controller.show_toast(message, 'error')

            self.run_task(task, on_complete, "Optimisation de la base de données...")

    def __del__(self):
        self.stop_polling()