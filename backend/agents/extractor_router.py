from core.models import FileMeta, FileContent
from core.utils import log_error, normalize_text
from agents.extractors import (
    PDFExtractorAgent,
    DocxExtractorAgent,
    TextExtractorAgent,
    OCRExtractorAgent,
    CodeExtractorAgent,
)

class ExtractorRouter:
    def __init__(self):
        self.extractors = {
            "pdf": PDFExtractorAgent(),
            "docx": DocxExtractorAgent(),
            "text": TextExtractorAgent(),
            "image": OCRExtractorAgent(),
            "code": CodeExtractorAgent(),
        }

    def route(self, file_meta: FileMeta) -> FileContent:
        file_type = file_meta.detected_type
        extractor = self.extractors.get(file_type)

        if extractor is None:
            log_error(f"[ExtractorRouter] No extractor found for type '{file_type}' ({file_meta.file_name})")
            return FileContent(file_meta=file_meta, raw_text="", status="error")

        try:
            raw_text = extractor.extract(file_meta.file_path)
            normalized = normalize_text(raw_text)

            if not normalized.strip():
                log_error(f"[ExtractorRouter] Empty output after extraction: {file_meta.file_name}")
                return FileContent(file_meta=file_meta, raw_text="", status="error")

            return FileContent(file_meta=file_meta, raw_text=normalized, status="success")

        except Exception as e:
            log_error(f"[ExtractorRouter] Extraction failed for '{file_meta.file_name}': {e}")
            return FileContent(file_meta=file_meta, raw_text="", status="error")