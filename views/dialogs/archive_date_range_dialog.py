import customtkinter as ctk
import datetime
from views.mixins.animation_mixin import AnimationMixin


class ArchiveDateRangeDialog(ctk.CTkToplevel, AnimationMixin):
    def __init__(self, master):
        super().__init__(master)
        AnimationMixin.__init__(self, master)

        self.transient(master)
        self.grab_set()
        self.title("Consulter les Archives")
        self.geometry("350x250")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self._result = None
        self.master = master

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        main_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(main_frame, text="Année de début:").grid(row=0, column=0, padx=(0, 10), pady=10, sticky="w")
        self.start_year_entry = ctk.CTkEntry(main_frame)
        self.start_year_entry.grid(row=0, column=1, pady=10, sticky="ew")
        self.start_year_entry.insert(0, str(datetime.date.today().year))

        ctk.CTkLabel(main_frame, text="Année de fin:").grid(row=1, column=0, padx=(0, 10), pady=10, sticky="w")
        self.end_year_entry = ctk.CTkEntry(main_frame)
        self.end_year_entry.grid(row=1, column=1, pady=10, sticky="ew")
        self.end_year_entry.insert(0, str(datetime.date.today().year))

        self.end_year_entry.bind("<Return>", self._on_validate)

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.grid(row=2, column=0, columnspan=2, pady=(20, 0))

        ctk.CTkButton(button_frame, text="Valider", command=self._on_validate).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Annuler", command=self._on_cancel, fg_color="gray").pack(side="left", padx=10)

        self.after(100, self.start_year_entry.focus)
        self.fade_in()

    def _on_validate(self, event=None):
        try:
            start_year = int(self.start_year_entry.get())
            end_year = int(self.end_year_entry.get())

            if not (2000 < start_year < 2100 and 2000 < end_year < 2100):
                self.master.app_controller.show_toast("Veuillez entrer des années valides.", "error")
                return

            if start_year > end_year:
                self.master.app_controller.show_toast("L'année de début ne peut pas être supérieure à l'année de fin.",
                                                      "error")
                return

            self._result = (start_year, end_year)
            self.close_animated()

        except (ValueError, TypeError):
            self.master.app_controller.show_toast("Veuillez entrer des années en chiffres (ex: 2024).", "error")

    def _on_cancel(self):
        self._result = None
        self.close_animated()

    def get_range(self):
        self.master.wait_window(self)
        return self._result