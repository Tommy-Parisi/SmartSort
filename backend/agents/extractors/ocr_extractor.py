import pytesseract
from PIL import Image

class OCRExtractorAgent:
    def extract(self, file_path: str) -> str:
        return pytesseract.image_to_string(Image.open(file_path))