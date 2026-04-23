import re
from datetime import datetime
from pathlib import Path

from ...core.utils import token_cap
from ..identity_utils import clean_filename_stem

_EXIF_KEEP = {"Make", "Model", "Software", "DateTime", "DateTimeOriginal", "ImageDescription"}
_HEIC_EXTS = {".heic", ".heif"}
_OCR_TOKEN_THRESHOLD = 8
_PHOTO_FALLBACK_MIN_TOKENS = 5


def _date_bucket(file_path: Path) -> str:
    try:
        dt = datetime.fromtimestamp(file_path.stat().st_mtime)
        return f"photo {dt.strftime('%B').lower()} {dt.year}"
    except Exception:
        return f"photo {clean_filename_stem(str(file_path))}"


def _read_pil_exif(file_path: Path) -> list[str]:
    from PIL import Image
    from PIL.ExifTags import TAGS

    img = Image.open(file_path)
    exif_data = img._getexif() if hasattr(img, "_getexif") else None
    if not exif_data:
        return []

    parts = []
    for tag_id, value in exif_data.items():
        tag = TAGS.get(tag_id, "")
        if tag not in _EXIF_KEEP:
            continue
        v = str(value).strip()
        if v and v not in ("0", ""):
            parts.append(f"{tag}:{v}")
    return parts


def _read_heic_exif(file_path: Path) -> list[str]:
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        return _read_pil_exif(file_path)
    except ImportError:
        return []


def _normalize_ocr_text(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9\s:/.-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _ocr_text(file_path: Path) -> str:
    try:
        from PIL import Image, ImageOps
        import pytesseract

        img = Image.open(file_path)
        img = ImageOps.exif_transpose(img)
        gray = ImageOps.grayscale(img)
        boosted = ImageOps.autocontrast(gray)
        enlarged = boosted.resize((boosted.width * 2, boosted.height * 2))
        thresholded = enlarged.point(lambda px: 255 if px > 180 else 0)
        text = pytesseract.image_to_string(thresholded, config="--oem 3 --psm 6")
        return _normalize_ocr_text(text)
    except Exception:
        return ""


def _ocr_token_count(text: str) -> int:
    return len([tok for tok in text.split() if len(tok) > 1])


def _photo_identity(file_path: Path, exif_parts: list[str]) -> str:
    stem = clean_filename_stem(str(file_path))
    parts: list[str] = ["photo"]

    make_model = []
    for item in exif_parts:
        if item.startswith("Make:") or item.startswith("Model:"):
            make_model.append(item.split(":", 1)[1].strip())

    description = next(
        (item.split(":", 1)[1].strip() for item in exif_parts if item.startswith("ImageDescription:")),
        "",
    )

    bucket = _date_bucket(file_path)
    parts.append(bucket)
    if make_model:
        parts.extend(make_model[:2])
    if description:
        parts.append(description)
    elif stem:
        parts.append(stem)

    result = token_cap(" ".join(parts))
    if len(result.split()) < _PHOTO_FALLBACK_MIN_TOKENS:
        return token_cap(f"{bucket} {stem}")
    return result


class OCRExtractorAgent:
    def extract(self, file_path: str) -> str:
        p = Path(file_path)

        try:
            if p.suffix.lower() in _HEIC_EXTS:
                exif_parts = _read_heic_exif(p)
            else:
                exif_parts = _read_pil_exif(p)
        except Exception:
            exif_parts = []

        ocr_text = _ocr_text(p)
        if _ocr_token_count(ocr_text) >= _OCR_TOKEN_THRESHOLD:
            stem = clean_filename_stem(file_path)
            if stem:
                return token_cap(f"scanned document {stem} {ocr_text}")
            return token_cap(f"scanned document {ocr_text}")

        return _photo_identity(p, exif_parts)
