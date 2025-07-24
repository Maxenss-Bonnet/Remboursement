import os
import customtkinter as ctk
import logging
from PIL import Image, ImageDraw, ImageFont

from config.settings import (
    PROFILE_PICTURES_DIR
)
from utils.image_utils import get_or_create_circular_pfp
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.polling_mixin import PollingMixin
from views.helpers.main_view_helper import MainViewHelper
from models.schemas import Remboursement

COULEUR_ACTIVE_POUR_UTILISATEUR = "#1E4D2B"
COULEUR_DEMANDE_TERMINEE = "#2E4374"
COULEUR_DEMANDE_ANNULEE = "#6A040F"

_log = logging.getLogger(__name__)


class MainView(ctk.CTkFrame, TaskRunnerMixin, PollingMixin):
    def __init__(self, master, nom_utilisateur, app_controller, remboursement_controller_factory,
                 preloaded_pfp_cache: dict):
        ctk.CTkFrame.__init__(self, master, corner_radius=0, fg_color="transparent")
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        PollingMixin.__init__(self)

        self.pack(fill="both", expand=True)

        self.master = master
        self.nom_utilisateur = nom_utilisateur
        self.app_controller = app_controller
        self.user_controller = app_controller.user_controller
        self.maintenance_controller = app_controller.maintenance_controller
        self.remboursement_controller = remboursement_controller_factory(self.nom_utilisateur)

        self.helper = MainViewHelper(self)
        self.network_sensitive_widgets = []

        self.pfp_size = 80
        self.pfp_cache = preloaded_pfp_cache
        self.items_per_page = 20
        self.is_archive_mode = False
        self.archive_date_range = None

        self._initialize_ui()

    def _initialize_ui(self):
        self.user_data = self.app_controller.get_user_from_cache(self.nom_utilisateur)
        if not self.user_data:
            self.app_controller.show_toast("Erreur critique au chargement des données utilisateur.", "error")
            self.app_controller.on_logout()
            return

        self.user_roles = self.user_data.roles
        user_theme = self.user_data.theme_color or "blue"
        ctk.set_default_color_theme(user_theme)

        self.initial_theme = self.user_data.theme_color
        self.current_sort = "Date de création (récent)"
        self.current_filter = self.user_data.default_filter
        self.search_var = ctk.StringVar()
        self.search_scope_var = ctk.StringVar(value="Tout")

        self._creer_widgets()
        self.helper.afficher_liste_demandes(is_initial_load=True)
        self.start_polling()

        if self.est_admin():
            self.app_controller.show_admin_warning_popup()

    def afficher_liste_demandes(self, is_initial_load=False, force_refresh=False, show_loader=True):
        self.helper.afficher_liste_demandes(is_initial_load, force_refresh, show_loader)

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
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self.winfo_toplevel().bind("<F5>", lambda e: self.afficher_liste_demandes(force_refresh=True))
        self.winfo_toplevel().bind("<Any-KeyPress>", self._reset_idle_timer)
        self.winfo_toplevel().bind("<Any-ButtonPress>", self._reset_idle_timer)
        self.winfo_toplevel().bind("<Motion>", self._reset_idle_timer)

        self._create_top_bar()
        self._create_main_content_frame()
        self._create_status_bar()

    def _create_top_bar(self):
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
        btn_profil = ctk.CTkButton(right_buttons_frame, text="Mon Profil", command=self.helper.open_profile_view,
                                   width=100,
                                   fg_color="gray")
        btn_profil.pack(side="left", padx=5)
        btn_aide = ctk.CTkButton(right_buttons_frame, text="Aide", command=self.helper.open_help_view, width=70)
        btn_aide.pack(side="left", padx=5)
        btn_deco = ctk.CTkButton(right_buttons_frame, text="Déconnexion", command=self.app_controller.on_logout,
                                 width=120)
        btn_deco.pack(side="left", padx=(5, 0))

        self.network_sensitive_widgets.extend([btn_profil, btn_aide, btn_deco])

    def set_network_status(self, is_connected: bool):
        """Active ou désactive les widgets sensibles à l'état du réseau."""
        if not self.winfo_exists():
            return

        state = "normal" if is_connected else "disabled"
        for widget in self.network_sensitive_widgets:
            if widget and widget.winfo_exists():
                widget.configure(state=state)

        # Assure que les contrôles d'archive sont correctement (dés)activés
        self._update_ui_for_archive_mode()

    def _create_main_content_frame(self):
        main_content_frame = ctk.CTkFrame(self)
        main_content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        main_content_frame.grid_columnconfigure(0, weight=1)
        main_content_frame.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(main_content_frame, text="Tableau de Bord - Remboursements",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, pady=(10, 10), sticky="n")

        self._create_actions_bar(main_content_frame)
        self._create_search_and_filter_bar(main_content_frame)
        self._create_demandes_list_frame(main_content_frame)
        self._create_pagination_frame(main_content_frame)
        self._create_legend_frame(main_content_frame)

    def _create_status_bar(self):
        self.status_bar = ctk.CTkFrame(self, height=25, corner_radius=0)
        self.status_bar.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        self.status_label = ctk.CTkLabel(self.status_bar, text="Prêt", font=ctk.CTkFont(size=12), anchor="w")
        self.status_label.pack(side="left", padx=10)
        self.status_progress = ctk.CTkProgressBar(self.status_bar, width=100, mode='indeterminate')
        self.status_progress.pack(side="right", padx=10)
        self.status_progress.pack_forget()

    def update_status_bar(self, message: str, is_busy: bool):
        if not self.winfo_exists(): return
        self.status_label.configure(text=message)
        if is_busy:
            if not self.status_progress.winfo_ismapped():
                self.status_progress.pack(side="right", padx=10)
                self.status_progress.start()
        else:
            if self.status_progress.winfo_ismapped():
                self.status_progress.stop()
                self.status_progress.pack_forget()

    def _create_actions_bar(self, parent):
        actions_bar_frame = ctk.CTkFrame(parent, fg_color="transparent")
        actions_bar_frame.grid(row=1, column=0, pady=(0, 5), padx=10, sticky="ew")

        btn_nouveau = ctk.CTkButton(actions_bar_frame, text="Nouvelle Demande",
                                    command=self.helper.ouvrir_fenetre_creation_demande)
        if self.peut_creer_demande():
            btn_nouveau.pack(side="left", pady=5, padx=(0, 10))
        self.network_sensitive_widgets.append(btn_nouveau)

        self.bouton_rafraichir = ctk.CTkButton(actions_bar_frame, text="Rafraîchir (F5)",
                                               command=lambda: self.afficher_liste_demandes(force_refresh=True),
                                               width=120)
        self.bouton_rafraichir.pack(side="left", pady=5, padx=10)
        self.notification_badge = ctk.CTkLabel(self.bouton_rafraichir, text="", fg_color="red", corner_radius=8,
                                               width=18, height=18, font=("Arial", 11, "bold"))
        self.network_sensitive_widgets.append(self.bouton_rafraichir)

        btn_archives = ctk.CTkButton(actions_bar_frame, text="Consulter les Archives", fg_color="gray50",
                                     command=self.helper.open_archive_dialog)
        btn_archives.pack(side="left", pady=5, padx=10)
        self.network_sensitive_widgets.append(btn_archives)
        
        btn_email_reminder = ctk.CTkButton(actions_bar_frame, text="Envoyer un rappel e-mail", 
                                          command=self.helper.open_email_reminder_dialog,
                                          fg_color="#1976D2", hover_color="#1565C0")
        btn_email_reminder.pack(side="left", pady=5, padx=10)
        self.network_sensitive_widgets.append(btn_email_reminder)

        if self.est_admin():
            admin_buttons_frame = ctk.CTkFrame(actions_bar_frame, fg_color="transparent")
            admin_buttons_frame.pack(side="left", padx=20)
            btn_gerer = ctk.CTkButton(admin_buttons_frame, text="Gérer Utilisateurs et BDD",
                                      command=self.helper.open_admin_user_management_view,
                                      fg_color="#555555", hover_color="#444444")
            btn_gerer.pack(side="left", padx=5)
            btn_purger = ctk.CTkButton(admin_buttons_frame, text="Purger les Archives",
                                       command=self.helper.action_admin_purge_archives,
                                       fg_color="#9D0208", hover_color="#6A040F")
            btn_purger.pack(side="left", padx=5)
            btn_maintenance = ctk.CTkButton(admin_buttons_frame, text="Maintenance BDD",
                                            command=self.helper.action_admin_optimiser_bdd,
                                            fg_color="#1F618D", hover_color="#154360")
            btn_maintenance.pack(side="left", padx=5)
            self.network_sensitive_widgets.extend([btn_gerer, btn_purger, btn_maintenance])

    def _create_search_and_filter_bar(self, parent):
        search_frame_parent = ctk.CTkFrame(parent, fg_color="transparent")
        search_frame_parent.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        search_frame_parent.grid_columnconfigure(0, weight=1)

        options_frame = ctk.CTkFrame(search_frame_parent, fg_color="transparent")
        options_frame.pack(side="right", pady=5, padx=0)

        ctk.CTkLabel(options_frame, text="Trier par:").pack(side="left", padx=(10, 5))
        sort_options = ["Date de création (récent)", "Date de création (ancien)", "Montant (décroissant)",
                        "Montant (croissant)", "Nom du patient (A-Z)"]
        self.sort_menu = ctk.CTkOptionMenu(options_frame, values=sort_options, command=self.helper.set_sort,
                                           width=180)
        self.sort_menu.set(self.current_sort)
        self.sort_menu.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(options_frame, text="Filtrer par:").pack(side="left", padx=(10, 5))
        filter_options = ["Toutes les demandes", "En attente de mon action", "En cours", "Terminées et annulées"]
        self.filter_menu = ctk.CTkOptionMenu(options_frame, values=filter_options, command=self.helper.set_filter,
                                             width=180)
        self.filter_menu.set(self.current_filter)
        self.filter_menu.pack(side="left")

        search_bar_frame = ctk.CTkFrame(search_frame_parent, fg_color="transparent")
        search_bar_frame.pack(side="left", fill="x", expand=True, pady=5, padx=0)
        search_bar_frame.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(search_bar_frame, text="Rechercher:", font=ctk.CTkFont(size=12)).grid(row=0, column=0,
                                                                                           sticky="w",
                                                                                           padx=(0, 5))

        search_scope_options = ["Tout", "Nom/Prénom", "Réf. Facture", "Montant"]
        self.search_scope_menu = ctk.CTkOptionMenu(search_bar_frame, values=search_scope_options,
                                                   variable=self.search_scope_var,
                                                   width=120, command=lambda e: self.helper.trigger_search_from_event())
        self.search_scope_menu.grid(row=0, column=1, sticky="w", padx=5)

        self.search_entry = ctk.CTkEntry(search_bar_frame, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=2, sticky="ew", padx=(0, 5))
        self.search_entry.bind("<Return>", self.helper.trigger_search_from_event)
        self.btn_clear_search = ctk.CTkButton(search_bar_frame, text="X", width=30, command=self.helper.clear_search)
        self.btn_clear_search.grid(row=0, column=3,
                                   sticky="w",
                                   padx=(0, 20))
        self.network_sensitive_widgets.extend(
            [self.sort_menu, self.filter_menu, self.search_scope_menu, self.search_entry, self.btn_clear_search])

        self.archive_mode_widgets = {
            "label": ctk.CTkLabel(search_bar_frame, text="", font=ctk.CTkFont(size=12, weight="bold")),
            "button": ctk.CTkButton(search_bar_frame, text="Quitter le mode Archive", text_color="white",
                                    fg_color="#E53935", hover_color="#C62828",
                                    command=self.helper.quit_archive_mode)
        }
        self.archive_mode_widgets["label"].grid(row=0, column=4, sticky="w", padx=(20, 5))
        self.archive_mode_widgets["button"].grid(row=0, column=5, sticky="w")
        self.network_sensitive_widgets.append(self.archive_mode_widgets["button"])

        self._update_ui_for_archive_mode()

    def _create_demandes_list_frame(self, parent):
        self.scrollable_frame_demandes = ctk.CTkScrollableFrame(parent,
                                                                label_text="Liste des Demandes de Remboursement")
        self.scrollable_frame_demandes.grid(row=3, column=0, pady=(5, 5), padx=10, sticky="nsew")
        self.scrollable_frame_demandes.grid_columnconfigure(0, weight=1)

    def _create_pagination_frame(self, parent):
        self.pagination_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.pagination_frame.grid(row=4, column=0, pady=(5, 0), sticky="ew")

    def _create_legend_frame(self, parent):
        legende_frame = ctk.CTkFrame(parent, fg_color="transparent")
        legende_frame.grid(row=5, column=0, sticky="ew", padx=10, pady=(5, 10))
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

    def _update_user_display(self):
        full_path = None
        if self.user_data and self.user_data.profile_picture_path:
            path = os.path.join(PROFILE_PICTURES_DIR, self.user_data.profile_picture_path)
            if os.path.exists(path): full_path = path

        pfp_image = get_or_create_circular_pfp(
            login=self.nom_utilisateur, source_path=full_path, size=self.pfp_size,
            cache_manager=self.app_controller.cache_manager
        )
        if not pfp_image: pfp_image = self._create_placeholder_image(self.nom_utilisateur[0].upper(), self.pfp_size)

        self.pfp_label.configure(image=pfp_image)
        roles_str = f" (Rôles: {', '.join(self.user_roles)})" if self.user_roles else ""
        self.user_name_label.configure(text=f"{self.nom_utilisateur}{roles_str}")

    def _update_ui_for_archive_mode(self):
        is_disabled_by_archive = self.is_archive_mode
        is_enabled_by_network = self.bouton_rafraichir.cget("state") == "normal"

        state_for_archive_sensitive_widgets = "normal" if is_enabled_by_network and not is_disabled_by_archive else "disabled"

        self.filter_menu.configure(state=state_for_archive_sensitive_widgets)

        self.search_entry.configure(state="normal" if is_enabled_by_network else "disabled")

        if self.is_archive_mode:
            start, end = self.archive_date_range
            self.archive_mode_widgets["label"].configure(text=f"Mode Archive ({start} - {end})")
            self.archive_mode_widgets["label"].grid()
            self.archive_mode_widgets["button"].grid()
        else:
            self.archive_mode_widgets["label"].grid_remove()
            self.archive_mode_widgets["button"].grid_remove()

    def _on_profile_saved(self):
        self.app_controller._load_user_cache()
        self.app_controller._preload_data()

        def task():
            return self.app_controller.get_user_from_cache(self.nom_utilisateur)

        def on_complete(new_user_data, error):
            if error or not new_user_data: return
            self.user_data = new_user_data
            self.user_roles = self.user_data.roles if self.user_data else []
            self._update_user_display()

            self.current_filter = self.user_data.default_filter
            self.filter_menu.set(self.current_filter)
            self.afficher_liste_demandes(force_refresh=True)

            new_theme = self.user_data.theme_color
            if new_theme != self.initial_theme:
                self.app_controller.request_restart("Le changement de thème nécessite un redémarrage.")

        self.run_task(task, on_complete, "Mise à jour du profil...")

    def _is_active_for_user(self, demande_data: dict) -> bool:
        try:
            demande_model = Remboursement.model_validate(demande_data)
            return demande_model.is_active_for(self.user_roles, self.nom_utilisateur)
        except Exception as e:
            _log.error(f"Impossible de créer le modèle Remboursement pour l'évaluation : {e}")
            return False

    def est_admin(self):
        return "admin" in self.user_roles

    def peut_creer_demande(self):
        return "demandeur" in self.user_roles

    def __del__(self):
        _log.debug(f"Destruction de MainView pour {self.nom_utilisateur}")
        self.stop_polling()