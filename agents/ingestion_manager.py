import os 
from pathlib import Path
from datetime import datetime
from typing import List
from core.models import FileMeta
from core.constants import FILE_TYPE_MAP
from core.utils import log_error, readable_size

IGNORED_EXTENSIONS = {'.tmp', '.part', '.log'} # Maintain list of ignored extensions
IGNORED_FILENAMES = {'.DS_Store', 'Thumbs.db'} # Special ignored files

class IngestionManager:
    def __init__(self, root_folder: str, recursive: bool = True):
        self.root = Path(root_folder).resolve()
        self.recursive = recursive
        self.file_meta_queue: List[FileMeta] = []

    def scan(self):
        if not self.root.exists() or not self.root.is_dir():
            log_error(f"[IngestionManager] Root folder {self.root} does not exist or is not a directory.")
            return
        
        files = self.root.rglob("*") if self.recursive else self.root.glob("*")
        for file_path in files:
            if not file_path.is_file():
                continue
            if file_path.name in IGNORED_FILENAMES:
                continue
            if file_path.suffix.lower() in IGNORED_EXTENSIONS:
                continue

            try:
                meta = self.create_file_meta(file_path)
                if meta:
                    self.file_meta_queue.append(meta)
            except Exception as e:
                log_error(f"[IngestionManager] Failed to ingest {file_path}: {e}")
        
    def create_file_meta(self, file_path: Path) -> FileMeta:
        extension = file_path.suffix.lower()
        detected_type = FILE_TYPE_MAP.get(extension, 'unknown')
        stat = file_path.stat()

        return FileMeta(
            file_path=str(file_path.resolve()),
            file_name=file_path.name,
            extension=extension,
            detected_type=detected_type,
            size_kb=round(stat.st_size / 1024, 2),
            created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
            modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            status="pending"
        )

    def summary(self):
        print(f"[IngestionManager] Found {len(self.file_meta_queue)} valid files.")
        for f in self.file_meta_queue:
            print(f"  - {f.file_name} ({f.detected_type}, {readable_size(f.size_kb)} KB)")

