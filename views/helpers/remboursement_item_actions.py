import copy
import datetime
from tkinter import messagebox

from config.settings import (
    STATUT_REFUSEE_CONSTAT_TP,
    STATUT_VALIDEE,
    STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_PAIEMENT_EFFECTUE,
    STATUT_ANNULEE,
    STATUT_CREEE, STATUT_TROP_PERCU_CONSTATE
)
from views.dialogs.comment_dialog import CommentDialog


class RemboursementItemActions:
    def __init__(self, item_view):
        self.view = item_view
        self.app_controller = item_view.app_controller
        self.remboursement_controller = item_view.remboursement_controller

    def _perform_optimistic_workflow_action(self, action_func, new_status: str, new_comment: str,
                                            success_message: str):
        original_data = copy.deepcopy(self.view.demande_data)
        self.view.demande_data['statut'] = new_status
        self.view.demande_data['derniere_modification_par'] = self.view.current_user_name
        now_iso = datetime.datetime.now().isoformat()
        self.view.demande_data['date_derniere_modification'] = now_iso
        new_hist_entry = {'statut': new_status, 'date': now_iso, 'par_utilisateur': self.view.current_user_name,
                          'commentaire': new_comment}
        if 'historique_statuts' not in self.view.demande_data:
            self.view.demande_data['historique_statuts'] = []
        self.view.demande_data['historique_statuts'].append(new_hist_entry)

        self.view._build_ui_content()
        self.view._show_local_loading(True)

        def on_complete(result, error):
            self.view._show_local_loading(False)
            if error or not (result and result[0]):
                self.app_controller.show_toast(f"Erreur: {error or (result and result[1])}", "error")
                self.view.update_content(original_data)
            else:
                self.app_controller.show_toast(success_message, "success")
                self.view.refresh_list_callback()

        self.view.run_task(action_func, on_complete, show_overlay=False)

    def accepter_constat_tp(self):
        from views.dialogs.acceptation_constat_dialog import AcceptationConstatDialog
        dialog = AcceptationConstatDialog(self.view, self.remboursement_controller, self.view.id_demande,
                                          self.app_controller)
        self.view.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.view.refresh_list_callback()

    def refuser_constat_tp(self):
        dialog = CommentDialog(self.view, title="Refus du Constat", prompt="Motif du refus :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_optimistic_workflow_action(
                lambda: self.remboursement_controller.mlupo_refuser_constat(self.view.id_demande, commentaire),
                STATUT_REFUSEE_CONSTAT_TP, commentaire, "Constat refusé et renvoyé au demandeur.")

    def valider_demande(self):
        dialog = CommentDialog(self.view, title="Validation", prompt="Commentaire (optionnel) :", is_mandatory=False)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_optimistic_workflow_action(
                lambda: self.remboursement_controller.jdurousset_valider_demande(self.view.id_demande, commentaire),
                STATUT_VALIDEE, commentaire or "Validé par le responsable.", "Demande validée avec succès.")

    def refuser_demande(self):
        dialog = CommentDialog(self.view, title="Refus de la Demande", prompt="Motif du refus :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_optimistic_workflow_action(
                lambda: self.remboursement_controller.jdurousset_refuser_demande(self.view.id_demande, commentaire),
                STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO, commentaire, "Demande refusée et renvoyée pour correction.")

    def confirmer_paiement(self):
        dialog = CommentDialog(self.view, title="Confirmation Paiement", prompt="Commentaire (optionnel) :",
                               is_mandatory=False)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_optimistic_workflow_action(
                lambda: self.remboursement_controller.pdiop_confirmer_paiement_effectue(self.view.id_demande,
                                                                                        commentaire),
                STATUT_PAIEMENT_EFFECTUE, commentaire or "Paiement effectué.", "Paiement confirmé.")

    def annuler_demande(self):
        dialog = CommentDialog(self.view, title="Annulation", prompt="Raison de l'annulation :", is_mandatory=True)
        commentaire = dialog.get_comment()
        if commentaire is not None:
            self._perform_optimistic_workflow_action(
                lambda: self.remboursement_controller.pneri_annuler_demande(self.view.id_demande, commentaire),
                STATUT_ANNULEE, commentaire, "Demande annulée.")

    def resoumettre_demande(self):
        from views.dialogs.resoumission_demande_dialog import ResoumissionDemandeDialog
        dialog = ResoumissionDemandeDialog(self.view, self.remboursement_controller, self.view.id_demande,
                                           self.app_controller)
        self.view.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.view.refresh_list_callback()

    def resoumettre_constat(self):
        from views.dialogs.resoumission_constat_dialog import ResoumissionConstatDialog
        dialog = ResoumissionConstatDialog(self.view, self.remboursement_controller, self.view.id_demande,
                                           self.app_controller)
        self.view.winfo_toplevel().wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.view.refresh_list_callback()

    def supprimer_demande(self):
        if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer la demande {self.view.id_demande}?",
                               icon='warning', parent=self.view):
            self.view.animate_out_and_destroy()

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur de suppression: {error}", "error")
                    self.view.refresh_list_callback()
                else:
                    self.app_controller.show_toast("Demande supprimée.", "success")

            # --- CORRECTION ICI ---
            # On lance la tâche sur la vue principale (self.view.main_view) qui ne sera pas détruite.
            self.view.main_view.run_task(lambda: self.remboursement_controller.supprimer_demande(self.view.id_demande),
                                         on_complete, show_overlay=False)

    def archiver_manuellement(self):
        if messagebox.askyesno("Archivage", f"Voulez-vous archiver manuellement la demande {self.view.id_demande}?",
                               parent=self.view):
            # De même, on utilise le run_task de la vue principale
            self.view.main_view.run_task(
                lambda: self.remboursement_controller.admin_manual_archive(self.view.id_demande),
                lambda r, e: self.view.refresh_list_callback() if not e and r and r[0] else None,
                show_overlay=False)

    def get_workflow_buttons(self):
        buttons = []
        statut_actuel = self.view.demande_data.get("statut")
        cree_par = self.view.demande_data.get("cree_par")
        btn_base = {"fg_color": None, "hover_color": None}

        if self.view.est_comptable_tresorerie() and statut_actuel == STATUT_CREEE:
            buttons.append(
                {**btn_base, "text": "Accepter (Constat TP)", "command": self.accepter_constat_tp, "fg_color": "green",
                 "hover_color": "darkgreen"})
            buttons.append(
                {**btn_base, "text": "Refuser (Constat TP)", "command": self.refuser_constat_tp, "fg_color": "orange",
                 "hover_color": "darkorange"})

        if (self.view.est_validateur_chef() or self.view.est_admin()) and statut_actuel == STATUT_TROP_PERCU_CONSTATE:
            buttons.append({**btn_base, "text": "Valider Demande", "command": self.valider_demande, "fg_color": "blue",
                            "hover_color": "darkblue"})
            buttons.append(
                {**btn_base, "text": "Refuser Demande", "command": self.refuser_demande, "fg_color": "orange",
                 "hover_color": "darkorange"})

        if (self.view.est_comptable_fournisseur() or self.view.est_admin()) and statut_actuel == STATUT_VALIDEE:
            buttons.append(
                {**btn_base, "text": "Confirmer Paiement", "command": self.confirmer_paiement, "fg_color": "#006400",
                 "hover_color": "#004d00"})

        if (
                self.view.current_user_name == cree_par or self.view.est_admin()) and statut_actuel == STATUT_REFUSEE_CONSTAT_TP:
            buttons.append(
                {**btn_base, "text": "Corriger Demande", "command": self.resoumettre_demande, "fg_color": "teal"})
            buttons.append(
                {**btn_base, "text": "Annuler Demande", "command": self.annuler_demande, "fg_color": "#D32F2F",
                 "hover_color": "#B71C1C"})

        if (
                self.view.est_comptable_tresorerie() or self.view.est_admin()) and statut_actuel == STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO:
            buttons.append(
                {**btn_base, "text": "Corriger Constat TP", "command": self.resoumettre_constat, "fg_color": "teal"})

        return buttons