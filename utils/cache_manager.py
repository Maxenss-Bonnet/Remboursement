import os
import shutil
import tempfile
from typing import List, Dict

from config.settings import REMBOURSEMENTS_ATTACHMENTS_DIR
from models.schemas import Remboursement


class CacheManager:
    def __init__(self):
        self.cache_dir = os.path.join(tempfile.gettempdir(), "remboursements_cache")
        self.ensure_cache_dir()

    def ensure_cache_dir(self):
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cached_filename(self, rel_path: str) -> str:
        return rel_path.replace('\\', '_').replace('/', '_')

    def get_cached_path(self, rel_path: str) -> str | None:
        if not rel_path:
            return None
        cached_file_path = os.path.join(self.cache_dir, self._get_cached_filename(rel_path))
        return cached_file_path if os.path.exists(cached_file_path) else None

    def add_to_cache(self, source_path: str, rel_path: str):
        if not rel_path or not os.path.exists(source_path):
            return

        cached_filename = self._get_cached_filename(rel_path)
        destination_path = os.path.join(self.cache_dir, cached_filename)

        if os.path.exists(destination_path):
            return

        try:
            shutil.copy2(source_path, destination_path)
        except Exception as e:
            print(f"Erreur lors de l'ajout du fichier au cache : {e}")

    def sync_proactive_cache(self, demands_to_cache: List[Remboursement]):
        try:
            active_files_on_disk = set(os.listdir(self.cache_dir))
            required_cached_files = set()

            all_attachments_map: Dict[str, str] = {}
            for demande in demands_to_cache:
                if demande.is_archived:
                    continue

                all_attachments = (demande.chemins_factures_stockees +
                                   demande.chemins_rib_stockes +
                                   demande.chemins_trop_percu_stockees)

                for rel_path in all_attachments:
                    cached_filename = self._get_cached_filename(rel_path)
                    required_cached_files.add(cached_filename)
                    if cached_filename not in all_attachments_map:
                        all_attachments_map[cached_filename] = rel_path

            files_to_add = required_cached_files - active_files_on_disk
            for filename in files_to_add:
                rel_path = all_attachments_map.get(filename)
                if rel_path:
                    source_path = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, rel_path)
                    destination_path = os.path.join(self.cache_dir, filename)
                    if os.path.exists(source_path):
                        shutil.copy2(source_path, destination_path)

            files_to_delete = active_files_on_disk - required_cached_files
            for filename in files_to_delete:
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                except OSError:
                    pass
        except Exception as e:
            print(f"Erreur lors de la synchronisation du cache proactif : {e}")

    def clear_all_cache(self):
        try:
            shutil.rmtree(self.cache_dir)
            self.ensure_cache_dir()
        except Exception as e:
            print(f"Erreur lors du nettoyage complet du cache : {e}")