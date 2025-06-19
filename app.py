import customtkinter as ctk
import os
import sys
import tkinter
import threading
import queue
from tkinter import messagebox
from controllers.app_controller import AppController
from config.settings import SHARED_DATA_BASE_PATH, IS_DEPLOYMENT_MODE, get_application_base_path


def is_path_writable(path: str) -> bool:
    """
    Vérifie si un chemin non seulement existe, mais est aussi accessible en écriture.
    C'est un test beaucoup plus fiable pour un lecteur réseau.
    """
    try:
        if not os.path.isdir(path):
            return False

        test_file = os.path.join(path, f"write_test_{os.getpid()}.tmp")
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except (IOError, OSError, PermissionError):
        return False


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
        self.minsize(800, 600)

        self.app_controller = None
        self._setup_loading_screen()
        self.after(100, self.run_startup_check)

    def _setup_loading_screen(self):
        """Affiche un message de chargement centré."""
        self.loading_label = ctk.CTkLabel(self, text="Vérification de la connexion réseau...",
                                          font=ctk.CTkFont(size=18))
        self.loading_label.place(relx=0.5, rely=0.5, anchor="center")

    def run_startup_check(self):
        """Lance la vérification du chemin réseau dans un thread séparé."""
        result_queue = queue.Queue()

        def checker_task():
            """La tâche qui s'exécute en arrière-plan."""
            is_writable = is_path_writable(SHARED_DATA_BASE_PATH) if IS_DEPLOYMENT_MODE else True
            result_queue.put(is_writable)

        threading.Thread(target=checker_task, daemon=True).start()
        self._process_check_result(result_queue)

    def _process_check_result(self, result_queue: queue.Queue):
        """Vérifie le résultat de la tâche de manière non-bloquante."""
        try:
            is_writable = result_queue.get_nowait()
            self.loading_label.destroy()

            if is_writable:
                self.app_controller = AppController(self)
                self.after(100, self.attempt_maximize)
            else:
                self._show_connection_error_window()
        except queue.Empty:
            # Le thread n'a pas encore terminé, on vérifie à nouveau dans 100ms
            self.after(100, self._process_check_result, result_queue)

    def _show_connection_error_window(self):
        """Affiche la fenêtre d'erreur de connexion."""
        for widget in self.winfo_children():
            widget.destroy()

        self.title("Erreur de Connexion")
        self.geometry("600x250")

        error_frame = ctk.CTkFrame(self)
        error_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            error_frame,
            text="Erreur de Connexion Réseau",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(20, 10), padx=30)

        error_message = (
            "Impossible d'accéder aux données partagées.\n\n"
            "Veuillez vérifier votre connexion Wi-Fi ou votre connexion VPN si vous êtes hors site."
        )
        ctk.CTkLabel(
            error_frame,
            text=error_message,
            font=ctk.CTkFont(size=14),
            justify="center"
        ).pack(pady=10, padx=30)

        ctk.CTkButton(
            error_frame,
            text="Redémarrer l'application",
            command=self._restart_app,
            width=200,
            height=40
        ).pack(pady=(15, 20), padx=30)

    def _restart_app(self):
        """Redémarre l'application."""
        try:
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception as e:
            messagebox.showerror(
                "Erreur de redémarrage",
                f"Le redémarrage automatique a échoué. Veuillez relancer l'application manuellement.\n\nErreur: {e}"
            )
            self.destroy()

    def attempt_maximize(self):
        """Tente d'agrandir la fenêtre principale."""
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