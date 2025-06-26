import customtkinter as ctk
import tkinter
import queue
from tkinterdnd2 import DND_FILES, TkinterDnD
from utils.global_events import loader_status_queue


class DragDropFrame(ctk.CTkFrame):
    def __init__(self, master, drop_callback, text="Déposez un fichier ici", **kwargs):
        super().__init__(master, **kwargs)

        self.drop_callback = drop_callback
        self.initial_text = text

        self.configure(border_width=2, border_color="gray50", fg_color=("gray90", "gray25"))

        self.label = ctk.CTkLabel(self, text=self.initial_text, text_color="gray60")
        self.label.pack(padx=20, pady=20, expand=True)

        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drop)
        self.dnd_bind('<<DragEnter>>', self.on_enter)
        self.dnd_bind('<<DragLeave>>', self.on_leave)

        self.border_color_default = "gray50"
        self.border_color_hover = "#1E90FF"

    def on_enter(self, event):
        self.configure(border_color=self.border_color_hover)
        return event.action

    def on_leave(self, event):
        self.configure(border_color=self.border_color_default)
        return event.action

    def on_drop(self, event):
        self.on_leave(event)
        try:
            files = self.winfo_toplevel().tk.splitlist(event.data)
            if files:
                self.drop_callback(files[0])
        except Exception:
            path = event.data.strip('{}')
            if path:
                self.drop_callback(path)
        return event.action


class LoadingCursor:
    def __init__(self, widget):
        self.widget = widget
        self.toplevel = self.widget.winfo_toplevel()

    def __enter__(self):
        self.toplevel.configure(cursor="watch")
        self.toplevel.update_idletasks()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.toplevel.configure(cursor="")


class LoadingOverlay(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.configure(fg_color=("gray20", "gray20"))
        self._polling_job_id = None

        self.main_label = ctk.CTkLabel(self, text="Chargement...", font=ctk.CTkFont(size=16))
        self.main_label.place(relx=0.5, rely=0.5, y=-40, anchor="center")

        # --- CORRECTION APPLIQUÉE ICI ---
        # L'argument 'width' est passé au constructeur, et non à .place()
        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate", width=250)
        self.progress_bar.place(relx=0.5, rely=0.5, anchor="center")
        # ------------------------------------

        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color="gray70")
        self.status_label.place(relx=0.5, rely=0.5, y=30, anchor="center")

    def set_message(self, message: str):
        self.main_label.configure(text=message)
        self.status_label.configure(text="")

    def show(self):
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()
        self.progress_bar.start()
        self._start_polling()

    def hide(self):
        self.progress_bar.stop()
        self._stop_polling()
        self.place_forget()
        while not loader_status_queue.empty():
            try:
                loader_status_queue.get_nowait()
            except queue.Empty:
                break

    def _start_polling(self):
        self._stop_polling()
        self._poll_status_queue()

    def _stop_polling(self):
        if self._polling_job_id:
            self.after_cancel(self._polling_job_id)
            self._polling_job_id = None

    def _poll_status_queue(self):
        try:
            message = loader_status_queue.get_nowait()
            self.status_label.configure(text=message)
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self._polling_job_id = self.after(200, self._poll_status_queue)


class ToastNotification(ctk.CTkFrame):
    _styles = {
        'success': {'fg_color': '#2E8B57', 'text_color': 'white', 'duration': 2500},
        'info': {'fg_color': '#1E90FF', 'text_color': 'white', 'duration': 2500},
        'warning': {'fg_color': '#FFC107', 'text_color': 'black', 'duration': 4000},
        'error': {'fg_color': '#B71C1C', 'text_color': 'white', 'duration': 3500}
    }

    def __init__(self, parent, message, m_type, on_destroy_callback):
        super().__init__(parent, corner_radius=6)
        self.on_destroy_callback = on_destroy_callback

        style = self._styles.get(m_type, self._styles['info'])

        self.configure(fg_color=style['fg_color'])
        label = ctk.CTkLabel(self, text=message, font=ctk.CTkFont(size=14),
                             text_color=style['text_color'], wraplength=350)
        label.pack(padx=15, pady=10)

        duration = style.get('duration', 3000)
        self.after(duration, self._start_destroy)

    def _start_destroy(self):
        self.on_destroy_callback(self)
        self.destroy()


class ToastManager:
    def __init__(self, parent):
        self.parent = parent
        self.active_toasts = []
        self.padding_x = 0.02
        self.padding_y = 10

    def show_toast(self, message, m_type='success'):
        toast = ToastNotification(self.parent, message, m_type, on_destroy_callback=self._remove_toast)
        toast.lift()
        self.active_toasts.append(toast)
        self._reposition_toasts()

    def _remove_toast(self, toast_instance):
        if toast_instance in self.active_toasts:
            self.active_toasts.remove(toast_instance)
        self._reposition_toasts()

    def _reposition_toasts(self):
        self.parent.update_idletasks()
        parent_height = self.parent.winfo_height()

        if parent_height < 100:
            self.parent.after(100, self._reposition_toasts)
            return

        rel_x_pos = 1.0 - self.padding_x
        y_for_bottom_edge = parent_height - self.padding_y

        for toast in reversed(self.active_toasts):
            toast.update_idletasks()
            toast_height = toast.winfo_reqheight()

            rel_y_pos = y_for_bottom_edge / parent_height

            toast.place(relx=rel_x_pos, rely=rel_y_pos, anchor='se')
            toast.lift()

            y_for_bottom_edge -= (toast_height + self.padding_y)