# views/mixins/animation_mixin.py
import customtkinter as ctk


class AnimationMixin:
    def __init__(self, master, *args, **kwargs):
        self.fade_job_id = None

        if isinstance(self, ctk.CTkToplevel) or isinstance(self, ctk.CTk):
            self.attributes('-alpha', 0)

    def fade_in(self, duration_ms: int = 250):
        if self.fade_job_id:
            self.after_cancel(self.fade_job_id)

        self._animate_fade(0, 1.0, duration_ms, "in")

    def fade_out_and_destroy(self, duration_ms: int = 200):
        if self.fade_job_id:
            self.after_cancel(self.fade_job_id)

        self._animate_fade(1.0, 0, duration_ms, "out")

    def _animate_fade(self, start_alpha: float, end_alpha: float, duration_ms: int, direction: str):
        steps = int(duration_ms / 15)
        if steps == 0: steps = 1

        delta = (end_alpha - start_alpha) / steps
        current_alpha = start_alpha

        def _step(current_step):
            nonlocal current_alpha
            current_alpha += delta

            if (direction == "in" and current_alpha > end_alpha) or \
                    (direction == "out" and current_alpha < end_alpha):
                current_alpha = end_alpha

            try:
                if self.winfo_exists():
                    self.attributes('-alpha', current_alpha)
            except Exception:
                return

            if current_step < steps and self.winfo_exists():
                self.fade_job_id = self.after(15, lambda: _step(current_step + 1))
            elif direction == "out":
                try:
                    if self.winfo_exists():
                        # CORRECTION : Appelle la méthode destroy() de l'instance
                        # pour permettre la surcharge et le nettoyage.
                        self.destroy()
                except Exception:
                    pass

        _step(0)

    def close_animated(self):
        """Méthode à appeler pour fermer la fenêtre avec une animation."""
        self.fade_out_and_destroy()