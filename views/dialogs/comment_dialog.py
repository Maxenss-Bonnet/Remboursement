import customtkinter as ctk
from views.mixins.animation_mixin import AnimationMixin


class CommentDialog(ctk.CTkToplevel, AnimationMixin):
    def __init__(self, master, title: str, prompt: str, is_mandatory: bool = False):
        super().__init__(master)
        AnimationMixin.__init__(self, master)

        self.transient(master)
        self.grab_set()
        self.title(title)
        self.geometry("450x300")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close_animated)

        self._comment = None
        self._is_mandatory = is_mandatory
        self.master = master

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        prompt_label_text = f"{prompt}{' (Obligatoire)' if is_mandatory else ' (Optionnel)'}"
        prompt_label = ctk.CTkLabel(main_frame, text=prompt_label_text, wraplength=400, justify="left")
        prompt_label.pack(pady=(0, 10), anchor="w")

        self.comment_textbox = ctk.CTkTextbox(main_frame, height=150)
        self.comment_textbox.pack(expand=True, fill="both")
        self.comment_textbox.focus()

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=(15, 0))

        ctk.CTkButton(button_frame, text="Valider", command=self._on_validate).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Annuler", command=self._on_cancel, fg_color="gray").pack(side="left", padx=10)

        self.fade_in()

    def _on_validate(self):
        comment_text = self.comment_textbox.get("1.0", "end-1c").strip()
        if self._is_mandatory and not comment_text:
            self.master.app_controller.show_toast("Le commentaire est obligatoire pour cette action.", "error")
            return

        self._comment = comment_text
        self.close_animated()

    def _on_cancel(self):
        self._comment = None
        self.close_animated()

    def get_comment(self):
        self.master.wait_window(self)
        return self._comment