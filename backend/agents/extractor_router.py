from ..core.models import FileMeta, FileContent
from ..core.utils import log_error, normalize_text
from .identity_utils import build_identity_text
from .extractors import (
    PDFExtractorAgent,
    DocxExtractorAgent,
    TextExtractorAgent,
    OCRExtractorAgent,
    CodeExtractorAgent,
    PptxExtractorAgent,
    TabularExtractorAgent,
    JSONExtractorAgent,
    FallbackExtractorAgent,
)


class ExtractorRouter:
    def __init__(self):
        _fallback = FallbackExtractorAgent()
        self.extractors = {
            "pdf": PDFExtractorAgent(),
            "docx": DocxExtractorAgent(),
            "text": TextExtractorAgent(),
            "image": OCRExtractorAgent(),
            "code": CodeExtractorAgent(),
            "presentation": PptxExtractorAgent(),
            "tabular": TabularExtractorAgent(),
            "data": JSONExtractorAgent(),
            "archive": _fallback,
            "video": _fallback,
        }
        self._fallback = _fallback

    def route(self, file_meta: FileMeta) -> FileContent:
        file_type = file_meta.detected_type
        extractor = self.extractors.get(file_type, self._fallback)

        try:
            raw_text = extractor.extract(file_meta.file_path)
            normalized = normalize_text(raw_text)
            identity = build_identity_text(file_meta.file_name, normalized)

            if not identity.strip():
                log_error(f"[ExtractorRouter] Empty output after extraction: {file_meta.file_name}")
                return FileContent(file_meta=file_meta, raw_text="", status="error")

            return FileContent(file_meta=file_meta, raw_text=identity, status="success")

        except Exception as e:
            log_error(f"[ExtractorRouter] Extraction failed for '{file_meta.file_name}': {e}")
            return FileContent(file_meta=file_meta, raw_text="", status="error")
