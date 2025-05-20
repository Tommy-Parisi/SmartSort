class TextExtractorAgent:
    def extract(self, file_path: str) -> str:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            return f.read()