import re
from pathlib import Path

FILENAME_NOISE = [
    " - Google Docs", " - Google Sheets", " - Google Slides",
    " - Google Drive", " - Microsoft Word", " - OneDrive", " - Dropbox",
    "_final", "_v2", "_v3", "_draft", "_copy",
    " copy", " (1)", " (2)", " (3)",
    " final", " draft", " FINAL", " DRAFT", "- Copy",
]

DOCTYPE_HINTS = {
    "resume": ["resume", "cv", "curriculum vitae", "work experience", "skills summary"],
    "cover letter": ["cover letter", "covering letter", "dear hiring", "dear recruiter"],
    "lecture": ["lecture", "week ", "class notes", "course notes", "slides"],
    "assignment": ["assignment", "homework", "problem set", "ps1", "ps2", "ps3",
                   "ps4", "ps5", "lab report", "submission"],
    "cheat sheet": ["cheat sheet", "reference sheet", "quick reference", "formula sheet"],
    "report": ["report", "assessment", "reflection", "analysis", "evaluation"],
    "agreement": ["agreement", "contract", "terms of service", "terms and conditions",
                  "policy", "health plan", "user agreement", "waiver"],
    "research": ["research paper", "thesis", "dissertation", "literature review",
                 "abstract", "methodology", "hypothesis"],
    "invoice": ["invoice", "receipt", "billing", "payment", "order confirmation"],
    "notes": ["notes", "summary", "overview", "key points", "takeaways"],
}


def clean_filename(stem: str) -> str:
    cleaned = stem
    for noise in FILENAME_NOISE:
        cleaned = cleaned.replace(noise, "").replace(noise.lower(), "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or stem.strip()


def clean_filename_stem(file_path: str) -> str:
    return clean_filename(Path(file_path).stem)


def infer_doctype(filename: str, content: str) -> str | None:
    combined = (filename + " " + content[:300]).lower()
    for doctype, hints in DOCTYPE_HINTS.items():
        if any(h in combined for h in hints):
            return doctype
    return None


def extract_prefixed_doctype(identity_text: str) -> str | None:
    if ":" not in identity_text:
        return None
    prefix = identity_text.split(":", 1)[0].strip().lower()
    if prefix in DOCTYPE_HINTS:
        return prefix
    return None


def build_identity_text(file_name: str, extracted_text: str) -> str:
    stem = clean_filename(Path(file_name).stem)
    body = extracted_text.strip()

    if not body:
        return stem

    if body.lower() == Path(file_name).stem.lower():
        body = stem

    doctype = infer_doctype(stem, body)
    return f"{doctype}: {body}" if doctype else body
