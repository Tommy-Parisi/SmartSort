import os
import shutil
from pathlib import Path
import pytest

from agents.ingestion_manager import IngestionManager
from core.models import FileMeta

TEST_DIR = Path("tests/temp_test_files")

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_test_dir():
    
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    (TEST_DIR / "example.pdf").write_text("This is a PDF file.")
    (TEST_DIR / "notes.txt").write_text("Some notes here.")
    (TEST_DIR / "temp.tmp").write_text("Should be ignored.")
    (TEST_DIR / ".DS_Store").write_text("Ignored system file.")

    yield  

    shutil.rmtree(TEST_DIR)

def test_ingestion_manager_valid_files():
    manager = IngestionManager(str(TEST_DIR))
    manager.scan()
    
    files = manager.file_meta_queue

    assert isinstance(files, list)
    assert all(isinstance(f, FileMeta) for f in files)

    file_names = [f.file_name for f in files]
    assert "example.pdf" in file_names
    assert "notes.txt" in file_names
    assert "temp.tmp" not in file_names
    assert ".DS_Store" not in file_names

def test_ingestion_manager_metadata_fields():
    manager = IngestionManager(str(TEST_DIR))
    manager.scan()
    file = next((f for f in manager.file_meta_queue if f.file_name == "example.pdf"), None)
    
    assert file is not None
    assert file.extension == ".pdf"
    assert file.detected_type == "pdf"
    assert file.status == "pending"
    assert isinstance(file.size_kb, float)
    assert file.created_at and file.modified_at

def test_invalid_root_folder_logs_error(capsys):
    bad_manager = IngestionManager("non_existent_dir")
    bad_manager.scan()

    captured = capsys.readouterr()
    assert "does not exist or is not a directory" in captured.out

def test_ingestion_ignores_hidden_and_zero_byte_files():
    hidden_file = TEST_DIR / ".hidden.txt"
    zero_file = TEST_DIR / "zero.txt"

    hidden_file.write_text("I'm hidden")
    zero_file.touch()

    manager = IngestionManager(str(TEST_DIR))
    manager.scan()
    files = manager.file_meta_queue

    file_names = [f.file_name for f in files]
    assert ".hidden.txt" not in file_names
    assert "zero.txt" in file_names  # Still valid, just small

def test_ingestion_detects_uppercase_and_unknown_extensions():
    upper_pdf = TEST_DIR / "UPPER.PDF"
    unknown_file = TEST_DIR / "data.weird"

    upper_pdf.write_text("Uppercase test")
    unknown_file.write_text("Who am I?")

    manager = IngestionManager(str(TEST_DIR))
    manager.scan()
    files = manager.file_meta_queue

    upper = next((f for f in files if f.file_name == "UPPER.PDF"), None)
    weird = next((f for f in files if f.file_name == "data.weird"), None)

    assert upper is not None and upper.detected_type == "pdf"
    assert weird is not None and weird.detected_type == "unknown"

def test_ingestion_skips_symlinks(tmp_path):
    real_file = tmp_path / "real.txt"
    real_file.write_text("Hello world")
    symlink = TEST_DIR / "link.txt"

    os.symlink(real_file, symlink)

    manager = IngestionManager(str(TEST_DIR))
    manager.scan()
    files = manager.file_meta_queue

    file_names = [f.file_name for f in files]
    assert "link.txt" not in file_names

