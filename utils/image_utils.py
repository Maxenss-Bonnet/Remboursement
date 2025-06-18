import os
from PIL import Image, ImageDraw, ImageOps
import customtkinter as ctk


def get_or_create_circular_pfp(login: str, source_path: str, size: int,
                               cache_manager) -> ctk.CTkImage | None:
    """
    Charge une PFP depuis le cache local. Si le cache est obsolète (le fichier
    source sur le réseau est plus récent) ou n'existe pas, il est (re)généré.
    """
    cached_path = cache_manager.get_cached_pfp_path(login, size)
    source_exists = source_path and os.path.exists(source_path)

    # 1. Vérifier si le cache existant est valide
    if os.path.exists(cached_path):
        is_valid = True
        try:
            # Invalider si la source n'existe plus
            if not source_exists:
                is_valid = False
            # Invalider si la source est plus récente que le cache
            elif os.path.getmtime(source_path) > os.path.getmtime(cached_path):
                is_valid = False

            if not is_valid:
                os.remove(cached_path)

        except (OSError, FileNotFoundError):
            # Si une erreur survient (ex: lecture timestamp), on considère le cache invalide
            if os.path.exists(cached_path):
                try:
                    os.remove(cached_path)
                except OSError:
                    pass
            is_valid = False

    # 2. Si le cache est valide et existe toujours, on l'utilise
    if os.path.exists(cached_path):
        try:
            pil_image = Image.open(cached_path)
            # CTkImage gère l'image, pas besoin de la garder ouverte avec 'with'
            return ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(size, size))
        except Exception:
            # Le fichier cache est peut-être corrompu, on va le regénérer
            pass

    # 3. Si on arrive ici, le cache doit être généré depuis la source
    if not source_exists:
        return None

    try:
        with Image.open(source_path) as img:
            img = img.convert("RGBA")
            img_fit = ImageOps.fit(img, (size, size), Image.Resampling.LANCZOS)

            mask = Image.new('L', (size, size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, size, size), fill=255)

            img_fit.putalpha(mask)
            img_fit.save(cached_path, "PNG")

            return ctk.CTkImage(light_image=img_fit, dark_image=img_fit, size=(size, size))

    except Exception as e:
        print(f"Erreur lors de la création de l'image de profil pour {login}: {e}")
        return None