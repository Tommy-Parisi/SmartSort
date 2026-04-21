import re
from pathlib import Path
from ...core.utils import token_cap

_HEADING_RE = re.compile(r'^[A-Z0-9].{0,70}$')


def _is_heading(line: str) -> bool:
    return bool(_HEADING_RE.match(line)) and not line.endswith((',', ';'))


class PDFExtractorAgent:
    def extract(self, file_path: str) -> str:
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                raw = ""
                for page in pdf.pages[:3]:
                    t = page.extract_text() or ""
                    if t.strip():
                        raw = t
                        break
        except Exception:
            return Path(file_path).stem

        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        if not lines:
            return Path(file_path).stem

        parts = [lines[0]]  # title = first non-empty line
        headings_seen = 0
        first_para_seen = False

        for line in lines[1:]:
            if headings_seen >= 4 and first_para_seen:
                break
            if _is_heading(line) and len(line) < 80 and headings_seen < 4:
                parts.append(line)
                headings_seen += 1
            elif len(line) > 60 and not first_para_seen:
                parts.append(line)
                first_para_seen = True

        return token_cap(" ".join(parts))
