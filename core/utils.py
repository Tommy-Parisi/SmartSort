def log_error(msg: str):
    print(f"\033[91m[ERROR] {msg}\033[0m")  # red color

def readable_size(kb: float) -> str:
    if kb < 1024:
        return f"{kb:.2f} KB"
    mb = kb / 1024
    return f"{mb:.2f} MB"