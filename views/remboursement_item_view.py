import os
import re
import customtkinter as ctk
import datetime
from tkinter import TclError

from config.settings import (
    STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_ANNULEE, STATUT_PAIEMENT_EFFECTUE
)
from views.mixins.task_runner_mixin import TaskRunnerMixin
from utils import icon_renderer
from views.helpers.remboursement_item_actions import RemboursementItemActions

COULEUR_ACTIVE_POUR_UTILISATEUR = "#1E4D2B"
COULEUR_DEMANDE_TERMINEE = "#2E4374"
COULEUR_DEMANDE_ANNULEE = "#6A040F"
COULEUR_BORDURE_ACTIVE = "#38761D"
COULEUR_BORDURE_TERMINEE = "#4A55A2"
COULEUR_BORDURE_ANNULEE = "#9D0208"
COULEUR_BORDURE_DEFAUT = "gray40"
COULEUR_BORDURE_FLASH = "#FFD700"


class RemboursementItemView(ctk.CTkFrame, TaskRunnerMixin):
    def __init__(self, master, main_view_instance, demande_data: dict, current_user_name: str, user_roles: list,
                 app_controller, remboursement_controller, refresh_list_callback):
        ctk.CTkFrame.__init__(self, master, border_width=1, corner_radius=5)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.main_view = main_view_instance
        self.demande_data = demande_data
        self.current_user_name = current_user_name
        self.user_roles = user_roles
        self.app_controller = app_controller
        self.remboursement_controller = remboursement_controller
        self.refresh_list_callback = refresh_list_callback

        self.actions = RemboursementItemActions(self)

        self.id_demande = self.demande_data.get("id_demande")
        self.content_frame = None
        self.original_border_color = COULEUR_BORDURE_DEFAUT
        self.workflow_frame = None
        self.master_scrollable_frame = master

        self._setup_item_colors_and_ui()

    def update_content(self, demande_data: dict):
        self.demande_data = demande_data
        self.id_demande = self.demande_data.get("id_demande")
        if self.content_frame and self.content_frame.winfo_exists():
            self.content_frame.destroy()
        self.content_frame = None
        self._setup_item_colors_and_ui()

    def _setup_item_colors_and_ui(self):
        is_active = self._is_active_for_user()
        status = self.demande_data.get("statut")

        color_map = {
            STATUT_ANNULEE: (COULEUR_DEMANDE_ANNULEE, COULEUR_BORDURE_ANNULEE, 2),
            STATUT_PAIEMENT_EFFECTUE: (COULEUR_DEMANDE_TERMINEE, COULEUR_BORDURE_TERMINEE, 2)
        }

        if is_active:
            fg_color, border_color, border_width = COULEUR_ACTIVE_POUR_UTILISATEUR, COULEUR_BORDURE_ACTIVE, 2
        elif status in color_map:
            fg_color, border_color, border_width = color_map[status]
        else:
            fg_color = self._resolve_color(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
            border_color, border_width = COULEUR_BORDURE_DEFAUT, 1

        self.original_border_color = border_color
        self.configure(border_width=border_width, fg_color=fg_color, border_color=border_color)
        self._build_ui_content()

    def _build_ui_content(self):
        if self.content_frame: self.content_frame.destroy()

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_frame.pack(fill="both", expand=True, padx=1, pady=1)
        self.content_frame.grid_columnconfigure(0, weight=2, minsize=280)
        self.content_frame.grid_columnconfigure(1, weight=3, minsize=300)
        self.content_frame.grid_columnconfigure(2, weight=0, minsize=180)

        self._build_basic_info_frame()
        self._build_history_frame()
        self._build_documents_frame()
        self._build_workflow_buttons_frame()
        if self.est_admin():
            self._build_admin_buttons_frame()

        self._bind_scroll_to_children(self)

    def _build_basic_info_frame(self):
        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=(8, 5), pady=5)
        frame.grid_columnconfigure(1, weight=1)

        info_rows = {
            "Patient:": f"{self.demande_data.get('nom', 'N/A')} {self.demande_data.get('prenom', 'N/A')}",
            "Réf. Facture:": self.demande_data.get('reference_facture', 'N/A'),
            "Montant:": f"{self.demande_data.get('montant_demande', 0.0):.2f} €",
            "Créée par:": self.demande_data.get('cree_par') or 'Utilisateur supprimé',
            "Créée le:": self.demande_data.get('date_creation', 'N/A'),
            "Modifiée par:": self.demande_data.get('derniere_modification_par') or 'Utilisateur supprimé',
            "Statut Actuel:": self.demande_data.get('statut', 'Non défini')
        }
        if self.demande_data.get('date_paiement_effectue'):
            info_rows["Paiement le:"] = self.demande_data['date_paiement_effectue']

        for i, (label, value) in enumerate(info_rows.items()):
            color = "lightgreen" if label == "Paiement le:" else None
            ctk.CTkLabel(frame, text=label, font=ctk.CTkFont(weight="bold", size=12), anchor="w").grid(row=i, column=0,
                                                                                                       sticky="nw",
                                                                                                       padx=(5, 2),
                                                                                                       pady=(2, 2))
            ctk.CTkLabel(frame, text=value, font=ctk.CTkFont(size=13), anchor="w", justify="left", wraplength=0,
                         text_color=color).grid(row=i, column=1, sticky="ew", padx=(5, 2), pady=(2, 2))

    def _build_history_frame(self):
        container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        container.grid(row=0, column=1, sticky="nsew", padx=(5, 5), pady=5)
        ctk.CTkLabel(container, text="Historique/Commentaires:", font=ctk.CTkFont(weight="bold", size=12)).pack(
            anchor="w", pady=(0, 2))

        scroll_frame = ctk.CTkScrollableFrame(container, fg_color="gray20", border_width=1, label_text="")
        scroll_frame.pack(fill="both", expand=True)

        historique = self.demande_data.get('historique_statuts', [])
        if not historique:
            ctk.CTkLabel(scroll_frame, text="Aucun historique.", font=ctk.CTkFont(size=13),
                         text_color="gray60").pack(pady=10)
        else:
            pfp_cache = self.app_controller.preloaded_pfp_cache or {}
            default_pfp = pfp_cache.get('default')
            for i, entree in enumerate(reversed(historique)):
                self._create_history_entry(scroll_frame, entree, pfp_cache, default_pfp)
                if i < len(historique) - 1:
                    ctk.CTkFrame(scroll_frame, height=1, fg_color="gray40").pack(fill="x", padx=5, pady=5)

    def _create_history_entry(self, parent, entree, pfp_cache, default_pfp):
        user = entree.get('par_utilisateur') or 'Système'
        pfp_image = pfp_cache.get(user, default_pfp)

        entry_frame = ctk.CTkFrame(parent, fg_color="transparent")
        entry_frame.pack(fill="x", expand=True, pady=(0, 5))

        ctk.CTkLabel(entry_frame, image=pfp_image, text="", width=20, height=20).pack(side="left", anchor="n",
                                                                                      padx=(5, 8), pady=3)

        details_frame = ctk.CTkFrame(entry_frame, fg_color="transparent")
        details_frame.pack(side="left", fill="x", expand=True)

        try:
            date_obj = datetime.datetime.fromisoformat(str(entree.get('date', '')).split('.')[0])
            formatted_date = date_obj.strftime('%d/%m/%y %H:%M')
        except (ValueError, TypeError):
            formatted_date = entree.get('date', 'N/A')

        ctk.CTkLabel(details_frame, text=f"{formatted_date} - {user}", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#C0C0C0", anchor="w").pack(fill="x")

        if entree.get('statut'):
            self._create_history_status_line(details_frame, entree.get('statut'))

        if str(entree.get('commentaire', '')).strip():
            ctk.CTkLabel(details_frame, text=f"{str(entree.get('commentaire')).strip()}\u00A0", wraplength=400,
                         justify="left", font=ctk.CTkFont(size=12, slant="italic"), text_color="gray85",
                         anchor="w").pack(fill="x", pady=(2, 0))

    def _create_history_status_line(self, parent, status_text):
        statut_frame = ctk.CTkFrame(parent, fg_color="transparent")
        statut_frame.pack(fill="x")
        icon = icon_renderer.get_icon_image(status_text, 16)
        if icon: ctk.CTkLabel(statut_frame, image=icon, text="").pack(side="left", padx=(0, 5), pady=2)
        ctk.CTkLabel(statut_frame, text=status_text, font=ctk.CTkFont(size=12), anchor="w").pack(side="left", fill="x")

    def _build_documents_frame(self):
        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        frame.grid(row=0, column=2, sticky="nsew", padx=(5, 8), pady=5)
        frame.grid_columnconfigure(0, weight=1)

        doc_types = {
            "Facture": "chemins_factures_stockees",
            "RIB": "chemins_rib_stockes",
            "Preuve TP": "chemins_trop_percu_stockees"
        }
        has_history = False
        for label, key in doc_types.items():
            file_list = self.demande_data.get(key, [])
            if len(file_list) > 1: has_history = True
            self._create_document_row(frame, label, file_list)

        if has_history:
            ctk.CTkFrame(frame, height=2, fg_color="gray50").pack(fill="x", pady=5, padx=10)
            ctk.CTkButton(frame, text="Historique des Documents", fg_color="gray50",
                          command=lambda: self.main_view.helper.action_voir_historique_docs(self.demande_data)
                          ).pack(fill="x", padx=2, pady=(5, 0))

    def _create_document_row(self, parent, label_text, file_list):
        if not file_list:
            ctk.CTkLabel(parent, text=f"{label_text}: N/A", font=ctk.CTkFont(size=12, slant="italic")).pack(fill="x",
                                                                                                            pady=2,
                                                                                                            padx=5,
                                                                                                            anchor="w")
            return

        def get_version(path):
            match = re.search(r'_v(\d+)', os.path.basename(path))
            return int(match.group(1)) if match else 0

        latest_file = sorted(file_list, key=get_version)[-1]

        ctk.CTkLabel(parent, text=label_text, font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x", pady=(5, 0),
                                                                                             padx=5, anchor="w")

        button_frame = ctk.CTkFrame(parent, fg_color="transparent")
        button_frame.pack(fill="x", expand=True)
        button_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(button_frame, text="Voir",
                      command=lambda p=latest_file: self.main_view.helper.action_voir_pj(self.id_demande, p)).grid(
            row=0, column=0, sticky="ew", padx=(0, 2))
        ctk.CTkButton(button_frame, text="DL", width=40, fg_color="gray50",
                      command=lambda p=latest_file: self.main_view.helper.action_telecharger_pj(self.id_demande,
                                                                                                p)).grid(row=0,
                                                                                                         column=1,
                                                                                                         sticky="e")

    def _build_workflow_buttons_frame(self):
        if self.workflow_frame and self.workflow_frame.winfo_exists(): self.workflow_frame.destroy()

        buttons_to_add = self.actions.get_workflow_buttons()
        if not buttons_to_add: return

        self.workflow_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.workflow_frame.grid(row=1, column=0, columnspan=3, pady=(8, 4), sticky="ew")
        self.workflow_frame.grid_columnconfigure(0, weight=1)

        inner_buttons_frame = ctk.CTkFrame(self.workflow_frame, fg_color="transparent")
        inner_buttons_frame.grid(row=0, column=0)

        for btn_info in buttons_to_add:
            ctk.CTkButton(inner_buttons_frame, text=btn_info["text"], width=150,
                          fg_color=btn_info["fg_color"], hover_color=btn_info["hover_color"],
                          command=btn_info["command"]).pack(side="left", padx=5)

    def _build_admin_buttons_frame(self):
        frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        frame.grid(row=2, column=0, columnspan=3, pady=(4, 8), sticky="e")

        is_finished = self.demande_data.get("statut") in [STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE]
        if not self.demande_data.get('is_archived', False) and is_finished:
            ctk.CTkButton(frame, text="Archiver Manuellement", width=150, fg_color="#6c757d",
                          hover_color="#5a6268", command=self.actions.archiver_manuellement).pack(side="right",
                                                                                                  padx=(5, 5))

        ctk.CTkButton(frame, text="Supprimer (Admin)", width=150, fg_color="red",
                      hover_color="darkred", command=self.actions.supprimer_demande).pack(side="right", padx=(0, 5))

    def _show_local_loading(self, is_loading: bool):
        if not self.workflow_frame or not self.workflow_frame.winfo_exists(): return
        if is_loading:
            for widget in self.workflow_frame.winfo_children(): widget.destroy()
            progress_bar = ctk.CTkProgressBar(self.workflow_frame, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill='x')
            progress_bar.start()
        else:
            self._build_workflow_buttons_frame()

    def _bind_scroll_to_children(self, widget):
        widget.bind("<MouseWheel>", self._propagate_scroll)
        for child in widget.winfo_children():
            if not isinstance(child, ctk.CTkScrollableFrame):
                child.bind("<MouseWheel>", self._propagate_scroll, add="+")
                self._bind_scroll_to_children(child)

    def _propagate_scroll(self, event):
        if self.master_scrollable_frame:
            self.master_scrollable_frame._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _resolve_color(self, color_val):
        try:
            if isinstance(color_val, (list, tuple)): return color_val[1] if ctk.get_appearance_mode() == "Dark" else \
                color_val[0]
            if isinstance(color_val, str) and " " in color_val: return color_val.split(" ")[
                1] if ctk.get_appearance_mode() == "Dark" else color_val.split(" ")[0]
            return color_val
        except (AttributeError, IndexError):
            return color_val

    def _interpolate_color(self, c1: str, c2: str, factor: float) -> str:
        try:
            r1, g1, b1 = self.winfo_rgb(self._resolve_color(c1))
            r2, g2, b2 = self.winfo_rgb(self._resolve_color(c2))
            r, g, b = int(r1 + (r2 - r1) * factor), int(g1 + (g2 - g1) * factor), int(b1 + (b2 - b1) * factor)
            return f"#{r >> 8:02x}{g >> 8:02x}{b >> 8:02x}"
        except (ValueError, TypeError, TclError):
            return self._resolve_color(c2)

    def animate_in(self, duration_ms: int = 250):
        start_color = self._resolve_color(self.master.cget("fg_color"))
        end_color = self._resolve_color(self.cget("fg_color"))

        steps = max(1, int(duration_ms / 15))  # Viser ~66 FPS
        self.configure(fg_color=start_color)

        def animation_step(current_step: int):
            if not self.winfo_exists(): return

            factor = current_step / steps
            new_color = self._interpolate_color(start_color, end_color, factor)
            self.configure(fg_color=new_color)

            if current_step < steps:
                self.after(15, lambda: animation_step(current_step + 1))

        animation_step(0)

    def animate_out_and_destroy(self, duration_ms: int = 250):
        start_color = self._resolve_color(self.cget("fg_color"))
        end_color = self._resolve_color(self.master.cget("fg_color"))
        start_border_color = self._resolve_color(self.cget("border_color"))

        if self.id_demande in self.main_view.helper.remboursement_widgets:
            self.main_view.helper.remboursement_widgets.pop(self.id_demande, None)

        steps = max(1, int(duration_ms / 15))

        def animation_step(current_step: int):
            if not self.winfo_exists(): return

            factor = current_step / steps
            new_color = self._interpolate_color(start_color, end_color, factor)
            new_border_color = self._interpolate_color(start_border_color, end_color, factor)

            self.configure(fg_color=new_color, border_color=new_border_color)

            if current_step < steps:
                self.after(15, lambda: animation_step(current_step + 1))
            else:
                self.destroy()

        animation_step(0)

    def flash_update(self, new_data):
        self.configure(border_color=COULEUR_BORDURE_FLASH, border_width=3)
        self.update_content(new_data)
        self.after(1500, self._restore_border_color)

    def _restore_border_color(self):
        if self.winfo_exists(): self._setup_item_colors_and_ui()

    def est_admin(self) -> bool:
        return "admin" in self.user_roles

    def est_comptable_tresorerie(self) -> bool:
        return "comptable_tresorerie" in self.user_roles

    def est_validateur_chef(self) -> bool:
        return "validateur_chef" in self.user_roles

    def est_comptable_fournisseur(self) -> bool:
        return "comptable_fournisseur" in self.user_roles

    def _is_active_for_user(self):
        status = self.demande_data.get("statut")
        created_by = self.demande_data.get("cree_par")
        return (self.est_comptable_tresorerie() and status == STATUT_CREEE) or \
            ((self.current_user_name == created_by or self.est_admin()) and status == STATUT_REFUSEE_CONSTAT_TP) or \
            ((self.est_validateur_chef() or self.est_admin()) and status == STATUT_TROP_PERCU_CONSTATE) or \
            ((
                         self.est_comptable_tresorerie() or self.est_admin()) and status == STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO) or \
            ((self.est_comptable_fournisseur() or self.est_admin()) and status == STATUT_VALIDEE)