import customtkinter as ctk
import os
import sys
import tkinter
import threading
import queue
import logging
from tkinter import messagebox
from tkinterdnd2 import TkinterDnD
from controllers.app_controller import AppController
from config.settings import SHARED_DATA_BASE_PATH, IS_DEPLOYMENT_MODE, get_application_base_path
from utils.database_manager import stop_db_writer_thread
from utils.logging_config import setup_logging
from utils.network_monitor import is_path_accessible


class MainApplication(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.configure(background="gray14")
        self.title("Application de Gestion")
        self.shutdown_window = None

        try:
            icon_path = os.path.join(get_application_base_path(), "assets", "app_icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception as e:
            logging.warning(f"Erreur lors du chargement de l'icône : {e}")

        initial_width = 1024
        initial_height = 768
        self.geometry(f"{int(initial_width)}x{int(initial_height)}")
        self.minsize(800, 600)

        self.app_controller = None
        self.loading_window, self.loading_label = self._create_loading_splash_screen()
        self.after(50, self.run_startup_check)

        self.protocol("WM_DELETE_WINDOW", self.on_attempt_close)

    def on_attempt_close(self, is_restart: bool = False):
        if self.app_controller and self.app_controller.is_application_busy():
            if not self.shutdown_window or not self.shutdown_window.winfo_exists():
                self.shutdown_window = ctk.CTkToplevel(self)
                self.shutdown_window.title("Fermeture")
                self.shutdown_window.geometry("350x120")
                self.shutdown_window.transient(self)
                self.shutdown_window.grab_set()
                self.shutdown_window.protocol("WM_DELETE_WINDOW", lambda: None)
                label = ctk.CTkLabel(self.shutdown_window,
                                     text="Finalisation des opérations en cours...\nVeuillez patienter.",
                                     font=ctk.CTkFont(size=14))
                label.pack(expand=True, padx=20, pady=20)
                self.shutdown_window.update()

            self.after(500, lambda: self.on_attempt_close(is_restart))
            return

        if self.shutdown_window and self.shutdown_window.winfo_exists():
            self.shutdown_window.destroy()
            self.shutdown_window = None

        if self.app_controller:
            self.app_controller.shutdown()
        stop_db_writer_thread()

        if is_restart:
            self._restart_app()
        else:
            self.destroy()

    def _create_loading_splash_screen(self) -> tuple[ctk.CTkToplevel, ctk.CTkLabel]:
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
        result_queue = queue.Queue()

        def checker_task():
            is_accessible = is_path_accessible(SHARED_DATA_BASE_PATH)
            result_queue.put(is_accessible)

        threading.Thread(target=checker_task, daemon=True).start()
        self._process_network_check_result(result_queue)

    def _process_network_check_result(self, result_queue: queue.Queue):
        try:
            is_accessible = result_queue.get_nowait()
            if is_accessible:
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
        if init_thread.is_alive():
            self.after(100, self._check_app_init_completion, init_thread)
        else:
            self.app_controller.show_initial_view()
            self.loading_window.destroy()
            self.deiconify()
            self.after(100, self.attempt_maximize)

    def _show_connection_error_window(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.title("Erreur de Connexion")
        self.geometry("600x250")
        self.center_window()

        error_frame = ctk.CTkFrame(self)
        error_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(error_frame, text="Erreur de Connexion Réseau", font=ctk.CTkFont(size=20, weight="bold")).pack(
            pady=(20, 10), padx=30)
        error_message = ("Impossible d'accéder aux données partagées.\n\n"
                         "Veuillez vérifier votre connexion Wi-Fi ou votre connexion VPN si vous êtes hors site.")
        ctk.CTkLabel(error_frame, text=error_message, font=ctk.CTkFont(size=14), justify="center").pack(pady=10,
                                                                                                        padx=30)
        ctk.CTkButton(error_frame, text="Réessayer", command=self._restart_app, width=200, height=40).pack(
            pady=(15, 20), padx=30)

    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _restart_app(self):
        try:
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception as e:
            logging.critical("Le redémarrage automatique a échoué.", exc_info=True)
            messagebox.showerror(
                "Erreur de redémarrage",
                f"Le redémarrage automatique a échoué. Veuillez relancer l'application manuellement.\n\nErreur: {e}"
            )
            self.destroy()

    def attempt_maximize(self):
        try:
            self.state('zoomed')
        except ctk.TclError:
            try:
                self.attributes('-zoomed', True)
            except ctk.TclError:
                pass


if __name__ == "__main__":
    setup_logging()
    app = MainApplication()
    app.mainloop()