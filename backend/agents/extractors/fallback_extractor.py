from ..identity_utils import clean_filename_stem


class FallbackExtractorAgent:
    def extract(self, file_path: str) -> str:
        return clean_filename_stem(file_path)
