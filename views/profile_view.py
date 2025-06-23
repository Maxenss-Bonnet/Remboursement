import os
import shutil
import customtkinter as ctk
import queue
import threading
from tkinter import messagebox, filedialog
from PIL import Image, ImageDraw, ImageFont, ImageOps

from config.settings import PROFILE_PICTURES_DIR
from utils.image_utils import get_or_create_circular_pfp
from utils.password_utils import check_password_strength
from utils.file_utils import copy_with_progress
from views.mixins.task_runner_mixin import TaskRunnerMixin
from views.mixins.animation_mixin import AnimationMixin

PFP_MAX_SIZE = (512, 512)


class ProfileView(ctk.CTkToplevel, TaskRunnerMixin, AnimationMixin):
    def __init__(self, master, auth_controller, app_controller, user_data: dict, on_save_callback):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)
        AnimationMixin.__init__(self, master)

        self.transient(master)
        self.grab_set()

        self.master = master
        self.auth_controller = auth_controller
        self.app_controller = app_controller
        self.user_data = user_data
        self.on_save_callback = on_save_callback
        self.current_user = user_data.get("login")

        self.title(f"Profil de {self.current_user}")
        self.geometry("500x800")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

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

        self.pfp_progress_bar = ctk.CTkProgressBar(main_frame)
        self.pfp_progress_bar.pack(fill='x', padx=20, pady=5)
        self.pfp_progress_bar.set(0)
        self.pfp_progress_bar.pack_forget()

        ctk.CTkLabel(main_frame, text="Adresse e-mail:", anchor="w").pack(fill="x", padx=20, pady=(10, 2))
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
        self.save_button = ctk.CTkButton(button_frame, text="Enregistrer", command=self._save_profile, width=150)
        self.save_button.pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Annuler", command=self.close_animated, fg_color="gray").pack(side="left",
                                                                                                       padx=10)
        self.fade_in()

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
        full_path = None
        if self.profile_pic_rel_path:
            full_path = os.path.join(PROFILE_PICTURES_DIR, self.profile_pic_rel_path)

        pfp_image = get_or_create_circular_pfp(
            login=self.current_user,
            source_path=full_path,
            size=self.pfp_size,
            cache_manager=self.app_controller.cache_manager
        )

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
            try:
                with Image.open(filepath) as img_source:
                    img = ImageOps.fit(img_source, (self.pfp_size, self.pfp_size), Image.Resampling.LANCZOS)
                    mask = Image.new('L', (self.pfp_size, self.pfp_size), 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0, self.pfp_size, self.pfp_size), fill=255)
                    img.putalpha(mask)
                    pfp_image = ctk.CTkImage(light_image=img, dark_image=img, size=(self.pfp_size, self.pfp_size))
                    self.pfp_label.configure(image=pfp_image)
            except Exception as e:
                self.app_controller.show_toast(f"Impossible de prévisualiser l'image: {e}", "error")

    def _remove_profile_picture(self):
        if messagebox.askyesno("Confirmation", "Êtes-vous sûr de vouloir supprimer votre photo de profil ?",
                               parent=self):
            def task():
                return self.auth_controller.remove_user_profile_picture(
                    login=self.current_user,
                    cache_manager=self.app_controller.cache_manager
                )

            def on_complete(result, error):
                if error:
                    self.app_controller.show_toast(f"Erreur: {error}", 'error')
                    return
                success, message = result
                if success:
                    self.app_controller.show_toast("Photo de profil supprimée.", 'success')
                    self.profile_pic_rel_path = None
                    self.new_profile_pic_source_path = None
                    self.load_profile_picture()
                    if self.on_save_callback:
                        self.on_save_callback()
                else:
                    self.app_controller.show_toast(message, 'error')

            self.run_task(task, on_complete, "Suppression de la photo...")

    def _handle_picture_save(self, progress_callback) -> str | None:
        if not self.new_profile_pic_source_path:
            return self.profile_pic_rel_path

        _, extension = os.path.splitext(self.new_profile_pic_source_path)
        new_filename = f"pfp_{self.current_user.lower().replace('.', '_')}{extension}"
        temp_dest_path = os.path.join(PROFILE_PICTURES_DIR, f"temp_{new_filename}")

        try:
            with Image.open(self.new_profile_pic_source_path) as img:
                img.thumbnail(PFP_MAX_SIZE, Image.Resampling.LANCZOS)
                rgb_img = img.convert('RGB')
                rgb_img.save(temp_dest_path, quality=90, optimize=True)

            final_dest_path = os.path.join(PROFILE_PICTURES_DIR, new_filename)
            copy_with_progress(temp_dest_path, final_dest_path, progress_callback)
            os.remove(temp_dest_path)
            return new_filename
        except Exception as e:
            if os.path.exists(temp_dest_path):
                os.remove(temp_dest_path)
            self.app_controller.show_toast(f"Impossible d'enregistrer la photo de profil : {e}", "error")
            return self.profile_pic_rel_path

    def _save_profile(self):
        self.save_button.configure(state="disabled")

        if self.new_profile_pic_source_path:
            self.pfp_progress_bar.pack()
            progress_queue = queue.Queue()

            def pfp_copy_task():
                try:
                    callback = lambda p: progress_queue.put(p)
                    new_rel_path = self._handle_picture_save(callback)
                    progress_queue.put(("done", new_rel_path))
                except Exception as e:
                    progress_queue.put(("error", str(e)))

            threading.Thread(target=pfp_copy_task, daemon=True).start()
            self._process_pfp_save(progress_queue)
        else:
            self._save_other_data(self.profile_pic_rel_path)

    def _process_pfp_save(self, q):
        try:
            message = q.get_nowait()
            if isinstance(message, float):
                self.pfp_progress_bar.set(message)
            elif isinstance(message, tuple):
                status, value = message
                if status == "done":
                    self.pfp_progress_bar.pack_forget()
                    self._save_other_data(value)  # value is the new_rel_path
                else:  # error
                    self.app_controller.show_toast(f"Erreur photo: {value}", "error")
                    self.save_button.configure(state="normal")

            if self.winfo_exists():
                self.after(100, lambda: self._process_pfp_save(q))
        except queue.Empty:
            if self.winfo_exists():
                self.after(100, lambda: self._process_pfp_save(q))

    def _save_other_data(self, pfp_rel_path: str | None):
        new_email = self.email_entry.get().strip()
        old_password = self.old_password_entry.get()
        new_password = self.new_password_entry.get()

        if new_password and not old_password:
            self.app_controller.show_toast("Veuillez entrer votre ancien mot de passe pour le modifier.", "error")
            self.save_button.configure(state="normal")
            return

        updated_prefs = {
            "theme_color": self.theme_menu.get(),
            "default_filter": self.filter_menu.get(),
            "profile_picture_path": pfp_rel_path
        }

        def task():
            return self.auth_controller.update_user_profile(
                login=self.current_user,
                new_email=new_email,
                old_password=old_password if old_password else None,
                new_password=new_password if new_password else None,
                preferences=updated_prefs,
                cache_manager=self.app_controller.cache_manager
            )

        def on_complete(result, error):
            self.save_button.configure(state="normal")
            if error:
                self.app_controller.show_toast(f"Erreur: {error}", 'error')
                return
            success, message = result
            if success:
                if self.on_save_callback:
                    self.on_save_callback()
                self.app_controller.show_toast("Profil enregistré avec succès.", 'success')
                self.close_animated()
            else:
                self.app_controller.show_toast(message, 'error')

        self.run_task(task, on_complete, "Enregistrement du profil...")