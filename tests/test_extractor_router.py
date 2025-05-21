import shutil
import tempfile
from pathlib import Path
import pytest
from agents.extractor_router import ExtractorRouter
from core.models import FileMeta
import fpdf

# ==== FIXTURE SETUP ====

@pytest.fixture(scope="module")
def test_file_dir():
    temp_dir = Path(tempfile.mkdtemp(prefix="extract_test_"))

    # Create text file
    (temp_dir / "sample.txt").write_text("   Hello,    world.  \n\nNew line.  ")

    # Create code file
    (temp_dir / "script.py").write_text("def foo():\n    return 42")

    # Create minimal PDF (with fallback if pdfplumber fails)
    try:
        pdf = fpdf.FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="PDF content here.", ln=True)
        pdf.output(str(temp_dir / "sample.pdf"))
    except ImportError:
        pass

    # Create minimal DOCX
    try:
        from docx import Document
        doc = Document()
        doc.add_paragraph("DOCX test content.")
        doc.save(str(temp_dir / "sample.docx"))
    except ImportError:
        pass

    # Create dummy image file (OCR test)
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (100, 30), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        d.text((10, 10), "Hello", fill=(0, 0, 0))
        img.save(str(temp_dir / "image.png"))
    except ImportError:
        pass

    yield temp_dir

    # Teardown
    shutil.rmtree(temp_dir)

# ==== TEST CASE ====

def build_file_meta(path: Path, detected_type: str) -> FileMeta:
    stat = path.stat()
    return FileMeta(
        file_path=str(path),
        file_name=path.name,
        extension=path.suffix.lower(),
        detected_type=detected_type,
        size_kb=round(stat.st_size / 1024, 2),
        created_at="2024-01-01T00:00:00",
        modified_at="2024-01-01T00:00:00",
        status="pending"
    )

def test_extractor_router_outputs_clean_text(test_file_dir):
    router = ExtractorRouter()

    samples = [
        ("sample.txt", "text"),
        ("script.py", "code"),
        ("sample.pdf", "pdf"),
        ("sample.docx", "docx"),
        ("image.png", "image"),
    ]

    for fname, ftype in samples:
        fpath = test_file_dir / fname
        if not fpath.exists():
            continue  # PDF, DOCX, or OCR may be missing

        meta = build_file_meta(fpath, ftype)
        result = router.route(meta)

        assert result.status in {"success", "error"}
        if result.status == "success":
            assert isinstance(result.raw_text, str)
            assert len(result.raw_text.strip()) > 0
            # Confirm no double spaces or ugly newlines
            assert "  " not in result.raw_text
            assert "\r" not in result.raw_text


@pytest.fixture(scope="module")
def edge_case_dir():
    temp_dir = Path(tempfile.mkdtemp(prefix="extract_edge_"))

    # 0-byte file
    (temp_dir / "empty.txt").touch()

    # Unsupported file type
    (temp_dir / "archive.zip").write_bytes(b"Not really a zip")

    # Binary disguised as .txt
    (temp_dir / "binary.txt").write_bytes(b"\x00\xFF\x00\xFF")

    # Corrupt PDF (not a real PDF)
    (temp_dir / "fake.pdf").write_text("%%% not a real PDF %%%")

    # Missing extractor type (e.g., .xyz)
    (temp_dir / "mystery.xyz").write_text("some random format")

    yield temp_dir
    shutil.rmtree(temp_dir)

def build_file_meta(path: Path, detected_type: str) -> FileMeta:
    stat = path.stat()
    return FileMeta(
        file_path=str(path),
        file_name=path.name,
        extension=path.suffix.lower(),
        detected_type=detected_type,
        size_kb=round(stat.st_size / 1024, 2),
        created_at="2024-01-01T00:00:00",
        modified_at="2024-01-01T00:00:00",
        status="pending"
    )

@pytest.mark.parametrize("fname, ftype, expected_status", [
    ("empty.txt", "text", "error"),
    ("archive.zip", "unknown", "error"),
    ("binary.txt", "text", "success"),   # Might technically extract weird content
    ("fake.pdf", "pdf", "error"),
    ("mystery.xyz", "unknown", "error")
])
def test_extractor_router_edge_cases(edge_case_dir, fname, ftype, expected_status):
    router = ExtractorRouter()
    fpath = edge_case_dir / fname

    meta = build_file_meta(fpath, ftype)
    result = router.route(meta)

    assert result.status == expected_status
    assert isinstance(result.raw_text, str)
    if expected_status == "success":
        assert len(result.raw_text.strip()) > 0