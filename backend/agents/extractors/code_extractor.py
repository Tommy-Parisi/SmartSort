import ast
import re
from pathlib import Path
from ...core.utils import token_cap

_TOP_COMMENT_RE = re.compile(r'^\s*(?://|#|\*)\s*(.+)')
_FUNC_CLASS_RE = re.compile(
    r'^\s*(?:export\s+)?(?:async\s+)?(?:function|class|def|fn|pub\s+fn|public|private|static)\s+(\w+)',
    re.MULTILINE
)
_SQL_COMMENT_RE = re.compile(r'^\s*--\s*(.+)', re.MULTILINE)
_SQL_OBJ_RE = re.compile(
    r'(?:CREATE|ALTER|DROP)\s+(?:OR\s+REPLACE\s+)?'
    r'(?:TABLE|VIEW|PROCEDURE|FUNCTION|TRIGGER|INDEX)\s+'
    r'(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(\w+)[`"\]]?',
    re.IGNORECASE,
)
_SQL_EXTS = {".sql"}


def _extract_python(source: str, stem: str) -> str:
    parts = []
    try:
        tree = ast.parse(source)
        if (tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.s, str)):
            first_line = tree.body[0].value.s.split('\n')[0].strip()
            if first_line:
                parts.append(first_line)

        names = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(node.name)
        if names:
            parts.append(" ".join(names[:25]))
    except SyntaxError:
        for line in source.splitlines()[:20]:
            m = re.match(r'^#\s*(.+)', line)
            if m:
                parts.append(m.group(1).strip())

    return " ".join(parts) if parts else stem


def _extract_sql(source: str, stem: str) -> str:
    parts = []
    # Leading -- comments (first 15 lines)
    for line in source.splitlines()[:15]:
        m = _SQL_COMMENT_RE.match(line)
        if m:
            parts.append(m.group(1).strip())
        elif line.strip() and not parts:
            break

    # Table / view / function / procedure names
    names = _SQL_OBJ_RE.findall(source)
    if names:
        parts.append(" ".join(names[:20]))

    return " ".join(parts) if parts else stem


def _extract_generic(source: str, stem: str) -> str:
    parts = []
    for line in source.splitlines()[:15]:
        m = _TOP_COMMENT_RE.match(line)
        if m:
            parts.append(m.group(1).strip())
        elif line.strip() and not parts:
            break

    names = _FUNC_CLASS_RE.findall(source)
    if names:
        parts.append(" ".join(names[:25]))

    return " ".join(parts) if parts else stem


class CodeExtractorAgent:
    def extract(self, file_path: str) -> str:
        stem = Path(file_path).stem
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                source = f.read(16384)
        except Exception:
            return stem

        ext = Path(file_path).suffix.lower()
        if ext == ".py":
            result = _extract_python(source, stem)
        elif ext in _SQL_EXTS:
            result = _extract_sql(source, stem)
        else:
            result = _extract_generic(source, stem)

        return token_cap(result or stem)
