import os
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
import fitz  # PyMuPDF
import sys
import subprocess
from utils import archive_utils


class DocumentViewerWindow(ctk.CTkToplevel):
    def __init__(self, master, file_path: str, title: str, temp_dir_to_clean: str | None = None):
        super().__init__(master)
        self.title(title)
        self.geometry("800x600")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(400, 300)

        self.master = master
        self.file_path = file_path
        self.pdf_doc = None
        self.temp_dir_to_clean = temp_dir_to_clean

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.content_container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.content_container.pack(expand=True, fill="both")

        self.load_and_display_document()

    def _open_with_system_default(self, close_viewer_after=True):
        """Tente d'ouvrir le fichier avec l'application par défaut du système."""
        try:
            if os.name == 'nt':
                os.startfile(self.file_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.file_path], check=True)
            else:
                subprocess.run(['xdg-open', self.file_path], check=True)
            if close_viewer_after:
                self.destroy()
        except Exception as e_gen:
            self.master.app_controller.show_toast(
                f"Impossible d'ouvrir le fichier avec l'application par défaut : {e_gen}", "error")

    def load_and_display_document(self):
        for widget in self.content_container.winfo_children():
            widget.destroy()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        max_window_width = int(screen_w * 0.9)
        max_window_height = int(screen_h * 0.85)

        file_processed_internally = False
        error_message_detail = ""

        try:
            ext = ""
            if self.file_path and '.' in self.file_path:
                ext = self.file_path.lower().split('.')[-1]
            else:
                raise ValueError("Chemin de fichier invalide ou sans extension.")

            if ext in ("png", "jpg", "jpeg", "gif", "bmp"):
                pil_image_original = Image.open(self.file_path)
                target_width, target_height = pil_image_original.size

                window_width = min(target_width + 60, max_window_width)
                window_height = min(target_height + 60, max_window_height)
                self.geometry(f"{int(window_width)}x{int(window_height)}")
                self.update_idletasks()

                ctk_img = ctk.CTkImage(light_image=pil_image_original,
                                       dark_image=pil_image_original,
                                       size=(target_width, target_height))
                image_label = ctk.CTkLabel(self.content_container, image=ctk_img, text="")
                image_label.pack(padx=0, pady=0)
                file_processed_internally = True

            elif ext == "pdf":
                self.pdf_doc = fitz.open(self.file_path)
                if self.pdf_doc.page_count == 0:
                    error_message_detail = "Le fichier PDF est vide."
                else:
                    max_page_render_width = 0
                    pdf_fixed_matrix_scale = 1.3

                    for page_num in range(self.pdf_doc.page_count):
                        page = self.pdf_doc.load_page(page_num)
                        mat = fitz.Matrix(pdf_fixed_matrix_scale, pdf_fixed_matrix_scale)
                        pix = page.get_pixmap(matrix=mat, alpha=False)

                        if pix.width == 0 or pix.height == 0: continue

                        current_pil_page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        current_page_width, current_page_height = current_pil_page_image.size

                        if page_num == 0:
                            max_page_render_width = current_page_width

                        ctk_img_page = ctk.CTkImage(light_image=current_pil_page_image,
                                                    dark_image=current_pil_page_image,
                                                    size=(current_page_width, current_page_height))
                        page_label = ctk.CTkLabel(self.content_container, image=ctk_img_page, text="")
                        page_label.pack(pady=(0 if page_num == 0 else 5, 0), padx=5)

                    window_width = min(max_page_render_width + 70, max_window_width)
                    first_page_height = self.pdf_doc.load_page(0).get_pixmap(
                        matrix=fitz.Matrix(pdf_fixed_matrix_scale, pdf_fixed_matrix_scale)).height
                    window_height = min(max(500, first_page_height + 60), max_window_height)
                    self.geometry(f"{int(window_width)}x{int(window_height)}")
                    file_processed_internally = True

            else:
                error_message_detail = f"Aperçu direct non supporté pour '{os.path.basename(self.file_path)}'."

            if not file_processed_internally:
                message_label = ctk.CTkLabel(self.content_container, text=error_message_detail, wraplength=380)
                message_label.pack(pady=20)
                self.geometry("500x150")

                if messagebox.askyesno("Ouvrir le fichier ?",
                                       f"{error_message_detail}\n\nVoulez-vous l'ouvrir avec l'application par défaut ?",
                                       parent=self):
                    self._open_with_system_default()

        except Exception as e:
            print(f"Erreur détaillée DocumentViewer: {e}")
            for widget in self.content_container.winfo_children(): widget.destroy()

            error_message_full = f"Une erreur est survenue lors de l'affichage du document:\n{e}"
            error_display_label = ctk.CTkLabel(self.content_container, text=error_message_full, wraplength=380)
            error_display_label.pack(pady=20)
            if not self.winfo_exists(): return
            self.geometry("400x200")

            if messagebox.askyesno("Ouvrir avec le système ?",
                                   f"{error_message_full}\n\nVoulez-vous essayer d'ouvrir le fichier avec l'application par défaut ?",
                                   parent=self):
                self._open_with_system_default()

    def destroy(self):
        if self.pdf_doc:
            try:
                self.pdf_doc.close()
            except Exception as e:
                print(f"Erreur lors de la fermeture du document PDF: {e}")
            self.pdf_doc = None
        if self.temp_dir_to_clean:
            archive_utils.cleanup_temp_dir(self.temp_dir_to_clean)
        super().destroy()