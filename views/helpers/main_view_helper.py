import os
import customtkinter as ctk
import logging
import math
from tkinter import messagebox, simpledialog

from views.document_viewer import DocumentViewerWindow
from views.remboursement_item_view import RemboursementItemView
from views.document_history_viewer import DocumentHistoryViewer
from views.admin_user_management_view import AdminUserManagementView
from views.help_view import HelpView
from views.profile_view import ProfileView
from views.dialogs.archive_date_range_dialog import ArchiveDateRangeDialog

_log = logging.getLogger(__name__)


class MainViewHelper:
    def __init__(self, main_view):
        self.view = main_view
        self.app_controller = main_view.app_controller
        self.remboursement_controller = main_view.remboursement_controller

        self.demandes_en_cache = {}
        self.remboursement_widgets = {}
        self.no_demandes_label = None
        self._is_refreshing = False
        self.current_page = 1
        self.total_items = 0
        self.total_pages = 1
        self.local_loading_frame = None

    def _show_local_loading(self, is_loading: bool):
        if is_loading:
            for widget in self.remboursement_widgets.values():
                if widget and widget.winfo_exists():
                    widget.destroy()
            self.remboursement_widgets.clear()
            if self.no_demandes_label and self.no_demandes_label.winfo_exists():
                self.no_demandes_label.destroy()

            if not self.local_loading_frame or not self.local_loading_frame.winfo_exists():
                self.local_loading_frame = ctk.CTkFrame(self.view.scrollable_frame_demandes, fg_color="transparent")
                self.local_loading_frame.grid(row=0, column=0, sticky="ew", pady=50)
                ctk.CTkLabel(self.local_loading_frame, text="Chargement des demandes...",
                             font=ctk.CTkFont(size=14)).pack(pady=5)
                progress_bar = ctk.CTkProgressBar(self.local_loading_frame, mode='indeterminate')
                progress_bar.pack(pady=10, padx=50, fill="x")
                progress_bar.start()
        else:
            if self.local_loading_frame and self.local_loading_frame.winfo_exists():
                for widget in self.local_loading_frame.winfo_children():
                    if isinstance(widget, ctk.CTkProgressBar):
                        widget.stop()
                    widget.destroy()
                self.local_loading_frame.destroy()
                self.local_loading_frame = None

    def afficher_liste_demandes(self, is_initial_load=False, force_refresh=False, show_loader=True):
        if self._is_refreshing:
            return

        self._is_refreshing = True
        self.view.bouton_rafraichir.configure(state="disabled")

        if is_initial_load:
            cache_key = f"{self.view.nom_utilisateur}_{self.view.current_filter}_default"
            cached_data = self.app_controller.cache_manager.get_demand_query_cache(cache_key)
            if cached_data and not force_refresh:
                _log.info("Affichage de la liste initiale à partir du cache.")
                self._on_demandes_loaded(cached_data)
                return

        if show_loader:
            self._show_local_loading(True)

        offset = (self.current_page - 1) * self.view.items_per_page

        def task():
            return self.remboursement_controller.get_demandes_filtrees_triees(
                user_roles=self.view.user_roles,
                filter_choice=self.view.current_filter,
                sort_choice=self.view.current_sort,
                search_term=self.view.search_var.get(),
                search_scope=self.view.search_scope_var.get(),
                is_archive_mode=self.view.is_archive_mode,
                archive_date_range=self.view.archive_date_range,
                limit=self.view.items_per_page,
                offset=offset
            )

        self.view.run_task(task_function=task, on_complete=self._on_demandes_loaded, loading_message="",
                           show_overlay=False)

    def _on_demandes_loaded(self, result, error=None):
        if self.local_loading_frame:
            self._show_local_loading(False)

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
            self.total_pages = math.ceil(
                self.total_items / self.view.items_per_page) if self.view.items_per_page > 0 else 1
            if self.total_pages == 0: self.total_pages = 1
            if self.current_page > self.total_pages: self.current_page = self.total_pages

            if self.no_demandes_label and self.no_demandes_label.winfo_exists():
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
                    master=self.view.scrollable_frame_demandes, main_view_instance=self.view,
                    demande_data=new_data_map[demande_id], current_user_name=self.view.nom_utilisateur,
                    user_roles=self.view.user_roles, app_controller=self.app_controller,
                    remboursement_controller=self.remboursement_controller,
                    refresh_list_callback=lambda: self.afficher_liste_demandes(force_refresh=True, show_loader=False)
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

            if not demandes_a_afficher and not self.local_loading_frame:
                self.no_demandes_label = ctk.CTkLabel(self.view.scrollable_frame_demandes,
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
            if self.view.bouton_rafraichir.winfo_exists():
                self.view.bouton_rafraichir.configure(state="normal")

    def _update_pagination_controls(self):
        for widget in self.view.pagination_frame.winfo_children():
            widget.destroy()

        if self.total_items == 0: return

        self.view.pagination_frame.grid_columnconfigure((0, 2), weight=1)
        self.view.pagination_frame.grid_columnconfigure(1, weight=0)

        buttons_frame = ctk.CTkFrame(self.view.pagination_frame, fg_color="transparent")
        buttons_frame.grid(row=0, column=1, pady=5)

        info_label_text = f"Page {self.current_page} sur {self.total_pages} ({self.total_items} résultats)"
        info_label = ctk.CTkLabel(self.view.pagination_frame, text=info_label_text, font=ctk.CTkFont(size=12))
        info_label.grid(row=0, column=0, sticky="e", padx=20)

        btn_first = ctk.CTkButton(buttons_frame, text="<<", width=40, command=lambda: self._go_to_page(1))
        btn_first.pack(side="left", padx=2)
        if self.current_page <= 1: btn_first.configure(state="disabled")

        btn_prev = ctk.CTkButton(buttons_frame, text="<", width=40,
                                 command=lambda: self._go_to_page(self.current_page - 1))
        btn_prev.pack(side="left", padx=2)
        if self.current_page <= 1: btn_prev.configure(state="disabled")

        start_page, end_page = max(1, self.current_page - 2), min(self.total_pages, self.current_page + 2)
        if end_page - start_page < 4:
            end_page = min(self.total_pages, start_page + 4)
            start_page = max(1, end_page - 4)

        if start_page > 1: ctk.CTkLabel(buttons_frame, text="...").pack(side="left", padx=2)
        for page_num in range(start_page, end_page + 1):
            btn_page = ctk.CTkButton(buttons_frame, text=str(page_num), width=30,
                                     command=lambda p=page_num: self._go_to_page(p))
            if page_num == self.current_page:
                btn_page.configure(fg_color="white", text_color="black", state="disabled")
            btn_page.pack(side="left", padx=2)
        if end_page < self.total_pages: ctk.CTkLabel(buttons_frame, text="...").pack(side="left", padx=2)

        btn_next = ctk.CTkButton(buttons_frame, text=">", width=40,
                                 command=lambda: self._go_to_page(self.current_page + 1))
        btn_next.pack(side="left", padx=2)
        if self.current_page >= self.total_pages: btn_next.configure(state="disabled")

        btn_last = ctk.CTkButton(buttons_frame, text=">>", width=40,
                                 command=lambda: self._go_to_page(self.total_pages))
        btn_last.pack(side="left", padx=2)
        if self.current_page >= self.total_pages: btn_last.configure(state="disabled")

    def _go_to_page(self, page_number):
        if 1 <= page_number <= self.total_pages:
            self.current_page = page_number
            self.afficher_liste_demandes(force_refresh=True, show_loader=True)

    def _update_notification_badge(self):
        count = sum(1 for d in self.demandes_en_cache.values() if self.view._is_active_for_user(d))
        if count > 0:
            self.view.notification_badge.configure(text=str(count))
            self.view.notification_badge.place(in_=self.view.bouton_rafraichir, relx=1.0, rely=0.0, anchor="ne")
        else:
            self.view.notification_badge.place_forget()

    def set_sort(self, sort_choice):
        self.view.current_sort = sort_choice
        self.current_page = 1
        self.afficher_liste_demandes(force_refresh=True, show_loader=True)

    def set_filter(self, filter_choice):
        self.view.current_filter = filter_choice
        self.current_page = 1
        self.afficher_liste_demandes(force_refresh=True, show_loader=True)

    def trigger_search_from_event(self, event=None):
        self.current_page = 1
        self.afficher_liste_demandes(force_refresh=True, show_loader=True)

    def clear_search(self):
        self.view.search_var.set("")
        self.current_page = 1
        self.afficher_liste_demandes(force_refresh=True, show_loader=True)

    def open_archive_dialog(self):
        dialog = ArchiveDateRangeDialog(self.view)
        date_range = dialog.get_range()
        if date_range:
            self.view.is_archive_mode = True
            self.view.archive_date_range = date_range
            self.current_page = 1
            self.view.search_var.set("")
            self.view._update_ui_for_archive_mode()
            self.afficher_liste_demandes(force_refresh=True, show_loader=True)

    def quit_archive_mode(self):
        self.view.is_archive_mode = False
        self.view.archive_date_range = None
        self.current_page = 1
        self.view._update_ui_for_archive_mode()
        self.afficher_liste_demandes(force_refresh=True, show_loader=True)

    def open_help_view(self):
        HelpView(self.view, self.view.nom_utilisateur, self.view.user_roles)

    def open_admin_user_management_view(self):
        AdminUserManagementView(self.view, self.app_controller)

    def open_profile_view(self):
        dialog = ProfileView(self.view, self.view.user_controller, self.app_controller,
                             self.view.user_data.model_dump(),
                             on_save_callback=self.view._on_profile_saved)
        self.view.wait_window(dialog)

    def ouvrir_fenetre_creation_demande(self):
        from views.dialogs.creation_demande_dialog import CreationDemandeDialog
        dialog = CreationDemandeDialog(self.view, self.remboursement_controller, self.app_controller)
        self.view.wait_window(dialog)
        if hasattr(dialog, 'submitted') and dialog.submitted:
            self.afficher_liste_demandes(force_refresh=True, show_loader=False)

    def action_voir_pj(self, demande_id, rel_path):
        cached_path = self.app_controller.cache_manager.get_cached_path(rel_path)
        if cached_path:
            DocumentViewerWindow(self.view, cached_path, f"Aperçu (Cache) - {os.path.basename(rel_path)}",
                                 temp_dir_to_clean=None)
            return

        def task():
            return self.remboursement_controller.get_viewable_attachment_path(demande_id, rel_path)

        def on_complete(result, error):
            if error: self.app_controller.show_toast(f"Erreur à l'ouverture : {error}", "error"); return
            chemin_pj, temp_dir = result
            if chemin_pj and os.path.exists(chemin_pj):
                self.app_controller.cache_manager.add_to_cache(chemin_pj, rel_path)
                DocumentViewerWindow(self.view, chemin_pj, f"Aperçu - {os.path.basename(rel_path)}",
                                     temp_dir_to_clean=temp_dir)
            else:
                self.app_controller.show_toast(f"Fichier non trouvé : {rel_path}", "error")

        self.view.run_task(task, on_complete, "Préparation du document...")

    def action_telecharger_pj(self, demande_id, rel_path):
        def task():
            return self.remboursement_controller.get_viewable_attachment_path(demande_id, rel_path)

        def on_complete(result, error):
            if error: self.app_controller.show_toast(f"Erreur : {error}", "error"); return
            chemin_pj, temp_dir = result
            if not chemin_pj: self.app_controller.show_toast(f"Fichier non trouvé : {rel_path}", "error"); return
            succes, message = self.remboursement_controller.telecharger_copie_piece_jointe(chemin_pj, temp_dir)
            if succes:
                self.app_controller.show_toast(message, 'success')
            elif "annulé" not in message.lower():
                self.app_controller.show_toast(message, 'error')

        self.view.run_task(task, on_complete, "Téléchargement...")

    def action_voir_historique_docs(self, demande_data):
        DocumentHistoryViewer(self.view, demande_data=demande_data,
                              remboursement_controller=self.remboursement_controller,
                              app_controller=self.app_controller)

    def action_admin_purge_archives(self):
        age_str = simpledialog.askstring("Purger les Archives",
                                         "Entrez l'âge minimum (en années) des archives à supprimer.",
                                         parent=self.view)
        if not age_str: return
        try:
            age = int(age_str)
            if messagebox.askyesno("Confirmation",
                                   f"Purger les archives de plus de {age} an(s) ?\nAction IRRÉVERSIBLE.",
                                   icon='warning', parent=self.view):
                def task():
                    return self.remboursement_controller.admin_purge_archives(age)

                def on_complete(result, error):
                    if error: self.app_controller.show_toast(f"Erreur: {error}", "error"); return
                    nb, errs = result
                    msg = f"{nb} demande(s) purgées." + (f"\nErreurs: {', '.join(errs)}" if errs else "")
                    self.app_controller.show_toast(msg, 'info')
                    self.afficher_liste_demandes(force_refresh=True, show_loader=True)

                self.view.run_task(task, on_complete, "Purge des archives...")
        except (ValueError, TypeError):
            self.app_controller.show_toast("Veuillez entrer un nombre valide.", "error")

    def action_admin_optimiser_bdd(self):
        msg = ("Optimiser la base de données (VACUUM) ?\n\nCette opération est bloquante et peut prendre du temps. "
               "Assurez-vous qu'aucun autre utilisateur n'est actif.")
        if messagebox.askyesno("Confirmation", msg, icon='warning', parent=self.view):
            def task():
                return self.view.maintenance_controller.optimiser_base_de_donnees_data()

            def on_complete(result, error):
                if error: self.app_controller.show_toast(f"Erreur: {error}", "error"); return
                succes, message = result
                self.app_controller.show_toast(message, 'success' if succes else 'error')

            self.view.run_task(task, on_complete, "Optimisation de la BDD...")