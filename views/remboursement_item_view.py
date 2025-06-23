import os
import re
import copy
import customtkinter as ctk
import datetime
from tkinter import messagebox, TclError

from config.settings import (
    STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_ANNULEE, STATUT_PAIEMENT_EFFECTUE
)
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.dialogs.comment_dialog import CommentDialog
from utils import icon_renderer

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

        self.id_demande = self.demande_data.get("id_demande")
        self.content_frame = None
        self.original_border_color = COULEUR_BORDURE_DEFAUT
        self.workflow_frame = None

        self.master_scrollable_frame = master

        self._setup_item_colors_and_ui()

    def _propagate_scroll(self, event):
        if self.master_scrollable_frame:
            self.master_scrollable_frame._parent_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _bind_scroll_to_children(self, widget):
        widget.bind("<MouseWheel>", self._propagate_scroll)
        for child in widget.winfo_children():
            # Ne pas lier les évènements pour les widgets déjà scrollables comme le CTkScrollableFrame de l'historique
            if not isinstance(child, ctk.CTkScrollableFrame):
                child.bind("<MouseWheel>", self._propagate_scroll)
                self._bind_scroll_to_children(child)

    def _resolve_color(self, color_val):
        try:
            if isinstance(color_val, (list, tuple)):
                return color_val[1] if ctk.get_appearance_mode() == "Dark" else color_val[0]
            if isinstance(color_val, str) and " " in color_val:
                parts = color_val.split(" ")
                return parts[1] if ctk.get_appearance_mode() == "Dark" else parts[0]
            return color_val
        except (AttributeError, IndexError):
            return color_val

    def _interpolate_color(self, color1: str, color2: str, factor: float) -> str:
        try:
            resolved_c1 = self._resolve_color(color1)
            resolved_c2 = self._resolve_color(color2)
            c1_rgb = self.winfo_rgb(resolved_c1)
            c2_rgb = self.winfo_rgb(resolved_c2)
            r = int(c1_rgb[0] + (c2_rgb[0] - c1_rgb[0]) * factor)
            g = int(c1_rgb[1] + (c2_rgb[1] - c1_rgb[1]) * factor)
            b = int(c1_rgb[2] + (c2_rgb[2] - c1_rgb[2]) * factor)
            return f"#{r >> 8:02x}{g >> 8:02x}{b >> 8:02x}"
        except (ValueError, TypeError, TclError):
            return self._resolve_color(color2)

    def animate_in(self, duration_ms: int = 300):
        start_color = self.master.cget("fg_color")
        end_color = self.cget("fg_color")
        if end_color == "transparent":
            end_color = self._resolve_color(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        steps = max(1, int(duration_ms / 15))
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
        steps = max(1, int(duration_ms / 20))
        start_color = self.cget("fg_color")
        if start_color == "transparent":
            start_color = self._resolve_color(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        end_color = self.master.cget("fg_color")
        self.main_view.remboursement_widgets.pop(self.id_demande, None)

        def animation_step(current_step: int):
            if not self.winfo_exists(): return
            factor = current_step / steps
            new_color = self._interpolate_color(start_color, end_color, factor)
            self.configure(fg_color=new_color, border_color=new_color, height=self.winfo_height() * (1 - factor))
            if current_step < steps:
                self.after(20, lambda: animation_step(current_step + 1))
            else:
                self.destroy()

        animation_step(0)

    def _on_history_scroll(self, event, scroll_frame):
        scroll_amount = 5
        if event.num == 4 or event.delta > 0:
            scroll_frame._parent_canvas.yview_scroll(-scroll_amount, "units")
        elif event.num == 5 or event.delta < 0:
            scroll_frame._parent_canvas.yview_scroll(scroll_amount, "units")
        return "break"

    def flash_update(self, new_data):
        self.configure(border_color=COULEUR_BORDURE_FLASH, border_width=3)
        self.update_content(new_data)
        self.after(1500, self._restore_border_color)

    def _restore_border_color(self):
        if self.winfo_exists():
            self._setup_item_colors_and_ui()

    def update_content(self, demande_data: dict):
        self.demande_data = demande_data
        self.id_demande = self.demande_data.get("id_demande")
        if self.content_frame:
            self.content_frame.destroy()
        self.content_frame = None
        self._setup_item_colors_and_ui()

    def _est_admin(self) -> bool:
        return "admin" in self.user_roles

    def _est_comptable_tresorerie(self) -> bool:
        return "comptable_tresorerie" in self.user_roles

    def _est_validateur_chef(self) -> bool:
        return "validateur_chef" in self.user_roles

    def _est_comptable_fournisseur(self) -> bool:
        return "comptable_fournisseur" in self.user_roles

    def _is_active_for_user(self):
        current_status = self.demande_data.get("statut")
        cree_par_user = self.demande_data.get("cree_par")
        if self._est_comptable_tresorerie() and current_status == STATUT_CREEE: return True
        if (
                self.current_user_name == cree_par_user or self._est_admin()) and current_status == STATUT_REFUSEE_CONSTAT_TP: return True
        if (
                self._est_validateur_chef() or self._est_admin()) and current_status == STATUT_TROP_PERCU_CONSTATE: return True
        if (
                self._est_comptable_tresorerie() or self._est_admin()) and current_status == STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO: return True
        if (self._est_comptable_fournisseur() or self._est_admin()) and current_status == STATUT_VALIDEE: return True
        return False

    def _setup_item_colors_and_ui(self):
        is_active_for_user = self._is_active_for_user()
        current_status = self.demande_data.get("statut")
        item_fg_color_to_set = self._resolve_color(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        border_color_to_set = COULEUR_BORDURE_DEFAUT
        border_width_to_set = 1
        if current_status == STATUT_ANNULEE:
            item_fg_color_to_set = COULEUR_DEMANDE_ANNULEE
            border_color_to_set = COULEUR_BORDURE_ANNULEE
            border_width_to_set = 2
        elif current_status == STATUT_PAIEMENT_EFFECTUE:
            item_fg_color_to_set = COULEUR_DEMANDE_TERMINEE
            border_color_to_set = COULEUR_BORDURE_TERMINEE
            border_width_to_set = 2
        elif is_active_for_user:
            item_fg_color_to_set = COULEUR_ACTIVE_POUR_UTILISATEUR
            border_color_to_set = COULEUR_BORDURE_ACTIVE
            border_width_to_set = 2
        self.original_border_color = border_color_to_set
        self.configure(border_width=border_width_to_set, fg_color=item_fg_color_to_set,
                       border_color=border_color_to_set)
        self._build_ui_content()

    def _build_ui_content(self):
        if self.content_frame: self.content_frame.destroy()
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_frame.pack(fill="both", expand=True, padx=1, pady=1)
        self.content_frame.grid_columnconfigure(0, weight=2, minsize=280)
        self.content_frame.grid_columnconfigure(1, weight=3, minsize=300)
        self.content_frame.grid_columnconfigure(2, weight=0, minsize=180)
        basic_info_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        basic_info_frame.grid(row=0, column=0, sticky="nsew", padx=(8, 5), pady=5)
        basic_info_frame.grid_columnconfigure(1, weight=1)
        row_idx_info = 0
        label_font_info = ctk.CTkFont(weight="bold", size=12)
        value_font_info = ctk.CTkFont(size=13)

        def add_basic_info_row(label_text, value_text, text_color=None):
            nonlocal row_idx_info
            ctk.CTkLabel(basic_info_frame, text=label_text, font=label_font_info, anchor="w").grid(row=row_idx_info,
                                                                                                   column=0,
                                                                                                   sticky="nw",
                                                                                                   padx=(5, 2),
                                                                                                   pady=(2, 2))
            val_label = ctk.CTkLabel(basic_info_frame, text=value_text, font=value_font_info, anchor="w",
                                     justify="left", wraplength=0, text_color=text_color)
            val_label.grid(row=row_idx_info, column=1, sticky="ew", padx=(5, 2), pady=(2, 2))
            row_idx_info += 1

        add_basic_info_row("Patient:",
                           f"{self.demande_data.get('nom', 'N/A')} {self.demande_data.get('prenom', 'N/A')}")
        add_basic_info_row("Réf. Facture:", self.demande_data.get('reference_facture', 'N/A'))
        add_basic_info_row("Montant:", f"{self.demande_data.get('montant_demande', 0.0):.2f} €")
        add_basic_info_row("Créée par:", self.demande_data.get('cree_par') or 'Utilisateur supprimé')
        add_basic_info_row("Créée le:", self.demande_data.get('date_creation', 'N/A'))
        add_basic_info_row("Modifiée par:",
                           self.demande_data.get('derniere_modification_par') or 'Utilisateur supprimé')
        add_basic_info_row("Statut Actuel:", self.demande_data.get('statut', 'Non défini'))
        if self.demande_data.get('date_paiement_effectue'): add_basic_info_row("Paiement le:", self.demande_data[
            'date_paiement_effectue'], text_color="lightgreen")
        hist_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        hist_container.grid(row=0, column=1, sticky="nsew", padx=(5, 5), pady=5)
        ctk.CTkLabel(hist_container, text="Historique/Commentaires:", font=label_font_info).pack(anchor="w",
                                                                                                 pady=(0, 2))
        hist_scroll_frame = ctk.CTkScrollableFrame(hist_container, fg_color="gray20", border_width=1, label_text="")
        hist_scroll_frame.pack(fill="both", expand=True)
        hist_widgets_to_bind = [hist_scroll_frame]
        historique = self.demande_data.get('historique_statuts', [])
        if not historique:
            no_hist_label = ctk.CTkLabel(hist_scroll_frame, text="Aucun historique.", font=value_font_info,
                                         text_color="gray60")
            no_hist_label.pack(pady=10);
            hist_widgets_to_bind.append(no_hist_label)
        else:
            with self.app_controller.pfp_cache_lock:
                pfp_cache = self.app_controller.preloaded_pfp_cache or {};
                default_pfp = pfp_cache.get('default')
                for i, entree_hist in enumerate(reversed(historique)):
                    user_str = entree_hist.get('par_utilisateur') or 'Système';
                    pfp_image = pfp_cache.get(user_str, default_pfp)
                    entry_frame = ctk.CTkFrame(hist_scroll_frame, fg_color="transparent");
                    entry_frame.pack(fill="x", expand=True, pady=(0, 10));
                    hist_widgets_to_bind.append(entry_frame)
                    pfp_label = ctk.CTkLabel(entry_frame, image=pfp_image, text="", width=20, height=20);
                    pfp_label.pack(side="left", anchor="n", padx=(5, 8), pady=3);
                    hist_widgets_to_bind.append(pfp_label)
                    details_frame = ctk.CTkFrame(entry_frame, fg_color="transparent");
                    details_frame.pack(side="left", fill="x", expand=True);
                    hist_widgets_to_bind.append(details_frame)
                    try:
                        date_obj = datetime.datetime.fromisoformat(str(entree_hist.get('date', 'N/A')).split('.')[0]);
                        formatted_date = date_obj.strftime('%d/%m/%y %H:%M')
                    except (ValueError, TypeError):
                        formatted_date = entree_hist.get('date', 'N/A')
                    header_label = ctk.CTkLabel(details_frame, text=f"{formatted_date} - {user_str}",
                                                font=ctk.CTkFont(size=11, weight="bold"), text_color="#C0C0C0",
                                                anchor="w");
                    header_label.pack(fill="x");
                    hist_widgets_to_bind.append(header_label)
                    statut_text = entree_hist.get('statut')
                    if statut_text:
                        statut_frame = ctk.CTkFrame(details_frame, fg_color="transparent");
                        statut_frame.pack(fill="x");
                        hist_widgets_to_bind.append(statut_frame)
                        icon = icon_renderer.get_icon_image(statut_text, 16)
                        if icon:
                            icon_label = ctk.CTkLabel(statut_frame, image=icon, text="");
                            icon_label.pack(side="left", padx=(0, 5), pady=2);
                            hist_widgets_to_bind.append(icon_label)
                        statut_label = ctk.CTkLabel(statut_frame, text=f"{statut_text}", font=ctk.CTkFont(size=12),
                                                    anchor="w");
                        statut_label.pack(side="left", fill="x");
                        hist_widgets_to_bind.append(statut_label)
                    comment_text = str(entree_hist.get('commentaire', '')).strip()
                    if comment_text:
                        comment_text += "\u00A0"
                        comment_label = ctk.CTkLabel(details_frame, text=comment_text, wraplength=400, justify="left",
                                                     font=ctk.CTkFont(size=12, slant="italic"), text_color="gray85",
                                                     anchor="w");
                        comment_label.pack(fill="x", pady=(2, 0));
                        hist_widgets_to_bind.append(comment_label)
                    if i < len(historique) - 1:
                        separator = ctk.CTkFrame(hist_scroll_frame, height=1, fg_color="gray40");
                        separator.pack(fill="x", padx=5, pady=5);
                        hist_widgets_to_bind.append(separator)
        for widget in hist_widgets_to_bind:
            widget.bind("<MouseWheel>", lambda e, hsf=hist_scroll_frame: self._on_history_scroll(e, hsf), add="+")
        action_buttons_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent");
        action_buttons_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 8), pady=5)
        self._populate_documents_buttons(action_buttons_frame)
        self._populate_workflow_buttons()
        if self._est_admin():
            admin_actions_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent");
            admin_actions_frame.grid(row=2, column=0, columnspan=3, pady=(4, 8), sticky="e")
            self._populate_admin_buttons(admin_actions_frame, self.demande_data.get("statut"))
        self._bind_scroll_to_children(self)

    def _populate_workflow_buttons(self):
        if self.workflow_frame and self.workflow_frame.winfo_exists(): self.workflow_frame.destroy()
        statut_actuel = self.demande_data.get("statut")
        buttons_to_add = self._get_workflow_buttons(statut_actuel)
        if buttons_to_add:
            self.workflow_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
            self.workflow_frame.grid(row=1, column=0, columnspan=3, pady=(8, 4), sticky="ew")
            self.workflow_frame.grid_columnconfigure(0, weight=1)
            inner_buttons_frame = ctk.CTkFrame(self.workflow_frame, fg_color="transparent")
            inner_buttons_frame.grid(row=0, column=0)
            btn_width_action = 150
            for btn_info in buttons_to_add:
                ctk.CTkButton(inner_buttons_frame, text=btn_info["text"], width=btn_width_action,
                              fg_color=btn_info["fg_color"], hover_color=btn_info["hover_color"],
                              command=btn_info["command"]).pack(side="left", padx=5)

    def _sort_files_by_version(self, file_paths):
        def get_version(path):
            match = re.search(r'_v(\d+)', os.path.basename(path));
            return int(match.group(1)) if match else 0

        return sorted(file_paths, key=get_version)

    def _populate_documents_buttons(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        btn_width_dl = 40

        def add_doc_row(label_text, file_list):
            if not file_list: ctk.CTkLabel(parent_frame, text=f"{label_text}: N/A",
                                           font=ctk.CTkFont(size=12, slant="italic")).pack(fill="x", pady=2, padx=5,
                                                                                           anchor="w"); return
            latest_file = self._sort_files_by_version(file_list)[-1]
            ctk.CTkLabel(parent_frame, text=label_text, font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x",
                                                                                                       pady=(5, 0),
                                                                                                       padx=5,
                                                                                                       anchor="w")
            button_frame = ctk.CTkFrame(parent_frame, fg_color="transparent");
            button_frame.pack(fill="x", expand=True);
            button_frame.grid_columnconfigure(0, weight=1)
            btn_voir = ctk.CTkButton(button_frame, text="Voir",
                                     command=lambda p=latest_file: self.main_view._action_voir_pj(self.id_demande, p));
            btn_voir.grid(row=0, column=0, sticky="ew", padx=(0, 2))
            btn_dl = ctk.CTkButton(button_frame, text="DL", width=btn_width_dl, fg_color="gray50",
                                   command=lambda p=latest_file: self.main_view._action_telecharger_pj(self.id_demande,
                                                                                                       p));
            btn_dl.grid(row=0, column=1, sticky="e")

        add_doc_row("Facture", self.demande_data.get("chemins_factures_stockees", []))
        add_doc_row("RIB", self.demande_data.get("chemins_rib_stockes", []))
        add_doc_row("Preuve TP", self.demande_data.get("chemins_trop_percu_stockees", []))
        if any(len(lst) > 1 for lst in [self.demande_data.get(k, []) for k in
                                        ["chemins_factures_stockees", "chemins_rib_stockes",
                                         "chemins_trop_percu_stockees"]]):
            ctk.CTkFrame(parent_frame, height=2, fg_color="gray50").pack(fill="x", pady=5, padx=10)
            ctk.CTkButton(parent_frame, text="Historique des Documents", fg_color="gray50",
                          command=lambda d=self.demande_data: self.main_view._action_voir_historique_docs(d)).pack(
                fill="x", padx=2, pady=(5, 0))

    def _get_workflow_buttons(self, statut_actuel):
        buttons = [];
        cree_par = self.demande_data.get("cree_par");
        btn_base = {"fg_color": None, "hover_color": None}
        if self._est_comptable_tresorerie() and statut_actuel == STATUT_CREEE:
            buttons.append({**btn_base, "text": "Accepter (Constat TP)", "command": self._action_mlupo_accepter,
                            "fg_color": "green", "hover_color": "darkgreen"})
            buttons.append({**btn_base, "text": "Refuser (Constat TP)", "command": self._action_mlupo_refuser,
                            "fg_color": "orange", "hover_color": "darkorange"})
        if (self._est_validateur_chef() or self._est_admin()) and statut_actuel == STATUT_TROP_PERCU_CONSTATE:
            buttons.append(
                {**btn_base, "text": "Valider Demande", "command": self._action_jdurousset_valider, "fg_color": "blue",
                 "hover_color": "darkblue"})
            buttons.append({**btn_base, "text": "Refuser Demande", "command": self._action_jdurousset_refuser,
                            "fg_color": "orange", "hover_color": "darkorange"})
        if (self._est_comptable_fournisseur() or self._est_admin()) and statut_actuel == STATUT_VALIDEE:
            buttons.append({**btn_base, "text": "Confirmer Paiement", "command": self._action_pdiop_confirmer_paiement,
                            "fg_color": "#006400", "hover_color": "#004d00"})
        if (self.current_user_name == cree_par or self._est_admin()) and statut_actuel == STATUT_REFUSEE_CONSTAT_TP:
            buttons.append(
                {**btn_base, "text": "Corriger Demande", "command": self._action_pneri_resoumettre, "fg_color": "teal"})
            buttons.append(
                {**btn_base, "text": "Annuler Demande", "command": self._action_pneri_annuler, "fg_color": "#D32F2F",
                 "hover_color": "#B71C1C"})
        if (
                self._est_comptable_tresorerie() or self._est_admin()) and statut_actuel == STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO:
            buttons.append(
                {**btn_base, "text": "Corriger Constat TP", "command": self._action_mlupo_resoumettre_constat,
                 "fg_color": "teal"})
        return buttons

    def _populate_admin_buttons(self, parent_frame, statut_actuel):
        btn_width_action = 150;
        is_archived = self.demande_data.get('is_archived', False);
        is_finished = statut_actuel in [STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE]
        if not is_archived and is_finished:
            ctk.CTkButton(parent_frame, text="Archiver Manuellement", width=btn_width_action, fg_color="#6c757d",
                          hover_color="#5a6268", command=self._action_admin_manual_archive).pack(side="right",
                                                                                                 padx=(5, 5))
        ctk.CTkButton(parent_frame, text="Supprimer (Admin)", width=btn_width_action, fg_color="red",
                      hover_color="darkred", command=self._action_supprimer_demande).pack(side="right", padx=(0, 5))

    def _perform_optimistic_workflow_action(self, action_func, new_status: str, new_comment: str, success_message: str):
        original_data = copy.deepcopy(self.demande_data)
        self.demande_data['statut'] = new_status
        self.demande_data['derniere_modification_par'] = self.current_user_name
        now_iso = datetime.datetime.now().isoformat()
        self.demande_data['date_derniere_modification'] = now_iso
        new_hist_entry = {'statut': new_status, 'date': now_iso, 'par_utilisateur': self.current_user_name,
                          'commentaire': new_comment}
        if 'historique_statuts' not in self.demande_data: self.demande_data['historique_statuts'] = []
        self.demande_data['historique_statuts'].append(new_hist_entry)
        self._build_ui_content()
        self._show_local_loading(True)

        def on_complete(result, error):
            self._show_local_loading(False)
            if error or not (result and result[0]):
                self.app_controller.show_toast(f"Erreur: {error or (result and result[1])}", "error")
                self.update_content(original_data)
            else:
                self.app_controller.show_toast(success_message, "success")
                self.update_content(self.demande_data)

        self.run_task(action_func, on_complete, show_overlay=False)

    def _show_local_loading(self, is_loading: bool):
        if not self.workflow_frame or not self.workflow_frame.winfo_exists(): return
        if is_loading:
            for widget in self.workflow_frame.winfo_children(): widget.destroy()
            progress_bar = ctk.CTkProgressBar(self.workflow_frame, mode='indeterminate');
            progress_bar.pack(pady=10, padx=20, fill='x');
            progress_bar.start()
        else:
            self._populate_workflow_buttons()

    def _action_mlupo_accepter(self):
        from views.dialogs.acceptation_constat_dialog import AcceptationConstatDialog
        dialog = AcceptationConstatDialog(self, self.remboursement_controller, self.id_demande, self.app_controller)
        self.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted: self.refresh_list_callback()

    def _action_mlupo_refuser(self):
        dialog = CommentDialog(self, title="Refus du Constat", prompt="Motif du refus :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None: self._perform_optimistic_workflow_action(
            lambda: self.remboursement_controller.mlupo_refuser_constat(self.id_demande, commentaire),
            STATUT_REFUSEE_CONSTAT_TP, commentaire, "Constat refusé et renvoyé au demandeur.")

    def _action_jdurousset_valider(self):
        dialog = CommentDialog(self, title="Validation", prompt="Commentaire (optionnel) :", is_mandatory=False)
        commentaire = dialog.get_comment()
        if commentaire is not None: self._perform_optimistic_workflow_action(
            lambda: self.remboursement_controller.jdurousset_valider_demande(self.id_demande, commentaire),
            STATUT_VALIDEE, commentaire or "Validé par le responsable.", "Demande validée avec succès.")

    def _action_jdurousset_refuser(self):
        dialog = CommentDialog(self, title="Refus de la Demande", prompt="Motif du refus :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None: self._perform_optimistic_workflow_action(
            lambda: self.remboursement_controller.jdurousset_refuser_demande(self.id_demande, commentaire),
            STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO, commentaire, "Demande refusée et renvoyée pour correction.")

    def _action_pdiop_confirmer_paiement(self):
        dialog = CommentDialog(self, title="Confirmation Paiement", prompt="Commentaire (optionnel) :",
                               is_mandatory=False)
        commentaire = dialog.get_comment()
        if commentaire is not None: self._perform_optimistic_workflow_action(
            lambda: self.remboursement_controller.pdiop_confirmer_paiement_effectue(self.id_demande, commentaire),
            STATUT_PAIEMENT_EFFECTUE, commentaire or "Paiement effectué.", "Paiement confirmé.")

    def _action_pneri_annuler(self):
        dialog = CommentDialog(self, title="Annulation", prompt="Raison de l'annulation :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None: self._perform_optimistic_workflow_action(
            lambda: self.remboursement_controller.pneri_annuler_demande(self.id_demande, commentaire), STATUT_ANNULEE,
            commentaire, "Demande annulée.")

    def _action_pneri_resoumettre(self):
        from views.dialogs.resoumission_demande_dialog import ResoumissionDemandeDialog
        dialog = ResoumissionDemandeDialog(self, self.remboursement_controller, self.id_demande, self.app_controller);
        self.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted: self.refresh_list_callback()

    def _action_mlupo_resoumettre_constat(self):
        from views.dialogs.resoumission_constat_dialog import ResoumissionConstatDialog
        dialog = ResoumissionConstatDialog(self, self.remboursement_controller, self.id_demande, self.app_controller);
        self.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted: self.refresh_list_callback()

    def _action_supprimer_demande(self):
        if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer la demande {self.id_demande}?",
                               icon='warning', parent=self):
            self.animate_out_and_destroy()

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur de suppression: {error}", "error")
                    self.refresh_list_callback()
                else:
                    self.app_controller.show_toast("Demande supprimée.", "success")

            self.run_task(lambda: self.remboursement_controller.supprimer_demande(self.id_demande), on_complete,
                          show_overlay=False)

    def _action_admin_manual_archive(self):
        if messagebox.askyesno("Archivage", f"Voulez-vous archiver manuellement la demande {self.id_demande}?",
                               parent=self):
            self.run_task(lambda: self.remboursement_controller.admin_manual_archive(self.id_demande),
                          lambda r, e: self.refresh_list_callback() if not e and r and r[0] else None,
                          show_overlay=False)