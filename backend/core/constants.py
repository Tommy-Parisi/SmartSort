# core/constants.py

# Types that never produce meaningful semantic signal — skip embedding entirely.
# Files of these types go to an unsorted/ folder rather than entering clustering.
SKIP_EMBEDDING_TYPES = {"video", "audio", "archive", "image"}

# Files producing fewer than this many tokens after extraction get the same treatment.
MIN_TOKENS_TO_EMBED = 5

FILE_TYPE_MAP = {
    # Documents
    '.pdf': 'pdf',
    '.docx': 'docx',
    '.doc': 'docx',
    # Presentations
    '.pptx': 'presentation',
    '.ppt': 'presentation',
    # Text / Markdown
    '.txt': 'text',
    '.md': 'text',
    '.markdown': 'text',
    '.rst': 'text',
    # Tabular
    '.csv': 'tabular',
    '.xlsx': 'tabular',
    '.xls': 'tabular',
    # Code
    '.py': 'code',
    '.js': 'code',
    '.ts': 'code',
    '.tsx': 'code',
    '.jsx': 'code',
    '.java': 'code',
    '.c': 'code',
    '.cpp': 'code',
    '.cc': 'code',
    '.h': 'code',
    '.hpp': 'code',
    '.rs': 'code',
    '.go': 'code',
    '.rb': 'code',
    '.php': 'code',
    '.swift': 'code',
    '.kt': 'code',
    '.cs': 'code',
    '.html': 'code',
    '.css': 'code',
    '.sh': 'code',
    '.bash': 'code',
    '.zsh': 'code',
    '.sql': 'code',
    # Data / config
    '.json': 'data',
    '.yaml': 'data',
    '.yml': 'data',
    '.toml': 'data',
    '.xml': 'data',
    # Images (EXIF + date-bucket fallback; no OCR)
    '.jpg': 'image',
    '.jpeg': 'image',
    '.png': 'image',
    '.gif': 'image',
    '.webp': 'image',
    '.bmp': 'image',
    '.tiff': 'image',
    '.tif': 'image',
    '.heic': 'image',
    '.heif': 'image',
    # Video (filename stem only)
    '.mp4': 'video',
    '.mov': 'video',
    '.webm': 'video',
    '.mkv': 'video',
    '.avi': 'video',
    '.m4v': 'video',
    '.wmv': 'video',
    # Archives / binaries (filename stem only)
    '.zip': 'archive',
    '.tar': 'archive',
    '.gz': 'archive',
    '.bz2': 'archive',
    '.7z': 'archive',
    '.rar': 'archive',
    '.dmg': 'archive',
    '.exe': 'archive',
    '.pkg': 'archive',
    '.deb': 'archive',
    '.rpm': 'archive',
}
