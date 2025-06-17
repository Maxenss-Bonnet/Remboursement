import os
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image
import fitz
import sys
import subprocess
import threading
import queue
import io
from utils import archive_utils
from views.mixins.task_runner_mixin import TaskRunnerMixin


class DocumentViewerWindow(ctk.CTkToplevel, TaskRunnerMixin):
    def __init__(self, master, file_path: str, title: str, temp_dir_to_clean: str | None = None):
        ctk.CTkToplevel.__init__(self, master)
        TaskRunnerMixin.__init__(self, parent_for_overlay=self)

        self.title(title)
        self.geometry("800x600")
        self.transient(master)
        self.grab_set()
        self.resizable(True, True)
        self.minsize(400, 300)

        self.master = master
        self.file_path = file_path
        self.temp_dir_to_clean = temp_dir_to_clean
        self.pdf_doc = None
        self.page_render_queue = queue.Queue()
        self.stop_rendering_thread = threading.Event()
        self.after_job_id = None
        self.page_labels = {}

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.scrollable_frame = ctk.CTkScrollableFrame(self)
        self.scrollable_frame.pack(expand=True, fill="both", padx=10, pady=10)

        self.content_container = ctk.CTkFrame(self.scrollable_frame, fg_color="transparent")
        self.content_container.pack(expand=True, fill="both")

        self.load_and_display_document()

    def load_and_display_document(self):
        file_ext = self.file_path.lower().split('.')[-1] if self.file_path else ''

        def task():
            if file_ext in ("png", "jpg", "jpeg", "gif", "bmp"):
                return 'image', self._load_image_data()
            elif file_ext == "pdf":
                return 'pdf', self._load_pdf_first_page()
            else:
                return 'unsupported', None

        def on_complete(result, error):
            if error:
                self._display_error(error)
                return

            doc_type, data = result
            if doc_type == 'image':
                self._display_image(data)
            elif doc_type == 'pdf':
                if data:
                    first_page_img, page_count = data
                    self._display_page_from_image(0, first_page_img)
                    if page_count > 1 and self.pdf_doc:
                        render_thread = threading.Thread(target=self._render_remaining_pages, daemon=True)
                        render_thread.start()
                        self._check_page_queue()
            else:
                self._display_unsupported_format()

        self.run_task(task, on_complete, "Chargement du document...")

    def _load_image_data(self):
        with open(self.file_path, "rb") as f:
            image_bytes = io.BytesIO(f.read())
        return Image.open(image_bytes)

    def _load_pdf_first_page(self):
        with open(self.file_path, "rb") as f:
            pdf_bytes = f.read()

        self.pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if not self.pdf_doc.page_count:
            raise ValueError("Le fichier PDF est vide.")

        page = self.pdf_doc.load_page(0)
        mat = fitz.Matrix(1.5, 1.5)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        if pix.width == 0 or pix.height == 0:
            raise ValueError("Impossible de rendre la première page du PDF.")

        return Image.frombytes("RGB", [pix.width, pix.height], pix.samples), self.pdf_doc.page_count

    def _display_image(self, pil_image):
        try:
            screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
            max_w, max_h = int(screen_w * 0.9), int(screen_h * 0.85)

            img_w, img_h = pil_image.size
            window_w = min(img_w + 60, max_w)
            window_h = min(img_h + 60, max_h)
            self.geometry(f"{int(window_w)}x{int(window_h)}")
            self.update_idletasks()

            ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(img_w, img_h))
            image_label = ctk.CTkLabel(self.content_container, image=ctk_img, text="")
            image_label.pack(padx=0, pady=0)
        except Exception as e:
            self._display_error(e)

    def _render_page_in_thread(self, page_num):
        if not self.pdf_doc: return
        try:
            page = self.pdf_doc.load_page(page_num)
            mat = fitz.Matrix(1.5, 1.5)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            if pix.width == 0 or pix.height == 0: return

            pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.page_render_queue.put((page_num, pil_image))
        except Exception as e:
            print(f"Erreur lors du rendu de la page {page_num}: {e}")

    def _display_page_from_image(self, page_num, pil_image):
        if not self.winfo_exists(): return

        w, h = pil_image.size
        ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(w, h))

        if page_num in self.page_labels:
            self.page_labels[page_num].configure(image=ctk_img)
        else:
            page_label = ctk.CTkLabel(self.content_container, image=ctk_img, text="")
            page_label.pack(pady=(0 if page_num == 0 else 5, 0), padx=5)
            self.page_labels[page_num] = page_label

        if page_num == 0:
            screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
            max_w, max_h = int(screen_w * 0.9), int(screen_h * 0.85)
            win_w = min(w + 70, max_w)
            win_h = min(max(500, h + 60), max_h)
            self.geometry(f"{int(win_w)}x{int(win_h)}")

    def _render_remaining_pages(self):
        if not self.pdf_doc: return
        for i in range(1, self.pdf_doc.page_count):
            if self.stop_rendering_thread.is_set(): break
            self._render_page_in_thread(i)

    def _check_page_queue(self):
        try:
            while not self.page_render_queue.empty():
                page_num, pil_image = self.page_render_queue.get_nowait()
                self._display_page_from_image(page_num, pil_image)
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists() and not self.stop_rendering_thread.is_set():
                self.after_job_id = self.after(100, self._check_page_queue)

    def _display_unsupported_format(self):
        detail = f"Aperçu direct non supporté pour '{os.path.basename(self.file_path)}'."
        ctk.CTkLabel(self.content_container, text=detail, wraplength=380).pack(pady=20)
        self.geometry("500x150")
        if messagebox.askyesno("Ouvrir le fichier ?",
                               f"{detail}\n\nVoulez-vous l'ouvrir avec l'application par défaut ?", parent=self):
            self._open_with_system_default()

    def _display_error(self, error):
        print(f"Erreur détaillée DocumentViewer: {error}")
        for widget in self.content_container.winfo_children():
            widget.destroy()
        msg = f"Une erreur est survenue lors de l'affichage du document:\n{error}"
        ctk.CTkLabel(self.content_container, text=msg, wraplength=380).pack(pady=20)
        self.geometry("400x200")
        if messagebox.askyesno("Ouvrir avec le système ?",
                               f"{msg}\n\nVoulez-vous essayer de l'ouvrir avec l'application par défaut ?",
                               parent=self):
            self._open_with_system_default()

    def _open_with_system_default(self, close_viewer_after=True):
        try:
            if os.name == 'nt':
                os.startfile(self.file_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.file_path], check=True)
            else:
                subprocess.run(['xdg-open', self.file_path], check=True)
            if close_viewer_after: self.on_close()
        except Exception as e_gen:
            self.app_controller.show_toast(f"Impossible d'ouvrir le fichier avec l'application par défaut : {e_gen}",
                                           "error")

    def on_close(self):
        self.stop_rendering_thread.set()
        if self.after_job_id:
            self.after_cancel(self.after_job_id)
            self.after_job_id = None
        if self.pdf_doc:
            try:
                self.pdf_doc.close()
            except Exception as e:
                print(f"Erreur lors de la fermeture du document PDF: {e}")
            self.pdf_doc = None
        if self.temp_dir_to_clean:
            archive_utils.cleanup_temp_dir(self.temp_dir_to_clean)
        self.destroy()