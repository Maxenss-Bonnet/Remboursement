import os
import customtkinter as ctk
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.document_viewer import DocumentViewerWindow


class DocumentHistoryViewer(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, demande_data: dict, remboursement_controller, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.demande_data = demande_data
        self.remboursement_controller = remboursement_controller
        self.app_controller = app_controller
        self.id_demande = self.demande_data.get("id_demande")

        self.title(f"Historique des Documents - Demande {self.id_demande[:8]}")
        self.geometry("700x500")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)

        main_frame = ctk.CTkScrollableFrame(self)
        main_frame.pack(expand=True, fill="both", padx=10, pady=10)

        label_font = ctk.CTkFont(weight="bold")

        chemins_factures_rel = self.demande_data.get("chemins_factures_stockees", [])
        if chemins_factures_rel:
            ctk.CTkLabel(main_frame, text="Historique des Factures:", font=label_font).pack(anchor="w", pady=(10, 5))
            for idx, rel_path in enumerate(chemins_factures_rel):
                self._creer_ligne_document(main_frame, f"Version {idx + 1}", rel_path)

        chemins_ribs_rel = self.demande_data.get("chemins_rib_stockes", [])
        if chemins_ribs_rel:
            ctk.CTkLabel(main_frame, text="Historique des RIBs:", font=label_font).pack(anchor="w", pady=(15, 5))
            for idx, rel_path in enumerate(chemins_ribs_rel):
                self._creer_ligne_document(main_frame, f"Version {idx + 1}", rel_path)

        chemins_trop_percu_rel = self.demande_data.get("chemins_trop_percu_stockees", [])
        if chemins_trop_percu_rel:
            ctk.CTkLabel(main_frame, text="Historique des Preuves de Trop-Perçu:", font=label_font).pack(anchor="w",
                                                                                                         pady=(15, 5))
            for idx, rel_path in enumerate(chemins_trop_percu_rel):
                self._creer_ligne_document(main_frame, f"Version {idx + 1}", rel_path)

        if not chemins_factures_rel and not chemins_ribs_rel and not chemins_trop_percu_rel:
            ctk.CTkLabel(main_frame, text="Aucun document historisé pour cette demande.").pack(pady=20)

        close_button = ctk.CTkButton(self, text="Fermer", command=self.destroy)
        close_button.pack(pady=10)

    def _creer_ligne_document(self, parent, version_text, rel_path):
        item_frame = ctk.CTkFrame(parent, fg_color="transparent")
        item_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(item_frame, text=f"{version_text}: {os.path.basename(rel_path)}").pack(side="left", padx=5)
        ctk.CTkButton(item_frame, text="DL", width=60,
                      command=lambda p=rel_path: self._telecharger_document(p)).pack(side="right", padx=2)
        ctk.CTkButton(item_frame, text="Voir", width=60,
                      command=lambda p=rel_path: self._voir_document(p)).pack(side="right", padx=2)

    def _voir_document(self, rel_path):
        cached_path = self.app_controller.cache_manager.get_cached_path(rel_path)
        if cached_path:
            DocumentViewerWindow(self, cached_path, f"Aperçu (Cache) - {os.path.basename(rel_path)}", temp_dir_to_clean=None)
            return

        def task():
            return self.remboursement_controller.get_viewable_attachment_path(self.id_demande, rel_path)

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

    def _telecharger_document(self, rel_path):
        def task():
            return self.remboursement_controller.get_viewable_attachment_path(self.id_demande, rel_path)

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