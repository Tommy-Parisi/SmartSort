import re
from pathlib import Path
from ...core.utils import token_cap
from ..identity_utils import clean_filename_stem

_MD_HEADING_RE = re.compile(r'^#{1,6}\s+(.+)')


class TextExtractorAgent:
    def extract(self, file_path: str) -> str:
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read(8192)
        except Exception:
            return clean_filename_stem(file_path)

        ext = Path(file_path).suffix.lower()
        if ext in (".md", ".markdown", ".rst"):
            return token_cap(self._extract_md(content))
        return token_cap(self._extract_txt(content))

    def _extract_md(self, content: str) -> str:
        parts = []
        headings_seen = 0
        first_para_seen = False
        for line in content.splitlines():
            stripped = line.strip()
            m = _MD_HEADING_RE.match(stripped)
            if m and headings_seen < 5:
                parts.append(m.group(1).strip())
                headings_seen += 1
            elif stripped and not stripped.startswith('#') and not first_para_seen and len(stripped) > 20:
                parts.append(stripped)
                first_para_seen = True
            if headings_seen >= 5 and first_para_seen:
                break
        return " ".join(parts) if parts else content[:300]

    def _extract_txt(self, content: str) -> str:
        paragraphs = re.split(r'\n\s*\n', content.strip())
        if paragraphs:
            return paragraphs[0].replace('\n', ' ').strip()
        return content[:300]
