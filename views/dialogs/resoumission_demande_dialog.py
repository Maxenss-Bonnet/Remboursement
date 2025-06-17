import os
import customtkinter as ctk
import threading
from views.mixins.task_runner_mixin import TaskRunnerMixin


class ResoumissionDemandeDialog(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, remboursement_controller, id_demande, app_controller):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.master = master
        self.remboursement_controller = remboursement_controller
        self.id_demande = id_demande
        self.app_controller = app_controller
        self.submitted = False

        self.title(f"Corriger Demande {id_demande[:8]}")
        self.geometry("600x550")
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.chemin_facture_reseau_temp = None
        self.chemin_rib_reseau_temp = None
        self.keep_facture_var = ctk.BooleanVar(value=True)
        self.keep_rib_var = ctk.BooleanVar(value=True)

        self.chemin_facture_var = ctk.StringVar(value="Ancienne facture conservée")
        self.chemin_rib_var = ctk.StringVar(value="Ancien RIB conservé")

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(expand=True, fill="both", padx=20, pady=10)

        self._load_data_and_build_ui()

    def _load_data_and_build_ui(self):
        def task():
            return self.remboursement_controller.get_demande(self.id_demande)

        def on_complete(demande, error):
            if error or not demande:
                self.app_controller.show_toast("Impossible de charger les données de la demande.", "error")
                self.destroy()
                return
            self._build_ui(demande)

        self.run_task(task, on_complete, "Chargement de la demande...")

    def _build_ui(self, demande):
        ctk.CTkLabel(self.main_frame, text="Veuillez fournir les documents mis à jour et un commentaire.").pack(
            pady=(0, 15))

        facture_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        facture_frame.pack(fill="x", pady=(5, 0))
        facture_frame.columnconfigure(1, weight=1)

        self.btn_sel_facture = ctk.CTkButton(facture_frame, text="Choisir Nouvelle Facture (Optionnel)",
                                             command=self._sel_new_facture, state="disabled")
        self.btn_sel_facture.grid(row=0, column=0, padx=(0, 10))
        self.lbl_facture_sel = ctk.CTkLabel(facture_frame, textvariable=self.chemin_facture_var, text_color="gray",
                                            anchor="w")
        self.lbl_facture_sel.grid(row=0, column=1, sticky="ew")
        factures_existantes = demande.chemins_factures_stockees
        self.cb_keep_facture = ctk.CTkCheckBox(self.main_frame, variable=self.keep_facture_var,
                                               command=self._toggle_facture_ui)
        if factures_existantes:
            self.cb_keep_facture.configure(text=f"Conserver la facture : {os.path.basename(factures_existantes[-1])}")
        else:
            self.cb_keep_facture.configure(text="Pas de facture précédente à conserver", state="disabled")
            self.keep_facture_var.set(False)
            self._toggle_facture_ui()
        self.cb_keep_facture.pack(anchor="w", padx=20, pady=(5, 15))

        rib_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        rib_frame.pack(fill="x", pady=(5, 0))
        rib_frame.columnconfigure(1, weight=1)
        self.btn_sel_rib = ctk.CTkButton(rib_frame, text="Choisir Nouveau RIB", command=self._sel_new_rib,
                                         state="disabled")
        self.btn_sel_rib.grid(row=0, column=0, padx=(0, 10))
        self.lbl_rib_sel = ctk.CTkLabel(rib_frame, textvariable=self.chemin_rib_var, text_color="gray", anchor="w")
        self.lbl_rib_sel.grid(row=0, column=1, sticky="ew")
        ribs_existants = demande.chemins_rib_stockes
        self.cb_keep_rib = ctk.CTkCheckBox(self.main_frame, variable=self.keep_rib_var, command=self._toggle_rib_ui)
        if ribs_existants:
            self.cb_keep_rib.configure(text=f"Conserver le RIB : {os.path.basename(ribs_existants[-1])}")
        else:
            self.cb_keep_rib.configure(text="Pas de RIB précédent à conserver", state="disabled")
            self.keep_rib_var.set(False)
            self._toggle_rib_ui()
        self.cb_keep_rib.pack(anchor="w", padx=20, pady=(5, 15))

        ctk.CTkLabel(self.main_frame, text="Commentaire de correction (Obligatoire):").pack(pady=(15, 0))
        self.commentaire_box = ctk.CTkTextbox(self.main_frame, height=80)
        self.commentaire_box.pack(pady=5, padx=20, fill="x", expand=True)
        self.commentaire_box.focus()

        ctk.CTkButton(self, text="Resoumettre la Demande", command=self._submit_correction).pack(pady=20)

    def _toggle_facture_ui(self):
        is_kept = self.keep_facture_var.get()
        self.btn_sel_facture.configure(state="disabled" if is_kept else "normal")
        self.lbl_facture_sel.configure(text_color="gray" if is_kept else ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        if self.chemin_facture_reseau_temp:
            self.remboursement_controller.supprimer_fichier_temporaire_reseau(self.chemin_facture_reseau_temp)
            self.chemin_facture_reseau_temp = None
        if is_kept:
            self.chemin_facture_var.set("Ancienne facture conservée")
        else:
            self.chemin_facture_var.set("Aucun fichier sélectionné")

    def _toggle_rib_ui(self):
        is_kept = self.keep_rib_var.get()
        self.btn_sel_rib.configure(state="disabled" if is_kept else "normal")
        self.lbl_rib_sel.configure(text_color="gray" if is_kept else ctk.ThemeManager.theme["CTkLabel"]["text_color"])
        if self.chemin_rib_reseau_temp:
            self.remboursement_controller.supprimer_fichier_temporaire_reseau(self.chemin_rib_reseau_temp)
            self.chemin_rib_reseau_temp = None
        if is_kept:
            self.chemin_rib_var.set("Ancien RIB conservé")
        else:
            self.chemin_rib_var.set("Aucun fichier sélectionné")

    def _sel_new_facture(self):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image("Nouvelle Facture")
        if not chemin_local: return

        if self.chemin_facture_reseau_temp:
            self.run_task(lambda p=self.chemin_facture_reseau_temp: self.remboursement_controller.supprimer_fichier_temporaire_reseau(p), None, show_overlay=False)
        self.chemin_facture_reseau_temp = None

        self.chemin_facture_var.set(f"Copie en cours...")
        def task(): return self.remboursement_controller.preparer_piece_jointe_reseau(chemin_local)
        def on_complete(result, error):
            if error:
                self.chemin_facture_var.set("Échec copie!")
            else:
                self.chemin_facture_reseau_temp = result
                self.chemin_facture_var.set(os.path.basename(result))
        self.run_task(task, on_complete, show_overlay=False)

    def _sel_new_rib(self):
        chemin_local = self.remboursement_controller.selectionner_fichier_document_ou_image("Nouveau RIB")
        if not chemin_local: return

        if self.chemin_rib_reseau_temp:
            self.run_task(lambda p=self.chemin_rib_reseau_temp: self.remboursement_controller.supprimer_fichier_temporaire_reseau(p), None, show_overlay=False)
        self.chemin_rib_reseau_temp = None

        self.chemin_rib_var.set(f"Copie en cours...")
        def task(): return self.remboursement_controller.preparer_piece_jointe_reseau(chemin_local)
        def on_complete(result, error):
            if error:
                self.chemin_rib_var.set("Échec copie!")
            else:
                self.chemin_rib_reseau_temp = result
                self.chemin_rib_var.set(os.path.basename(result))
        self.run_task(task, on_complete, show_overlay=False)

    def _submit_correction(self):
        commentaire = self.commentaire_box.get("1.0", "end-1c").strip()
        if not self.keep_rib_var.get() and not self.chemin_rib_reseau_temp:
            self.app_controller.show_toast("Un nouveau RIB est obligatoire si vous ne conservez pas l'ancien.", "error")
            return
        if not commentaire:
            self.app_controller.show_toast("Un commentaire expliquant la correction est obligatoire.", "error")
            return

        def task():
            facture_path = self.chemin_facture_reseau_temp
            rib_path = self.chemin_rib_reseau_temp
            self.chemin_facture_reseau_temp, self.chemin_rib_reseau_temp = None, None

            return self.remboursement_controller.pneri_resoumettre_demande_corrigee(
                self.id_demande, commentaire,
                None if self.keep_facture_var.get() else facture_path,
                None if self.keep_rib_var.get() else rib_path
            )

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur : {error}", 'error')
                return
            success, message = result
            if success:
                self.app_controller.show_toast(message, 'success')
                self.submitted = True
                self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')
        self.run_task(task, on_complete, "Resoumission de la demande...")

    def _on_close(self):
        paths_to_delete = [self.chemin_facture_reseau_temp, self.chemin_rib_reseau_temp]
        for path in paths_to_delete:
            if path:
                threading.Thread(target=self.remboursement_controller.supprimer_fichier_temporaire_reseau, args=(path,), daemon=True).start()
        self.destroy()