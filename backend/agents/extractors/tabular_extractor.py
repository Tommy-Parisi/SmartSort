import csv
from pathlib import Path
from ...core.utils import token_cap
from ..identity_utils import clean_filename_stem


class TabularExtractorAgent:
    def extract(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        try:
            if ext == ".csv":
                return token_cap(self._extract_csv(file_path))
            elif ext in (".xlsx", ".xls"):
                return token_cap(self._extract_xlsx(file_path))
        except Exception:
            pass
        return clean_filename_stem(file_path)

    def _extract_csv(self, file_path: str) -> str:
        rows = []
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i >= 4:
                    break
                cleaned = ", ".join(str(v).strip() for v in row if str(v).strip())
                if cleaned:
                    rows.append(cleaned)
        return " | ".join(rows)

    def _extract_xlsx(self, file_path: str) -> str:
        rows = []
        try:
            import openpyxl
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= 4:
                    break
                cleaned = ", ".join(str(v).strip() for v in row if v is not None)
                if cleaned:
                    rows.append(cleaned)
            wb.close()
        except ImportError:
            import pandas as pd
            df = pd.read_excel(file_path, nrows=3)
            rows.append(", ".join(str(c) for c in df.columns))
            for _, row in df.iterrows():
                rows.append(", ".join(str(v) for v in row.values))
        return " | ".join(rows)
