"""
Filesystem watcher for the SmartSort daemon.

Monitors configured folders with watchdog. On each new file:
  - Debounces for 2 s (writes often arrive in chunks)
  - Calls AssignmentAgent.assign()
  - If assigned: moves file to cluster folder, appends to move_log.jsonl
  - If unassigned: adds to unassigned_queue.json
  - When queue reaches recluster_queue_size: spawns background re-cluster
"""

from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from ..agents.index_manager import SMARTSORT_DIR

if TYPE_CHECKING:
    from ..agents.assignment_agent import AssignmentAgent

MOVE_LOG = SMARTSORT_DIR / "move_log.jsonl"
UNASSIGNED_QUEUE = SMARTSORT_DIR / "unassigned_queue.json"

DEBOUNCE_SECONDS = 2.0


# ── Filesystem helpers ────────────────────────────────────────────────────────

def _safe_dest(dest_dir: Path, filename: str) -> Path:
    """Return a non-colliding destination path by appending _1, _2, ..."""
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    i = 1
    while True:
        candidate = dest_dir / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _append_move_log(source: str, dest: str, cluster_id: int, similarity: float) -> None:
    SMARTSORT_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "destination": dest,
        "cluster_id": cluster_id,
        "similarity": round(similarity, 4),
    }
    with open(MOVE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _load_queue() -> list:
    try:
        with open(UNASSIGNED_QUEUE) as f:
            return json.load(f)
    except Exception:
        return []


def _save_queue(queue: list) -> None:
    SMARTSORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(UNASSIGNED_QUEUE, "w") as f:
        json.dump(queue, f, indent=2)


# ── Watchdog handler ──────────────────────────────────────────────────────────

class _Handler(FileSystemEventHandler):
    def __init__(self, agent: "AssignmentAgent", recluster_size: int):
        super().__init__()
        self.agent = agent
        self.recluster_size = recluster_size
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def on_created(self, event: FileCreatedEvent):
        if not event.is_directory:
            self._debounce(event.src_path)

    def on_moved(self, event: FileMovedEvent):
        if not event.is_directory:
            self._debounce(event.dest_path)

    def _debounce(self, path: str) -> None:
        with self._lock:
            existing = self._timers.pop(path, None)
            if existing:
                existing.cancel()
            t = threading.Timer(DEBOUNCE_SECONDS, self._process, args=[path])
            self._timers[path] = t
            t.start()

    def _process(self, file_path: str) -> None:
        with self._lock:
            self._timers.pop(file_path, None)

        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return

        try:
            result = self.agent.assign(file_path)
        except Exception as exc:
            print(f"[Watcher] Assignment error for {p.name}: {exc}")
            result = None

        if result and result.folder_path:
            dest_dir = Path(result.folder_path)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = _safe_dest(dest_dir, p.name)
            try:
                shutil.move(str(p), str(dest))
                _append_move_log(file_path, str(dest), result.cluster_id, result.similarity)
                print(
                    f"[Watcher] ✓ {p.name} → {dest_dir.name}/"
                    f"  (sim={result.similarity:.3f}, cluster={result.cluster_id},"
                    f" votes={result.neighbor_votes}/{self.agent.k})"
                )
            except Exception as exc:
                print(f"[Watcher] Move failed for {p.name}: {exc}")
        else:
            queue = _load_queue()
            if file_path not in queue:
                queue.append(file_path)
                _save_queue(queue)
            print(f"[Watcher] ⏳ {p.name} → unassigned queue ({len(queue)} pending)")
            if len(queue) >= self.recluster_size:
                self._trigger_recluster(queue)

    def _trigger_recluster(self, queue: list) -> None:
        print(f"[Watcher] Queue full ({len(queue)}) — triggering background re-cluster")
        t = threading.Thread(target=self._run_recluster, args=[list(queue)], daemon=True)
        t.start()

    def _run_recluster(self, queue: list) -> None:
        """
        Placeholder for full re-cluster.
        Phase 3 will replace this with a proper call into TauriPipeline /
        a headless pipeline run that rebuilds the faiss index and clears the queue.
        """
        print(f"[Watcher] Re-cluster triggered for {len(queue)} unassigned files.")
        print("[Watcher] Full re-cluster not yet implemented — clear queue manually.")
        _save_queue([])


# ── Public watcher class ──────────────────────────────────────────────────────

class SmartSortWatcher:
    def __init__(self, config: dict, agent: "AssignmentAgent"):
        self._config = config
        self._agent = agent
        self._observer = Observer()
        self._handler = _Handler(
            agent=agent,
            recluster_size=config.get("recluster_queue_size", 20),
        )

    def start(self) -> None:
        folders = self._config.get("watched_folders", [])
        if not folders:
            print("[Watcher] No watched_folders in config — nothing to watch.")
            return

        for folder in folders:
            p = Path(folder)
            if p.exists() and p.is_dir():
                self._observer.schedule(self._handler, str(p), recursive=False)
                print(f"[Watcher] Watching: {p}")
            else:
                print(f"[Watcher] Skipped (not found): {folder}")

        self._observer.start()
        print("[Watcher] Observer started.")

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()
        print("[Watcher] Observer stopped.")
