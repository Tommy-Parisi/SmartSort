import re

def log_error(msg: str):
    print(f"\033[91m[ERROR] {msg}\033[0m")

def readable_size(kb: float) -> str:
    return f"{kb:.2f} KB" if kb < 1024 else f"{kb / 1024:.2f} MB"

def normalize_text(text: str) -> str:
    if not text:
        return ""
    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Collapse whitespace and multiple newlines
    text = re.sub(r'\s+', ' ', text)
    return text.strip()
