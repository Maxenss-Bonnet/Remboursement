import customtkinter as ctk
from config.settings import (
    STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE,
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO,
    STATUT_PAIEMENT_EFFECTUE, STATUT_ANNULEE
)

# --- Palette de couleurs pour le stepper ---
COLOR_DONE = "#2ECC71"  # Vert
COLOR_CURRENT = "#3498DB"  # Bleu
COLOR_FUTURE = "#95A5A6"  # Gris
COLOR_REJECTED = "#F39C12"  # Orange
COLOR_CANCELLED = "#E74C3C"  # Rouge

# --- Définition des étapes et des statuts associés ---
WORKFLOW_STEPS = [
    {"label": "Création", "statuses": [STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP]},
    {"label": "Constat TP", "statuses": [STATUT_TROP_PERCU_CONSTATE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO]},
    {"label": "Validation", "statuses": [STATUT_VALIDEE]},
    {"label": "Paiement", "statuses": [STATUT_PAIEMENT_EFFECTUE]}
]


class StatusStepper(ctk.CTkFrame):
    def __init__(self, master, current_status: str):
        super().__init__(master, fg_color="transparent")
        self.current_status = current_status
        self.grid_columnconfigure(list(range(len(WORKFLOW_STEPS) * 2 - 1)), weight=1)

        self._build_stepper()

    def _build_stepper(self):
        # Cas spécial pour les statuts terminaux qui ne font pas partie du flux normal
        if self.current_status == STATUT_ANNULEE:
            self.grid_columnconfigure(0, weight=1)
            label = ctk.CTkLabel(self, text="✖ Demande Annulée", font=ctk.CTkFont(size=12, weight="bold"),
                                 text_color=COLOR_CANCELLED)
            label.grid(row=0, column=0, sticky="ew")
            return

        current_step_index = -1
        is_rejected = False

        for i, step in enumerate(WORKFLOW_STEPS):
            if self.current_status in step["statuses"]:
                current_step_index = i
                # Détecte si le statut est un statut de "refus" ou de "retour"
                if self.current_status in [STATUT_REFUSEE_CONSTAT_TP, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO]:
                    is_rejected = True
                break

        # Si le statut est "Paiement effectué", on considère toutes les étapes comme terminées
        if self.current_status == STATUT_PAIEMENT_EFFECTUE:
            current_step_index = len(WORKFLOW_STEPS)

        for i, step_info in enumerate(WORKFLOW_STEPS):
            # Déterminer l'état de l'étape
            if i < current_step_index:
                icon = "✔"
                color = COLOR_DONE
            elif i == current_step_index:
                icon = "●"
                color = COLOR_REJECTED if is_rejected else COLOR_CURRENT
            else:
                icon = "○"
                color = COLOR_FUTURE

            # Créer le label pour l'étape (icône + texte)
            step_label = ctk.CTkLabel(self, text=f"{icon} {step_info['label']}",
                                      font=ctk.CTkFont(size=11, weight="bold" if i == current_step_index else "normal"),
                                      text_color=color)
            step_label.grid(row=0, column=i * 2, padx=4, sticky="ew")

            # Ajouter une ligne de séparation entre les étapes
            if i < len(WORKFLOW_STEPS) - 1:
                line_color = COLOR_DONE if i < current_step_index - 1 else COLOR_FUTURE
                separator = ctk.CTkFrame(self, fg_color=line_color, height=2)
                separator.grid(row=0, column=i * 2 + 1, sticky="ew", padx=2)