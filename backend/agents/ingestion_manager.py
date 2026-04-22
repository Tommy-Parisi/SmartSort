import os
from pathlib import Path
from datetime import datetime
from typing import List
from ..core.models import FileMeta
from ..core.constants import FILE_TYPE_MAP
from ..core.utils import log_error, readable_size

IGNORED_EXTENSIONS = {'.tmp', '.part', '.log'} # Maintain list of ignored extensions
IGNORED_FILENAMES = {'.DS_Store', 'Thumbs.db'} # Special ignored files

SKIP_DIRS = {
    'node_modules', '.git', '__pycache__', '.next', 'dist', 'build',
    'venv', '.venv', 'env', '.env', 'target', '.cache', '.parcel-cache',
    'vendor', 'bower_components', '.tox', 'coverage', '.nyc_output',
    '.gradle', '.idea', '.vscode', '__MACOSX', '.DS_Store',
}

class IngestionManager:
    def __init__(self, root_folder: str, recursive: bool = False):
        self.root = Path(root_folder).resolve()
        self.recursive = recursive
        self.file_meta_queue: List[FileMeta] = []

    def _should_process(self, file_path: Path) -> bool:
        if not file_path.is_file():
            return False
        if file_path.is_symlink():
            return False
        if file_path.name.startswith('.'):
            return False
        if file_path.name in IGNORED_FILENAMES:
            return False
        if file_path.suffix.lower() in IGNORED_EXTENSIONS:
            return False
        return True

    def scan(self):
        if not self.root.exists() or not self.root.is_dir():
            log_error(f"[IngestionManager] Root folder {self.root} does not exist or is not a directory.")
            return

        if not self.recursive:
            candidates = [entry.path for entry in os.scandir(self.root) if entry.is_file(follow_symlinks=False)]
            file_paths = [Path(p) for p in candidates]
        else:
            file_paths = []
            for dirpath, dirnames, filenames in os.walk(self.root):
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]
                for name in filenames:
                    file_paths.append(Path(dirpath) / name)

        for file_path in file_paths:
            if not self._should_process(file_path):
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

