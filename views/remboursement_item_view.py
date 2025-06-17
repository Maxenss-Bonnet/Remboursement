import os
import re
import customtkinter as ctk
from tkinter import messagebox

from config.settings import (
    STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_ANNULEE, STATUT_PAIEMENT_EFFECTUE
)
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.dialogs.comment_dialog import CommentDialog

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

        self._setup_item_colors_and_ui()

    def flash_update(self, new_data):
        self.configure(border_color=COULEUR_BORDURE_FLASH, border_width=3)
        self.update_content(new_data)
        self.after(1500, self._restore_border_color)

    def _restore_border_color(self):
        if self.winfo_exists():
            self._setup_item_colors_and_ui()

    def run_task(self, task_function, on_complete, loading_message="Mise à jour...", show_overlay=True):
        if self.content_frame and self.content_frame.winfo_manager():
            self.content_frame.pack_forget()
        super().run_task(task_function, on_complete, loading_message, show_overlay)

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

        if self._est_comptable_tresorerie() and current_status == STATUT_CREEE:
            return True
        if (
                self.current_user_name == cree_par_user or self._est_admin()) and current_status == STATUT_REFUSEE_CONSTAT_TP:
            return True
        if (self._est_validateur_chef() or self._est_admin()) and current_status == STATUT_TROP_PERCU_CONSTATE:
            return True
        if (
                self._est_comptable_tresorerie() or self._est_admin()) and current_status == STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO:
            return True
        if (self._est_comptable_fournisseur() or self._est_admin()) and current_status == STATUT_VALIDEE:
            return True
        return False

    def _setup_item_colors_and_ui(self):
        is_active_for_user = self._is_active_for_user()
        current_status = self.demande_data.get("statut")

        item_fg_color_to_set = "transparent"
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
        if self.content_frame:
            self.content_frame.destroy()

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
        add_basic_info_row("Créée le:", self.demande_data.get('date_creation', 'N/A'))
        add_basic_info_row("Modifiée par:", self.demande_data.get('derniere_modification_par', 'N/A'))
        add_basic_info_row("Statut Actuel:", self.demande_data.get('statut', 'Non défini'))
        if self.demande_data.get('date_paiement_effectue'):
            add_basic_info_row("Paiement le:", self.demande_data['date_paiement_effectue'], text_color="lightgreen")

        historique_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        historique_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 5), pady=5)
        ctk.CTkLabel(historique_frame, text="Historique/Commentaires:", font=label_font_info).pack(anchor="w",
                                                                                                   pady=(0, 2))
        hist_text_box = ctk.CTkTextbox(historique_frame, height=110, fg_color="gray20", border_width=1,
                                       activate_scrollbars=True)
        hist_text_box.pack(fill="both", expand=True, pady=(0, 2))
        historique = self.demande_data.get('historique_statuts', [])
        hist_text_box.configure(state="normal")
        hist_text_box.delete("1.0", "end")
        if historique:
            for entree_hist in reversed(historique):
                hist_text_box.insert("end",
                                     f"{entree_hist.get('date', 'N/A')} - {entree_hist.get('par_utilisateur', 'Système')}:\n")
                if entree_hist.get('statut'): hist_text_box.insert("end", f"  Statut: {entree_hist.get('statut')}\n")
                if entree_hist.get('commentaire', '').strip(): hist_text_box.insert("end",
                                                                                    f"  Commentaire: {entree_hist.get('commentaire').strip()}\n")
                hist_text_box.insert("end", "----\n")
        else:
            hist_text_box.insert("end", "Aucun historique.")
        hist_text_box.configure(state="disabled")

        action_buttons_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        action_buttons_frame.grid(row=0, column=2, sticky="nsew", padx=(5, 8), pady=5)
        self._populate_documents_buttons(action_buttons_frame)

        statut_actuel = self.demande_data.get("statut")
        buttons_to_add = self._get_workflow_buttons(statut_actuel)
        if buttons_to_add:
            workflow_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
            workflow_frame.grid(row=1, column=0, columnspan=3, pady=(8, 4), sticky="ew")
            workflow_frame.grid_columnconfigure(0, weight=1)
            inner_buttons_frame = ctk.CTkFrame(workflow_frame, fg_color="transparent")
            inner_buttons_frame.grid(row=0, column=0)
            btn_width_action = 150
            for text, command, fg_color, hover_color in buttons_to_add:
                ctk.CTkButton(inner_buttons_frame, text=text, width=btn_width_action, fg_color=fg_color,
                              hover_color=hover_color, command=command).pack(side="left", padx=5)

        if self._est_admin():
            admin_actions_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
            admin_actions_frame.grid(row=2, column=0, columnspan=3, pady=(4, 8), sticky="e")
            self._populate_admin_buttons(admin_actions_frame, statut_actuel)

    def _sort_files_by_version(self, file_paths):
        def get_version(path):
            match = re.search(r'_v(\d+)', os.path.basename(path))
            return int(match.group(1)) if match else 0

        return sorted(file_paths, key=get_version)

    def _populate_documents_buttons(self, parent_frame):
        parent_frame.grid_columnconfigure(0, weight=1)
        btn_width_dl = 40

        def add_doc_row(label_text, file_list):
            if not file_list:
                ctk.CTkLabel(parent_frame, text=f"{label_text}: N/A", font=ctk.CTkFont(size=12, slant="italic")).pack(
                    fill="x", pady=2, padx=5, anchor="w")
                return
            sorted_file_list = self._sort_files_by_version(file_list)
            latest_file = sorted_file_list[-1]
            ctk.CTkLabel(parent_frame, text=label_text, font=ctk.CTkFont(size=12, weight="bold")).pack(fill="x",
                                                                                                       pady=(5, 0),
                                                                                                       padx=5,
                                                                                                       anchor="w")
            button_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            button_frame.pack(fill="x", expand=True)
            button_frame.grid_columnconfigure(0, weight=1)
            btn_voir = ctk.CTkButton(button_frame, text="Voir",
                                     command=lambda p=latest_file: self.main_view._action_voir_pj(self.id_demande, p))
            btn_voir.grid(row=0, column=0, sticky="ew", padx=(0, 2))
            btn_dl = ctk.CTkButton(button_frame, text="DL", width=btn_width_dl, fg_color="gray50",
                                   command=lambda p=latest_file: self.main_view._action_telecharger_pj(self.id_demande,
                                                                                                       p))
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
        buttons = []
        cree_par = self.demande_data.get("cree_par")
        if self._est_comptable_tresorerie() and statut_actuel == STATUT_CREEE:
            buttons.append(("Accepter (Constat TP)", lambda: self._action_mlupo_accepter(), "green", "darkgreen"))
            buttons.append(("Refuser (Constat TP)", lambda: self._action_mlupo_refuser(), "orange", "darkorange"))
        if (self._est_validateur_chef() or self._est_admin()) and statut_actuel == STATUT_TROP_PERCU_CONSTATE:
            buttons.append(("Valider Demande", lambda: self._action_jdurousset_valider(), "blue", "darkblue"))
            buttons.append(("Refuser Demande", lambda: self._action_jdurousset_refuser(), "orange", "darkorange"))
        if (self._est_comptable_fournisseur() or self._est_admin()) and statut_actuel == STATUT_VALIDEE:
            buttons.append(
                ("Confirmer Paiement", lambda: self._action_pdiop_confirmer_paiement(), "#006400", "#004d00"))
        if (self.current_user_name == cree_par or self._est_admin()) and statut_actuel == STATUT_REFUSEE_CONSTAT_TP:
            buttons.append(("Corriger Demande", lambda: self._action_pneri_resoumettre(), "teal", None))
            buttons.append(("Annuler Demande", lambda: self._action_pneri_annuler(), "#D32F2F", "#B71C1C"))
        if (
                self._est_comptable_tresorerie() or self._est_admin()) and statut_actuel == STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO:
            buttons.append(("Corriger Constat TP", lambda: self._action_mlupo_resoumettre_constat(), "teal", None))
        return buttons

    def _populate_admin_buttons(self, parent_frame, statut_actuel):
        btn_width_action = 150
        is_archived = self.demande_data.get('is_archived', False)
        is_finished = statut_actuel in [STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE]
        if not is_archived and is_finished:
            ctk.CTkButton(parent_frame, text="Archiver Manuellement", width=btn_width_action, fg_color="#6c757d",
                          hover_color="#5a6268", command=self._action_admin_manual_archive).pack(side="right",
                                                                                                 padx=(5, 5))
        ctk.CTkButton(parent_frame, text="Supprimer (Admin)", width=btn_width_action, fg_color="red",
                      hover_color="darkred", command=self._action_supprimer_demande).pack(side="right", padx=(0, 5))

    def _perform_workflow_action(self, action_func, loading_message="Mise à jour..."):
        def on_complete(result, error):
            if self.content_frame:
                self.content_frame.pack(fill="both", expand=True, padx=1, pady=1)
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", "error")
                return
            success, message = result
            if success:
                self.app_controller.show_toast(message, "success")
                self.refresh_list_callback(show_overlay=False)
            else:
                self.app_controller.show_toast(message, "error")

        self.run_task(action_func, on_complete, loading_message)

    def _action_mlupo_accepter(self):
        from views.dialogs.acceptation_constat_dialog import AcceptationConstatDialog
        dialog = AcceptationConstatDialog(self, self.remboursement_controller, self.id_demande, self.app_controller)
        self.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.refresh_list_callback()

    def _action_mlupo_refuser(self):
        dialog = CommentDialog(self, title="Refus du Constat", prompt="Motif du refus :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_workflow_action(
                lambda: self.remboursement_controller.mlupo_refuser_constat(self.id_demande, commentaire))

    def _action_jdurousset_valider(self):
        dialog = CommentDialog(self, title="Validation", prompt="Commentaire (optionnel) :", is_mandatory=False)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_workflow_action(
                lambda: self.remboursement_controller.jdurousset_valider_demande(self.id_demande, commentaire))

    def _action_jdurousset_refuser(self):
        dialog = CommentDialog(self, title="Refus de la Demande", prompt="Motif du refus :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_workflow_action(
                lambda: self.remboursement_controller.jdurousset_refuser_demande(self.id_demande, commentaire))

    def _action_pdiop_confirmer_paiement(self):
        dialog = CommentDialog(self, title="Confirmation Paiement", prompt="Commentaire (optionnel) :",
                               is_mandatory=False)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_workflow_action(
                lambda: self.remboursement_controller.pdiop_confirmer_paiement_effectue(self.id_demande, commentaire))

    def _action_pneri_annuler(self):
        dialog = CommentDialog(self, title="Annulation", prompt="Raison de l'annulation :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_workflow_action(
                lambda: self.remboursement_controller.pneri_annuler_demande(self.id_demande, commentaire))

    def _action_pneri_resoumettre(self):
        from views.dialogs.resoumission_demande_dialog import ResoumissionDemandeDialog
        dialog = ResoumissionDemandeDialog(self, self.remboursement_controller, self.id_demande, self.app_controller)
        self.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.refresh_list_callback()

    def _action_mlupo_resoumettre_constat(self):
        from views.dialogs.resoumission_constat_dialog import ResoumissionConstatDialog
        dialog = ResoumissionConstatDialog(self, self.remboursement_controller, self.id_demande, self.app_controller)
        self.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.refresh_list_callback()

    def _action_supprimer_demande(self):
        if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer la demande {self.id_demande}?",
                               icon='warning', parent=self):
            self._perform_workflow_action(lambda: self.remboursement_controller.supprimer_demande(self.id_demande))

    def _action_admin_manual_archive(self):
        if messagebox.askyesno("Archivage", f"Voulez-vous archiver manuellement la demande {self.id_demande}?",
                               parent=self):
            self._perform_workflow_action(lambda: self.remboursement_controller.admin_manual_archive(self.id_demande))