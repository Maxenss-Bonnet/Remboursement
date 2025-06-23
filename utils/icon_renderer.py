import os
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont
from config.settings import APP_ROOT_PATH, STATUT_CREEE, STATUT_REFUSEE_CONSTAT_TP, STATUT_TROP_PERCU_CONSTATE, \
    STATUT_VALIDEE, STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO, STATUT_ANNULEE, STATUT_PAIEMENT_EFFECTUE

_icon_cache = {}
_font_cache = {}

# --- Palette de couleurs professionnelles ---
COLOR_SUCCESS = "#28a745"
COLOR_DANGER = "#dc3545"
COLOR_WARNING = "#ffc107"
COLOR_INFO = "#17a2b8"
COLOR_PRIMARY = "#007bff"
COLOR_SECONDARY = "#6c757d"
WHITE = "#FFFFFF"

# --- Mapping des statuts aux caractères Unicode de FontAwesome et aux couleurs ---
# Les caractères sont trouvés sur la "cheatsheet" de FontAwesome (ex: \uf00c pour 'check')
ICON_MAPPING = {
    STATUT_CREEE: ("\uf15c", COLOR_INFO),  # fa-file-text
    STATUT_REFUSEE_CONSTAT_TP: ("\uf057", COLOR_DANGER),  # fa-times-circle
    STATUT_TROP_PERCU_CONSTATE: ("\uf002", COLOR_PRIMARY),  # fa-search
    STATUT_VALIDEE: ("\uf087", COLOR_SUCCESS),  # fa-thumbs-up
    STATUT_REFUSEE_VALIDATION_CORRECTION_MLUPO: ("\uf0e2", COLOR_WARNING),  # fa-undo
    STATUT_PAIEMENT_EFFECTUE: ("\uf058", COLOR_SUCCESS),  # fa-check-circle
    STATUT_ANNULEE: ("\uf05e", COLOR_SECONDARY)  # fa-ban
}

def _get_font(size: int):
    """Charge et met en cache la police FontAwesome."""
    if size in _font_cache:
        return _font_cache[size]
    try:
        font_path = os.path.join(APP_ROOT_PATH, "assets", "fonts", "Font Awesome 6 Free-Solid-900.otf")
        font = ImageFont.truetype(font_path, size)
        _font_cache[size] = font
        return font
    except IOError:
        print(f"ERREUR: Impossible de charger la police FontAwesome depuis {font_path}")
        # Tente de charger une police par défaut en cas d'échec
        try:
            font = ImageFont.truetype("arial.ttf", size)
            _font_cache[size] = font
            return font
        except IOError:
            return ImageFont.load_default()


def get_icon_image(status: str, size: int) -> ctk.CTkImage | None:
    """
    Crée une CTkImage pour un statut donné en utilisant la police FontAwesome locale.
    """
    if status not in ICON_MAPPING:
        return None

    cache_key = (status, size)
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    unicode_char, color = ICON_MAPPING[status]
    font = _get_font(int(size * 0.9))

    try:
        # Crée une image de base transparente
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Dessine le caractère/icône au centre avec la bonne couleur
        draw.text((size / 2, size / 2), text=unicode_char, font=font, anchor="mm", fill=color)

        ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
        _icon_cache[cache_key] = ctk_image
        return ctk_image
    except Exception as e:
        print(f"Erreur lors de la création de l'icône pour le statut '{status}': {e}")
        _icon_cache[cache_key] = None
        return None