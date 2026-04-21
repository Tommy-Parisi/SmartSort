from pathlib import Path
from ...core.utils import token_cap


def _slide_title(slide) -> str:
    """Return the title placeholder text, or first non-empty text on the slide."""
    try:
        for shape in slide.placeholders:
            if shape.placeholder_format.idx == 0:  # 0 = title
                t = shape.text.strip()
                if t:
                    return t
    except Exception:
        pass
    for shape in slide.shapes:
        if hasattr(shape, "text") and shape.text.strip():
            return shape.text.strip().split("\n")[0]
    return ""


class PptxExtractorAgent:
    def extract(self, file_path: str) -> str:
        try:
            from pptx import Presentation
        except ImportError:
            return Path(file_path).stem

        try:
            prs = Presentation(file_path)
        except Exception:
            return Path(file_path).stem

        titles = []
        for slide in prs.slides:
            t = _slide_title(slide)
            if t:
                titles.append(t)

        return token_cap(" ".join(titles)) if titles else Path(file_path).stem
