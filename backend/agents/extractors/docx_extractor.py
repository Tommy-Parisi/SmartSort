from pathlib import Path
from ...core.utils import token_cap

_HEADING_STYLES = {"heading 1", "heading 2", "heading 3", "title"}


class DocxExtractorAgent:
    def extract(self, file_path: str) -> str:
        try:
            from docx import Document
            doc = Document(file_path)
        except Exception:
            return Path(file_path).stem

        parts = []
        headings_seen = 0
        first_body_seen = False

        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style_name = (para.style.name or "").lower() if para.style else ""
            is_heading = any(h in style_name for h in _HEADING_STYLES)

            if is_heading and headings_seen < 5:
                parts.append(text)
                headings_seen += 1
            elif not is_heading and not first_body_seen and len(text) > 30:
                parts.append(text)
                first_body_seen = True

            if headings_seen >= 5 and first_body_seen:
                break

        if not parts:
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    parts.append(text)
                    break

        return token_cap(" ".join(parts)) if parts else Path(file_path).stem
