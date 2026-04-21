"""
Tests for SmartSortWatcher and the file-move helpers.

Uses a real temp directory + a mock AssignmentAgent so watchdog events
can be triggered without needing a sentence-transformer model.
"""

import json
import shutil
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.agents.assignment_agent import AssignmentResult
from backend.daemon.watcher import (
    SmartSortWatcher,
    _safe_dest,
    _append_move_log,
    _load_queue,
    _save_queue,
    MOVE_LOG,
    UNASSIGNED_QUEUE,
    SMARTSORT_DIR,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def watched_dir():
    d = Path(tempfile.mkdtemp(prefix="watch_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def cluster_dir():
    d = Path(tempfile.mkdtemp(prefix="cluster_test_"))
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def patch_smartsort_dir(tmp_path, monkeypatch):
    """Redirect ~/.smartsort writes to a temp dir for every test."""
    monkeypatch.setattr("backend.daemon.watcher.SMARTSORT_DIR", tmp_path)
    monkeypatch.setattr("backend.daemon.watcher.MOVE_LOG", tmp_path / "move_log.jsonl")
    monkeypatch.setattr("backend.daemon.watcher.UNASSIGNED_QUEUE", tmp_path / "unassigned_queue.json")
    yield tmp_path


# ── _safe_dest tests ──────────────────────────────────────────────────────────

def test_safe_dest_no_collision(tmp_path):
    dest = _safe_dest(tmp_path, "report.pdf")
    assert dest == tmp_path / "report.pdf"


def test_safe_dest_increments_on_collision(tmp_path):
    (tmp_path / "report.pdf").touch()
    dest = _safe_dest(tmp_path, "report.pdf")
    assert dest == tmp_path / "report_1.pdf"


def test_safe_dest_increments_past_existing(tmp_path):
    (tmp_path / "report.pdf").touch()
    (tmp_path / "report_1.pdf").touch()
    dest = _safe_dest(tmp_path, "report.pdf")
    assert dest == tmp_path / "report_2.pdf"


# ── move log tests ────────────────────────────────────────────────────────────

def test_append_move_log_creates_jsonl(tmp_path, monkeypatch):
    log_path = tmp_path / "move_log.jsonl"
    monkeypatch.setattr("backend.daemon.watcher.MOVE_LOG", log_path)
    monkeypatch.setattr("backend.daemon.watcher.SMARTSORT_DIR", tmp_path)

    _append_move_log("/src/a.pdf", "/dst/cluster/a.pdf", cluster_id=2, similarity=0.81)
    assert log_path.exists()

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["cluster_id"] == 2
    assert entry["similarity"] == 0.81
    assert entry["source"] == "/src/a.pdf"


def test_append_move_log_appends(tmp_path, monkeypatch):
    log_path = tmp_path / "move_log.jsonl"
    monkeypatch.setattr("backend.daemon.watcher.MOVE_LOG", log_path)
    monkeypatch.setattr("backend.daemon.watcher.SMARTSORT_DIR", tmp_path)

    _append_move_log("/a.pdf", "/c/a.pdf", 0, 0.7)
    _append_move_log("/b.pdf", "/c/b.pdf", 1, 0.8)
    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 2


# ── queue tests ───────────────────────────────────────────────────────────────

def test_save_and_load_queue(tmp_path, monkeypatch):
    q_path = tmp_path / "unassigned_queue.json"
    monkeypatch.setattr("backend.daemon.watcher.UNASSIGNED_QUEUE", q_path)
    monkeypatch.setattr("backend.daemon.watcher.SMARTSORT_DIR", tmp_path)

    _save_queue(["/file1.pdf", "/file2.txt"])
    q = _load_queue()
    assert q == ["/file1.pdf", "/file2.txt"]


def test_load_queue_returns_empty_when_missing(tmp_path, monkeypatch):
    q_path = tmp_path / "nonexistent_queue.json"
    monkeypatch.setattr("backend.daemon.watcher.UNASSIGNED_QUEUE", q_path)
    assert _load_queue() == []


# ── SmartSortWatcher integration tests ───────────────────────────────────────

def _make_agent(result: AssignmentResult | None) -> MagicMock:
    agent = MagicMock()
    agent.assign.return_value = result
    agent.k = 5
    return agent


def test_watcher_moves_file_when_assigned(watched_dir, cluster_dir, tmp_path, monkeypatch):
    """File created in watched folder should be moved to the cluster folder."""
    monkeypatch.setattr("backend.daemon.watcher.SMARTSORT_DIR", tmp_path)
    monkeypatch.setattr("backend.daemon.watcher.MOVE_LOG", tmp_path / "move_log.jsonl")
    monkeypatch.setattr("backend.daemon.watcher.UNASSIGNED_QUEUE", tmp_path / "unassigned_queue.json")

    assignment = AssignmentResult(
        cluster_id=0,
        folder_path=str(cluster_dir),
        similarity=0.82,
        neighbor_votes=4,
    )
    agent = _make_agent(assignment)

    config = {"watched_folders": [str(watched_dir)], "recluster_queue_size": 20}
    watcher = SmartSortWatcher(config=config, agent=agent)
    watcher.start()

    test_file = watched_dir / "invoice.pdf"
    test_file.write_text("invoice content")

    # Wait for debounce + processing (2 s debounce + slack)
    time.sleep(3.0)
    watcher.stop()

    assert not test_file.exists(), "Source file should have been moved"
    moved = list(cluster_dir.glob("invoice*.pdf"))
    assert len(moved) == 1, f"Expected 1 moved file, found: {moved}"

    log_path = tmp_path / "move_log.jsonl"
    assert log_path.exists()
    entry = json.loads(log_path.read_text().strip())
    assert entry["cluster_id"] == 0


def test_watcher_queues_file_when_unassigned(watched_dir, tmp_path, monkeypatch):
    """File that can't be assigned should land in the unassigned queue."""
    monkeypatch.setattr("backend.daemon.watcher.SMARTSORT_DIR", tmp_path)
    monkeypatch.setattr("backend.daemon.watcher.MOVE_LOG", tmp_path / "move_log.jsonl")
    monkeypatch.setattr("backend.daemon.watcher.UNASSIGNED_QUEUE", tmp_path / "unassigned_queue.json")

    agent = _make_agent(None)

    config = {"watched_folders": [str(watched_dir)], "recluster_queue_size": 20}
    watcher = SmartSortWatcher(config=config, agent=agent)
    watcher.start()

    test_file = watched_dir / "mystery.txt"
    test_file.write_text("unknown content")

    time.sleep(3.0)
    watcher.stop()

    queue = [str(Path(p).resolve()) for p in _load_queue()]
    assert str(test_file.resolve()) in queue


def test_watcher_no_overwrite_on_collision(watched_dir, cluster_dir, tmp_path, monkeypatch):
    """If destination already exists the file should be renamed, not overwritten."""
    monkeypatch.setattr("backend.daemon.watcher.SMARTSORT_DIR", tmp_path)
    monkeypatch.setattr("backend.daemon.watcher.MOVE_LOG", tmp_path / "move_log.jsonl")
    monkeypatch.setattr("backend.daemon.watcher.UNASSIGNED_QUEUE", tmp_path / "unassigned_queue.json")

    # Pre-existing file at destination
    existing = cluster_dir / "report.txt"
    existing.write_text("existing content")

    assignment = AssignmentResult(
        cluster_id=0,
        folder_path=str(cluster_dir),
        similarity=0.75,
        neighbor_votes=3,
    )
    agent = _make_agent(assignment)

    config = {"watched_folders": [str(watched_dir)], "recluster_queue_size": 20}
    watcher = SmartSortWatcher(config=config, agent=agent)
    watcher.start()

    new_file = watched_dir / "report.txt"
    new_file.write_text("new content")

    time.sleep(3.0)
    watcher.stop()

    # Original must be untouched
    assert existing.read_text() == "existing content"
    # Renamed copy must exist
    renamed = cluster_dir / "report_1.txt"
    assert renamed.exists(), "Expected renamed file report_1.txt"
    assert renamed.read_text() == "new content"
