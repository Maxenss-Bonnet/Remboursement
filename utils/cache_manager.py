import os
import shutil
import tempfile
import time
import logging
from typing import List, Dict, Any, Tuple

from config.settings import REMBOURSEMENTS_ATTACHMENTS_DIR, REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR
from models.schemas import Remboursement

_log = logging.getLogger(__name__)

CACHE_LIFETIME_SECONDS = 30 * 24 * 3600  # 30 jours


class CacheManager:
    def __init__(self):
        self.cache_dir = os.path.join(tempfile.gettempdir(), "remboursements_cache")
        self.pfp_cache_dir = os.path.join(self.cache_dir, "pfp_cache")
        self.demand_query_cache: Dict[str, Tuple[Any, float]] = {}
        self.ensure_cache_dir()

    def ensure_cache_dir(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.pfp_cache_dir, exist_ok=True)

    def get_demand_query_cache(self, key: str, max_age_seconds: int = 300) -> Any | None:
        if key in self.demand_query_cache:
            data, timestamp = self.demand_query_cache[key]
            if time.time() - timestamp < max_age_seconds:
                return data
        return None

    def set_demand_query_cache(self, key: str, data: Any):
        self.demand_query_cache[key] = (data, time.time())

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
            _log.error(f"Erreur lors de l'ajout du fichier au cache : {e}")

    def get_cached_pfp_path(self, login: str, size: int) -> str:
        safe_login = login.replace('.', '_').replace(' ', '_')
        return os.path.join(self.pfp_cache_dir, f"pfp_{safe_login}_{size}.png")

    def invalidate_pfp_cache(self, login: str):
        safe_login = login.replace('.', '_').replace(' ', '_')
        prefix_to_find = f"pfp_{safe_login}_"
        try:
            if os.path.exists(self.pfp_cache_dir):
                for filename in os.listdir(self.pfp_cache_dir):
                    if filename.startswith(prefix_to_find):
                        os.remove(os.path.join(self.pfp_cache_dir, filename))
        except OSError as e:
            _log.error(f"Erreur lors de l'invalidation du cache PFP pour {login}: {e}")

    def sync_proactive_cache(self, demands_to_cache: List[Remboursement]):
        _log.info(f"Début de la synchronisation proactive du cache pour {len(demands_to_cache)} demandes.")
        try:
            active_files_on_disk = set(os.listdir(self.cache_dir))
            required_cached_files = set()

            all_attachments_map: Dict[str, str] = {}
            for demande in demands_to_cache:
                if demande.is_archived:
                    base_dir = REMBOURSEMENTS_ARCHIVE_ATTACHMENTS_DIR
                else:
                    base_dir = REMBOURSEMENTS_ATTACHMENTS_DIR

                all_attachments = (demande.chemins_factures_stockees +
                                   demande.chemins_rib_stockes +
                                   demande.chemins_trop_percu_stockees)

                for rel_path in all_attachments:
                    cached_filename = self._get_cached_filename(rel_path)
                    required_cached_files.add(cached_filename)
                    if cached_filename not in all_attachments_map:
                        all_attachments_map[cached_filename] = (rel_path, base_dir, demande.is_archived, demande.reference_facture_dossier)

            files_to_add = required_cached_files - active_files_on_disk
            files_added_count = 0
            for filename in files_to_add:
                rel_path, base_dir, is_archived, _ = all_attachments_map.get(filename)
                if rel_path:
                    if is_archived:
                        continue
                    source_path = os.path.join(base_dir, rel_path)
                    destination_path = os.path.join(self.cache_dir, filename)
                    if os.path.exists(source_path):
                        shutil.copy2(source_path, destination_path)
                        files_added_count += 1
            if files_added_count > 0:
                _log.info(f"{files_added_count} nouveaux fichiers ajoutés au cache proactif.")

        except Exception as e:
            _log.error(f"Erreur lors de la synchronisation du cache proactif : {e}", exc_info=True)

    def cleanup_old_cache_files(self):
        _log.info("Lancement du nettoyage du cache local...")
        deleted_files = 0
        deleted_size = 0
        now = time.time()
        try:
            for dirpath, _, filenames in os.walk(self.cache_dir):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        if os.path.getmtime(file_path) < (now - CACHE_LIFETIME_SECONDS):
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted_files += 1
                            deleted_size += file_size
                    except (OSError, FileNotFoundError):
                        continue
            if deleted_files > 0:
                size_mb = deleted_size / (1024 * 1024)
                _log.info(f"Nettoyage du cache terminé. {deleted_files} fichiers supprimés ({size_mb:.2f} MB).")
            else:
                _log.info("Aucun fichier de cache obsolète à nettoyer.")
        except Exception as e:
            _log.error(f"Erreur lors du nettoyage du cache : {e}", exc_info=True)

    def clear_all_cache(self):
        try:
            shutil.rmtree(self.cache_dir)
            self.ensure_cache_dir()
        except Exception as e:
            _log.error(f"Erreur lors du nettoyage complet du cache : {e}")