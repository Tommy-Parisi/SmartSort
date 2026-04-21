from pathlib import Path


class FallbackExtractorAgent:
    def extract(self, file_path: str) -> str:
        return Path(file_path).stem
