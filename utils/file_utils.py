import os
import shutil
from typing import Callable
from .decorators import retry_on_network_error


@retry_on_network_error(retries=4, delay=2.5)
def copy_with_progress(source_path: str, dest_path: str, progress_callback: Callable[[float], None]):
    """
    Copie un fichier d'une source vers une destination en appelant un callback
    avec le pourcentage de progression. Réessaie en cas d'erreur réseau.
    """
    try:
        total_size = os.path.getsize(source_path)
        if total_size == 0:
            shutil.copy2(source_path, dest_path)
            if progress_callback:
                progress_callback(1.0)
            return

        copied_size = 0
        chunk_size = 1024 * 1024  # 1 MB

        with open(source_path, 'rb') as src_file:
            with open(dest_path, 'wb') as dest_file:
                while True:
                    chunk = src_file.read(chunk_size)
                    if not chunk:
                        break
                    dest_file.write(chunk)
                    copied_size += len(chunk)
                    if progress_callback:
                        progress = min(1.0, copied_size / total_size)
                        progress_callback(progress)
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise e