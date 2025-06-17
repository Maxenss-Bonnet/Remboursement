import customtkinter as ctk
import os
import sys
import tkinter
from tkinter import messagebox
from controllers.app_controller import AppController
from config.settings import SHARED_DATA_BASE_PATH, IS_DEPLOYMENT_MODE, get_application_base_path


class MainApplication(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Application de Gestion")

        try:
            icon_path = os.path.join(get_application_base_path(), "assets", "app_icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Erreur lors du chargement de l'icône : {e}")

        initial_width = 1024
        initial_height = 768
        self.geometry(f"{int(initial_width)}x{int(initial_height)}")

        self.after(100, self.attempt_maximize)
        self.minsize(800, 600)

        self.app_controller = None
        self.after(50, self.initialize_app)

    def initialize_app(self):
        if IS_DEPLOYMENT_MODE and not os.path.exists(SHARED_DATA_BASE_PATH):
            messagebox.showerror(
                "Erreur de Connexion Réseau",
                f"Impossible d'accéder au dossier de données partagées :\n\n{SHARED_DATA_BASE_PATH}\n\n"
                "Veuillez vérifier votre connexion réseau (VPN, câble, etc.) et que le serveur est accessible.\n\n"
                "L'application va maintenant se fermer."
            )
            self.destroy()
            sys.exit(1)

        self.app_controller = AppController(self)

    def attempt_maximize(self):
        try:
            self.state('zoomed')
        except ctk.TclError:
            try:
                self.attributes('-zoomed', True)
            except ctk.TclError:
                try:
                    screen_width = self.winfo_screenwidth()
                    screen_height = self.winfo_screenheight()
                    self.geometry(f"{screen_width}x{screen_height}+0+0")
                except ctk.TclError:
                    pass


if __name__ == "__main__":
    app = MainApplication()
    app.mainloop()