"""
SmartSort daemon entry point.

Usage:
    python -m backend.daemon.daemon_runner

Lifecycle:
  1. Ensure ~/.smartsort/config.json exists (writes defaults if missing)
  2. Write PID to ~/.smartsort/daemon.pid
  3. Load AssignmentAgent (sentence-transformer model enters memory here)
  4. Start SmartSortWatcher on configured folders
  5. Block; handle SIGTERM / SIGINT for graceful shutdown
  6. Remove daemon.pid on exit

Tauri can check daemon status by:
  - Reading daemon.pid and calling kill(pid, 0) to see if the process is alive
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

# Allow running as  python -m backend.daemon.daemon_runner  from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.agents.index_manager import SMARTSORT_DIR

CONFIG_FILE = SMARTSORT_DIR / "config.json"
PID_FILE = SMARTSORT_DIR / "daemon.pid"

_DEFAULT_CONFIG: dict = {
    "watched_folders": [],
    "similarity_threshold": 0.65,
    "recluster_queue_size": 20,
    "recluster_interval_days": 7,
}


# ── Config helpers ────────────────────────────────────────────────────────────

def _ensure_config() -> dict:
    SMARTSORT_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                on_disk = json.load(f)
            return {**_DEFAULT_CONFIG, **on_disk}
        except Exception:
            pass
    with open(CONFIG_FILE, "w") as f:
        json.dump(_DEFAULT_CONFIG, f, indent=2)
    print(f"[Daemon] Created default config at {CONFIG_FILE}")
    return _DEFAULT_CONFIG.copy()


def _write_pid() -> None:
    SMARTSORT_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _clear_pid() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


# ── Entry point ───────────────────────────────────────────────────────────────

def run() -> None:
    from backend.agents.assignment_agent import AssignmentAgent
    from backend.daemon.watcher import SmartSortWatcher
    from backend.daemon.model_server import ModelServer

    config = _ensure_config()
    _write_pid()
    print(f"[Daemon] PID {os.getpid()} — SmartSort daemon starting")

    if not config.get("watched_folders"):
        print(
            f"[Daemon] No watched_folders configured.\n"
            f"         Edit {CONFIG_FILE} and restart."
        )

    # Start model server first so the pipeline subprocess can share it.
    # EmbeddingAgent will detect the server via /health and skip loading locally.
    model_server = ModelServer()
    model_server.start()

    agent = AssignmentAgent(threshold=config.get("similarity_threshold", 0.65))
    watcher = SmartSortWatcher(config=config, agent=agent)
    watcher.start()

    def _shutdown(signum: int, _frame) -> None:
        print(f"\n[Daemon] Signal {signum} received — shutting down")
        watcher.stop()
        model_server.stop()
        _clear_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    print("[Daemon] Running. Send SIGTERM or Ctrl-C to stop.")
    while True:
        time.sleep(1)


if __name__ == "__main__":
    run()
