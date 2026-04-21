from datetime import datetime
from pathlib import Path
from ...core.utils import token_cap

_EXIF_KEEP = {"Make", "Model", "Software", "DateTime", "DateTimeOriginal", "ImageDescription"}
_HEIC_EXTS = {".heic", ".heif"}
_WEAK_TOKEN_THRESHOLD = 5


def _date_bucket(file_path: Path) -> str:
    """Coarse month/year bucket from filesystem mtime for low-signal images."""
    try:
        dt = datetime.fromtimestamp(file_path.stat().st_mtime)
        return f"photos {dt.strftime('%B').lower()} {dt.year}"
    except Exception:
        return file_path.stem


def _read_pil_exif(file_path: Path) -> list:
    from PIL import Image
    from PIL.ExifTags import TAGS
    img = Image.open(file_path)
    exif_data = img._getexif() if hasattr(img, "_getexif") else None
    if not exif_data:
        return []
    parts = []
    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, "")
        if tag in _EXIF_KEEP:
            v = str(value).strip()
            if v and v not in ("0", ""):
                parts.append(f"{tag}:{v}")
    return parts


def _read_heic_exif(file_path: Path) -> list:
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        return _read_pil_exif(file_path)
    except ImportError:
        return []


class OCRExtractorAgent:
    def extract(self, file_path: str) -> str:
        p = Path(file_path)
        parts = []

        try:
            if p.suffix.lower() in _HEIC_EXTS:
                parts = _read_heic_exif(p)
            else:
                parts = _read_pil_exif(p)
        except Exception:
            pass

        parts.append(p.stem)
        result = token_cap(" ".join(parts))

        # Weak-signal fallback: group by month/year so these don't all become noise
        if len(result.split()) < _WEAK_TOKEN_THRESHOLD:
            result = _date_bucket(p)

        return result
