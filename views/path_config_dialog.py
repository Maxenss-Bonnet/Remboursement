import os
import customtkinter as ctk
from tkinter import filedialog, messagebox
from config import settings
from views.mixins.animation_mixin import AnimationMixin


class PathConfigDialog(ctk.CTkToplevel, AnimationMixin):
    def __init__(self, master, restart_callback):
        super().__init__(master)
        AnimationMixin.__init__(self, master)

        self.transient(master)
        self.grab_set()
        self.title("Configuration du Chemin d'Accès")
        self.geometry("650x400")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self.master = master
        self.restart_callback = restart_callback

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        # --- Section d'aide ---
        help_frame = ctk.CTkFrame(main_frame, fg_color=("gray90", "gray25"))
        help_frame.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(help_frame, text="Comment configurer le bon dossier ?",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(10, 5), padx=10)

        help_text = (
            "Pour que l'application fonctionne, elle doit accéder au dossier partagé de l'entreprise.\n\n"
            "La méthode la plus simple est d'utiliser le bouton 'Parcourir...'.\n\n"
            "1. Cliquez sur le bouton **'Parcourir...'** ci-dessous.\n"
            "2. Une fenêtre s'ouvrira. Cherchez le lecteur réseau de l'entreprise (souvent\n"
            "   nommé 'Commun', 'Partage', ou une lettre comme 'Z:', 'P:', etc.).\n"
            "3. Dans ce lecteur, trouvez et sélectionnez le dossier nommé **REMBOURSEMENT**.\n"
            "4. Cliquez sur 'Sélectionner un dossier'."
        )
        ctk.CTkLabel(help_frame, text=help_text, justify="left", wraplength=580).pack(padx=10, pady=(0, 15))

        # --- Section de configuration ---
        config_frame = ctk.CTkFrame(main_frame)
        config_frame.pack(fill="x")
        config_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(config_frame, text="Chemin d'accès au dossier 'REMBOURSEMENT':").pack(anchor="w", padx=10,
                                                                                           pady=(10, 2))

        entry_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        entry_frame.pack(fill="x", expand=True, padx=10)
        entry_frame.grid_columnconfigure(0, weight=1)

        self.path_entry = ctk.CTkEntry(entry_frame, height=35)
        self.path_entry.grid(row=0, column=0, sticky="ew")
        self.path_entry.insert(0, settings.SHARED_DATA_BASE_PATH)
        self.path_entry.configure(state="readonly")  # L'utilisateur ne doit pas pouvoir taper manuellement

        browse_button = ctk.CTkButton(entry_frame, text="Parcourir...", command=self._browse_directory, width=100, height=35)
        browse_button.grid(row=0, column=1, padx=(10, 0))

        # --- Boutons d'action ---
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=(25, 0))

        ctk.CTkButton(button_frame, text="Valider et Redémarrer", command=self._on_validate, height=35).pack(
            side="left", padx=10)
        ctk.CTkButton(button_frame, text="Annuler", command=self.close_animated, fg_color="gray", height=35).pack(
            side="left", padx=10)

        self.after(100, self.path_entry.focus)
        self.fade_in()

    def _browse_directory(self):
        # Ouvre un dialogue pour sélectionner un dossier
        directory = filedialog.askdirectory(
            title="Veuillez sélectionner le dossier 'REMBOURSEMENT'",
            initialdir=os.path.dirname(self.path_entry.get())
        )
        if directory:
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, directory)
            self.path_entry.configure(state="readonly")

    def _on_validate(self):
        new_path = self.path_entry.get().strip()
        if not new_path or not os.path.isdir(new_path):
            messagebox.showerror("Chemin Invalide",
                                     "Le chemin spécifié n'existe pas ou n'est pas un dossier. Veuillez vérifier.",
                                     parent=self)
            return

        if os.path.basename(os.path.normpath(new_path)).upper() != "REMBOURSEMENT":
            if not messagebox.askyesno("Confirmation",
                                       f"Le dossier sélectionné ne s'appelle pas 'REMBOURSEMENT' (nom actuel : '{os.path.basename(new_path)}').\n\nÊtes-vous sûr de vouloir utiliser ce chemin ?",
                                       icon='warning', parent=self):
                return

        # Sauvegarde du nouveau chemin et redémarrage
        if settings.save_custom_path(new_path):
            self.restart_callback()
        else:
            messagebox.showerror("Erreur",
                                     "Impossible de sauvegarder le nouveau chemin de configuration.",
                                     parent=self)