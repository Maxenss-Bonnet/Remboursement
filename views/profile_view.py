import os
import shutil
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageDraw, ImageFont

from config.settings import PROFILE_PICTURES_DIR
from utils.image_utils import create_circular_image
from utils.password_utils import check_password_strength
from views.mixins.task_runner_mixin import TaskRunnerMixin


class ProfileView(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, auth_controller, app_controller, user_data: dict, on_save_callback):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.transient(master)
        self.grab_set()

        self.master = master
        self.auth_controller = auth_controller
        self.app_controller = app_controller
        self.user_data = user_data
        self.on_save_callback = on_save_callback
        self.current_user = user_data.get("login")

        self.title(f"Profil de {self.current_user}")
        self.geometry("500x750")
        self.resizable(False, False)

        self.new_profile_pic_source_path = None
        self.profile_pic_rel_path = user_data.get("profile_picture_path")

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        self.pfp_size = 80
        self.pfp_label = ctk.CTkLabel(main_frame, text="", width=self.pfp_size, height=self.pfp_size)
        self.pfp_label.pack(pady=(10, 5))
        self.load_profile_picture()

        pfp_buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        pfp_buttons_frame.pack(pady=5)
        ctk.CTkButton(pfp_buttons_frame, text="Changer de photo", command=self._select_profile_picture).pack(
            side="left", padx=5)
        ctk.CTkButton(pfp_buttons_frame, text="Supprimer Photo", command=self._remove_profile_picture,
                      fg_color="#D32F2F", hover_color="#B71C1C").pack(side="left", padx=5)

        ctk.CTkLabel(main_frame, text="Adresse e-mail:", anchor="w").pack(fill="x", padx=20, pady=(15, 2))
        self.email_entry = ctk.CTkEntry(main_frame)
        self.email_entry.insert(0, user_data.get("email", ""))
        self.email_entry.pack(fill="x", padx=20)

        ctk.CTkLabel(main_frame, text="Ancien mot de passe:", anchor="w").pack(fill="x", padx=20, pady=(15, 2))
        self.old_password_entry = ctk.CTkEntry(main_frame, show="*")
        self.old_password_entry.pack(fill="x", padx=20)

        ctk.CTkLabel(main_frame, text="Nouveau mot de passe (laisser vide pour ne pas changer):",
                     anchor="w").pack(
            fill="x", padx=20, pady=(5, 2))
        self.new_password_entry = ctk.CTkEntry(main_frame, show="*")
        self.new_password_entry.pack(fill="x", padx=20)
        self.new_password_entry.bind("<KeyRelease>", self._update_password_strength)

        self.strength_progress = ctk.CTkProgressBar(main_frame, progress_color="grey")
        self.strength_progress.set(0)
        self.strength_progress.pack(fill="x", padx=20, pady=(5, 2))
        self.strength_label = ctk.CTkLabel(main_frame, text="", font=ctk.CTkFont(size=12))
        self.strength_label.pack(fill="x", padx=20)

        self.show_password_var = ctk.BooleanVar()
        ctk.CTkCheckBox(main_frame, text="Afficher les mots de passe", variable=self.show_password_var,
                        command=self._toggle_password_visibility).pack(padx=20, pady=10)

        ctk.CTkLabel(main_frame, text="Thème de couleur:", anchor="w").pack(fill="x", padx=20, pady=(15, 2))
        themes = ["blue", "dark-blue", "green"]
        self.theme_menu = ctk.CTkOptionMenu(main_frame, values=themes)
        self.theme_menu.set(user_data.get("theme_color", "blue"))
        self.theme_menu.pack(fill="x", padx=20)

        ctk.CTkLabel(main_frame, text="Filtre par défaut au démarrage:", anchor="w").pack(fill="x", padx=20,
                                                                                          pady=(15, 2))
        filters = ["Toutes les demandes", "En attente de mon action", "En cours", "Terminées et annulées"]
        self.filter_menu = ctk.CTkOptionMenu(main_frame, values=filters)
        self.filter_menu.set(user_data.get("default_filter", "Toutes les demandes"))
        self.filter_menu.pack(fill="x", padx=20)

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=30)
        ctk.CTkButton(button_frame, text="Enregistrer", command=self._save_profile, width=150).pack(side="left",
                                                                                                    padx=10)
        ctk.CTkButton(button_frame, text="Annuler", command=self.destroy, fg_color="gray").pack(side="left",
                                                                                                padx=10)

    def _toggle_password_visibility(self):
        show_char = "" if self.show_password_var.get() else "*"
        self.old_password_entry.configure(show=show_char)
        self.new_password_entry.configure(show=show_char)

    def _update_password_strength(self, event=None):
        password = self.new_password_entry.get()
        if not password:
            self.strength_label.configure(text="")
            self.strength_progress.set(0)
            return

        score, feedback = check_password_strength(password)
        progress = score / 5.0

        colors = {
            "Très faible": "#D32F2F", "Faible": "#F44336", "Moyen": "#FFC107",
            "Fort": "#4CAF50", "Très fort": "#4CAF50"
        }
        color = colors.get(feedback, "grey")

        self.strength_progress.set(progress)
        self.strength_progress.configure(progress_color=color)
        self.strength_label.configure(text=feedback, text_color=color)

    def load_profile_picture(self):
        pfp_image = None
        if self.profile_pic_rel_path:
            full_path = os.path.join(PROFILE_PICTURES_DIR, self.profile_pic_rel_path)
            if os.path.exists(full_path):
                pfp_image = create_circular_image(full_path, self.pfp_size)

        if pfp_image:
            self.pfp_label.configure(image=pfp_image)
        else:
            placeholder = Image.new('RGBA', (self.pfp_size, self.pfp_size), (80, 80, 80, 255))
            draw = ImageDraw.Draw(placeholder)
            try:
                font = ImageFont.truetype("arial", 40)
            except IOError:
                font = ImageFont.load_default()
            initial = self.current_user[0].upper() if self.current_user else "?"
            draw.text((self.pfp_size / 2, self.pfp_size / 2), initial, font=font, anchor="mm")
            ctk_placeholder = ctk.CTkImage(light_image=placeholder, dark_image=placeholder,
                                           size=(self.pfp_size, self.pfp_size))
            self.pfp_label.configure(image=ctk_placeholder)
            self.pfp_label.image = ctk_placeholder

    def _select_profile_picture(self):
        filepath = filedialog.askopenfilename(
            title="Choisir une photo de profil",
            filetypes=(("Images", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Tous les fichiers", "*.*"))
        )
        if filepath:
            self.new_profile_pic_source_path = filepath
            pfp_image = create_circular_image(filepath, self.pfp_size)
            if pfp_image:
                self.pfp_label.configure(image=pfp_image)

    def _remove_profile_picture(self):
        if messagebox.askyesno("Confirmation", "Êtes-vous sûr de vouloir supprimer votre photo de profil ?",
                               parent=self):
            def task():
                return self.auth_controller.remove_user_profile_picture(self.current_user)

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur: {error}", 'error')
                    return
                success, message = result
                if success:
                    self.app_controller.show_toast("Photo de profil supprimée.", 'success')
                    self.profile_pic_rel_path = None
                    self.load_profile_picture()
                    if self.on_save_callback:
                        self.on_save_callback()
                else:
                    self.app_controller.show_toast(message, 'error')

            self.run_task(task, on_complete, "Suppression de la photo...")

    def _handle_picture_save(self) -> str | None:
        if not self.new_profile_pic_source_path:
            return self.profile_pic_rel_path

        _, extension = os.path.splitext(self.new_profile_pic_source_path)
        new_filename = f"pfp_{self.current_user.lower().replace('.', '_')}{extension}"
        destination_path = os.path.join(PROFILE_PICTURES_DIR, new_filename)

        try:
            shutil.copy2(self.new_profile_pic_source_path, destination_path)
            return new_filename
        except Exception as e:
            self.app_controller.show_toast(f"Impossible d'enregistrer la photo de profil : {e}", "error")
            return self.profile_pic_rel_path

    def _save_profile(self):
        new_email = self.email_entry.get().strip()
        old_password = self.old_password_entry.get()
        new_password = self.new_password_entry.get()

        if new_password and not old_password:
            self.app_controller.show_toast("Veuillez entrer votre ancien mot de passe pour le modifier.", "error")
            return

        def task():
            new_pfp_rel_path = self._handle_picture_save()
            updated_prefs = {
                "theme_color": self.theme_menu.get(),
                "default_filter": self.filter_menu.get(),
                "profile_picture_path": new_pfp_rel_path
            }
            return self.auth_controller.update_user_profile(
                login=self.current_user,
                new_email=new_email,
                old_password=old_password if old_password else None,
                new_password=new_password if new_password else None,
                preferences=updated_prefs
            )

        def on_complete(result, error):
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", 'error')
                return
            success, message = result
            if success:
                if self.on_save_callback:
                    self.on_save_callback()
                self.app_controller.show_toast("Profil enregistré avec succès.", 'success')
                self.destroy()
            else:
                self.app_controller.show_toast(message, 'error')

        self.run_task(task, on_complete, "Enregistrement du profil...")