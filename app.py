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
        self.withdraw()

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
        self.loading_window, self.loading_label = self._create_loading_splash_screen()
        self.after(50, self.run_startup_check)

    def _create_loading_splash_screen(self) -> tuple[ctk.CTkToplevel, ctk.CTkLabel]:
        """Crée une petite fenêtre de chargement centrée et retourne la fenêtre et son label."""
        loading_window = ctk.CTkToplevel(self)
        loading_window.overrideredirect(True)
        loading_window.transient(self)

        width, height = 300, 150

        loading_window.update_idletasks()
        screen_width = loading_window.winfo_screenwidth()
        screen_height = loading_window.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        loading_window.geometry(f"{width}x{height}+{x}+{y}")

        frame = ctk.CTkFrame(loading_window, corner_radius=10)
        frame.pack(expand=True, fill="both", padx=5, pady=5)

        loading_label = ctk.CTkLabel(frame, text="Vérification de la connexion...", font=ctk.CTkFont(size=14))
        loading_label.pack(pady=(25, 10))

        progress_bar = ctk.CTkProgressBar(frame, mode='indeterminate')
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar.start()

        loading_window.lift()
        return loading_window, loading_label

    def run_startup_check(self):
        """Lance la vérification du chemin réseau dans un thread séparé."""
        result_queue = queue.Queue()

        def checker_task():
            """La tâche qui s'exécute en arrière-plan."""
            is_writable = is_path_writable(SHARED_DATA_BASE_PATH) if IS_DEPLOYMENT_MODE else True
            result_queue.put(is_writable)

        threading.Thread(target=checker_task, daemon=True).start()
        self._process_network_check_result(result_queue)

    def _process_network_check_result(self, result_queue: queue.Queue):
        """Vérifie le résultat de la tâche réseau et lance l'initialisation de l'app."""
        try:
            is_writable = result_queue.get_nowait()

            if is_writable:
                self.loading_label.configure(text="Démarrage de l'application...")
                self.loading_window.update_idletasks()

                self.app_controller = AppController(self)

                init_thread = threading.Thread(target=self.app_controller.run_initialization, daemon=True)
                init_thread.start()

                self.after(100, self._check_app_init_completion, init_thread)
            else:
                self.loading_window.destroy()
                self.deiconify()
                self._show_connection_error_window()
        except queue.Empty:
            self.after(100, self._process_network_check_result, result_queue)

    def _check_app_init_completion(self, init_thread: threading.Thread):
        """Sondage pour vérifier si le thread d'initialisation de l'application est terminé."""
        if init_thread.is_alive():
            self.after(100, self._check_app_init_completion, init_thread)
        else:
            self.app_controller.show_initial_view()
            self.loading_window.destroy()
            self.deiconify()
            self.after(100, self.attempt_maximize)

    def _show_connection_error_window(self):
        """Affiche la fenêtre d'erreur de connexion."""
        for widget in self.winfo_children():
            widget.destroy()

        self.title("Erreur de Connexion")
        self.geometry("600x250")
        self.center_window()

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

    def center_window(self):
        """Centre la fenêtre principale sur l'écran."""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

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