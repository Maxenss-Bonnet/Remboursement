import os
import shutil
import tempfile
from typing import List

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

    def sync_cache_for_user(self, actionable_demandes: List[Remboursement]):
        try:
            active_files_on_disk = set(os.listdir(self.cache_dir))
            required_cached_files = set()

            # Déterminer les fichiers qui DEVRAIENT être en cache
            for demande in actionable_demandes:
                if demande.is_archived:
                    continue

                all_attachments = (demande.chemins_factures_stockees +
                                   demande.chemins_rib_stockes +
                                   demande.chemins_trop_percu_stockees)

                for rel_path in all_attachments:
                    cached_filename = self._get_cached_filename(rel_path)
                    required_cached_files.add(cached_filename)

                    # Si le fichier requis n'est pas en cache, on le copie
                    if cached_filename not in active_files_on_disk:
                        source_path = os.path.join(REMBOURSEMENTS_ATTACHMENTS_DIR, rel_path)
                        destination_path = os.path.join(self.cache_dir, cached_filename)
                        if os.path.exists(source_path):
                            shutil.copy2(source_path, destination_path)

            # Supprimer les fichiers en cache qui ne sont plus nécessaires
            files_to_delete = active_files_on_disk - required_cached_files
            for filename in files_to_delete:
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                except OSError:
                    pass  # Le fichier a peut-être déjà été supprimé
        except Exception as e:
            print(f"Erreur lors de la synchronisation du cache : {e}")

    def clear_all_cache(self):
        try:
            for filename in os.listdir(self.cache_dir):
                os.remove(os.path.join(self.cache_dir, filename))
        except Exception as e:
            print(f"Erreur lors du nettoyage complet du cache : {e}")