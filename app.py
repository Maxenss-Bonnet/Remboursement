import customtkinter as ctk
import os
import sys
import tkinter
import threading
import queue
import logging
import time
from tkinter import messagebox
from tkinterdnd2 import TkinterDnD

from controllers.app_controller import AppController
from config.settings import SHARED_DATA_BASE_PATH, get_application_base_path
from utils.database_manager import stop_db_writer_thread, cleanup_stale_lock_on_startup
from utils.logging_config import setup_logging
from utils.network_monitor import is_path_accessible
from views.path_config_dialog import PathConfigDialog


class MainApplication(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.configure(background="gray14")
        self.title("Application de Gestion")
        self.shutdown_window = None
        self.force_close_button = None
        self.force_close_label = None
        self._after_job_id = None

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
            if self.shutdown_window is None or not self.shutdown_window.winfo_exists():
                self.show_shutdown_window()
            self._check_busy_status(is_restart)
        else:
            self._perform_shutdown(is_restart)

    def show_shutdown_window(self):
        self.shutdown_window = ctk.CTkToplevel(self)
        self.shutdown_window.title("Fermeture")
        self.shutdown_window.geometry("450x220")
        self.shutdown_window.transient(self)
        self.shutdown_window.grab_set()
        self.shutdown_window.protocol("WM_DELETE_WINDOW", lambda: None)
        self.shutdown_window.resizable(False, False)

        main_label = ctk.CTkLabel(self.shutdown_window,
                                  text="Finalisation des opérations en cours...\nVeuillez patienter.",
                                  font=ctk.CTkFont(size=14))
        main_label.pack(pady=(20, 10), padx=20)

        self.force_close_label = ctk.CTkLabel(self.shutdown_window,
                                              text="La fermeture prend un temps anormalement long, un blocage est possible.\nSi cela persiste, vous pouvez forcer la fermeture.",
                                              font=ctk.CTkFont(size=12, slant="italic"),
                                              text_color="gray60")

        self.force_close_button = ctk.CTkButton(self.shutdown_window, text="Forcer la Fermeture",
                                                fg_color="red", hover_color="#C00000",
                                                command=self._force_quit)

        self.after(30000, self._show_force_close_widgets)
        self.shutdown_window.update()

    def _show_force_close_widgets(self):
        if self.shutdown_window and self.shutdown_window.winfo_exists():
            if self.force_close_label:
                self.force_close_label.pack(pady=(10, 5), padx=20)
            if self.force_close_button:
                self.force_close_button.pack(pady=10, padx=20)

    def _check_busy_status(self, is_restart: bool):
        if self.app_controller and self.app_controller.is_application_busy():
            self._after_job_id = self.after(500, lambda: self._check_busy_status(is_restart))
        else:
            self._perform_shutdown(is_restart)

    def _perform_shutdown(self, is_restart: bool):
        if self._after_job_id:
            self.after_cancel(self._after_job_id)
            self._after_job_id = None

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
            sys.exit(0)

    def _force_quit(self):
        logging.warning("L'application a été forcée de quitter par l'utilisateur.")
        sys.exit(1)

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
            max_retries = 15
            retry_delay = 1

            for i in range(max_retries):
                if is_path_accessible(SHARED_DATA_BASE_PATH):
                    result_queue.put(True)
                    return

                self.loading_label.configure(text=f"Réseau indisponible. Réessai ({i + 1}/{max_retries})...")

                if i < max_retries - 1:
                    time.sleep(retry_delay)

            result_queue.put(False)

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
        self.geometry("600x300")
        self.center_window()

        error_frame = ctk.CTkFrame(self)
        error_frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(error_frame, text="Erreur de Connexion Réseau", font=ctk.CTkFont(size=20, weight="bold")).pack(
            pady=(20, 10), padx=30)

        error_message = (
            "Impossible d'accéder au dossier des données partagées.\n\n"
            "Veuillez vérifier votre connexion Wi-Fi ou votre VPN (si hors-site).\n"
            "Si le problème persiste alors que vous êtes bien connecté au VPN ou au Wi-Fi de NATECIA,\n"
            "le chemin d'accès au dossier a peut-être changé."
        )
        ctk.CTkLabel(error_frame, text=error_message, font=ctk.CTkFont(size=14), justify="center").pack(pady=10,
                                                                                                        padx=30)
        button_frame = ctk.CTkFrame(error_frame, fg_color="transparent")
        button_frame.pack(pady=(15, 20), padx=30)

        ctk.CTkButton(button_frame, text="Configurer le chemin", command=self._open_path_config_dialog,
                      width=180, height=40).pack(side="left", padx=10)

        ctk.CTkButton(button_frame, text="Réessayer", command=self._restart_app, width=180, height=40).pack(
            side="left", padx=10)

    def _open_path_config_dialog(self):
        self.withdraw()
        dialog = PathConfigDialog(master=self, restart_callback=self._restart_app)
        self.wait_window(dialog)
        self.deiconify()

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

    try:
        cleanup_stale_lock_on_startup()
    except Exception as e:
        logging.critical(f"Erreur critique lors du nettoyage du verrou au démarrage : {e}", exc_info=True)

    app = MainApplication()
    app.mainloop()