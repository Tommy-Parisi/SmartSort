import json
from pathlib import Path
from ...core.utils import token_cap


class JSONExtractorAgent:
    def extract(self, file_path: str) -> str:
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
        except Exception:
            return Path(file_path).stem

        if isinstance(data, dict):
            keys = list(data.keys())[:20]
            return token_cap(" ".join(str(k) for k in keys))

        if isinstance(data, list) and data and isinstance(data[0], dict):
            keys = list(data[0].keys())[:20]
            return token_cap(f"array {len(data)} items " + " ".join(str(k) for k in keys))

        return Path(file_path).stem
