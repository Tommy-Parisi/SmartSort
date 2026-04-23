import json
from pathlib import Path
from ...core.utils import token_cap
from ..identity_utils import clean_filename_stem

# Keys that indicate a numeric annotation/label file (COCO, YOLO, BDD, etc.)
_ANNOTATION_KEYS = {
    "bbox", "bboxes", "segmentation", "keypoints", "category_id",
    "image_id", "annotation_id", "area", "iscrowd", "supercategory",
    "box2d", "poly2d", "attributes", "occluded", "truncated",
}


def _is_numeric_annotation(data: dict) -> bool:
    """True if the dict looks like a per-image annotation record."""
    keys = {str(k).lower() for k in data.keys()}
    if not keys & _ANNOTATION_KEYS:
        return False
    non_string_vals = sum(
        1 for v in data.values() if not isinstance(v, str)
    )
    return non_string_vals >= len(data) * 0.7


def _extract_strings(obj, depth: int = 0, max_depth: int = 2, limit: int = 30) -> list:
    """Recursively collect string leaf values, capped."""
    results = []
    if depth > max_depth or len(results) >= limit:
        return results
    if isinstance(obj, str) and obj.strip():
        results.append(obj.strip())
    elif isinstance(obj, dict):
        for v in obj.values():
            results.extend(_extract_strings(v, depth + 1, max_depth, limit))
            if len(results) >= limit:
                break
    elif isinstance(obj, list):
        for item in obj[:10]:
            results.extend(_extract_strings(item, depth + 1, max_depth, limit))
            if len(results) >= limit:
                break
    return results


class JSONExtractorAgent:
    def extract(self, file_path: str) -> str:
        stem = clean_filename_stem(file_path)

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
        except Exception:
            return stem

        if isinstance(data, dict):
            if _is_numeric_annotation(data):
                # Filename stem often carries the semantic label (e.g. "Car (106)")
                return stem
            keys = [str(k) for k in list(data.keys())[:20]]
            strings = _extract_strings(data, limit=30)
            return token_cap(" ".join(keys + strings))

        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                keys = {str(k).lower() for k in first.keys()}
                if keys & _ANNOTATION_KEYS:
                    # COCO-style list — try to pull category names
                    strings = _extract_strings(data[:5], limit=20)
                    if strings:
                        return token_cap(f"annotations {len(data)} items " + " ".join(strings))
                    return stem
                keys_text = " ".join(str(k) for k in list(first.keys())[:20])
                strings = _extract_strings(data[:3], limit=20)
                return token_cap(f"array {len(data)} items " + keys_text + " " + " ".join(strings))

        return stem
