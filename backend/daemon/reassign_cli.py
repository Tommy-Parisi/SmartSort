"""
CLI entry point: reassign files to remaining clusters after a folder is deleted.

Usage:
    python -m backend.daemon.reassign_cli \
        --files-json '["path/to/a.pdf", "path/to/b.docx"]' \
        --exclude 42

Returns a JSON array to stdout:
    [{"filename": "a.pdf", "cluster_id": 7, "folder_name": "/Users/.../Work"},
     {"filename": "b.docx", "cluster_id": -1, "folder_name": ""}]

cluster_id -1 means below-threshold (file should go to unsorted).
"""

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--files-json', required=True,
                        help='JSON array of absolute file paths')
    parser.add_argument('--exclude', type=int, required=True,
                        help='Cluster ID to exclude from candidates')
    args = parser.parse_args()

    try:
        file_paths: list[str] = json.loads(args.files_json)
    except json.JSONDecodeError as e:
        print(f"[reassign_cli] Bad --files-json: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        from backend.agents.assignment_agent import AssignmentAgent
        agent = AssignmentAgent()
    except Exception as e:
        # Index not loaded or model unavailable — all files become unsorted
        print(f"[reassign_cli] Could not load AssignmentAgent: {e}", file=sys.stderr)
        results = [
            {"filename": Path(p).name, "cluster_id": -1, "folder_name": ""}
            for p in file_paths
        ]
        print(json.dumps(results))
        return

    results = []
    for filepath in file_paths:
        filename = Path(filepath).name
        try:
            result = agent.assign(filepath)
            if result is None or result.cluster_id == args.exclude:
                results.append({"filename": filename, "cluster_id": -1, "folder_name": ""})
            else:
                results.append({
                    "filename": filename,
                    "cluster_id": result.cluster_id,
                    "folder_name": result.folder_path,
                })
        except Exception as e:
            print(f"[reassign_cli] Failed to assign {filename}: {e}", file=sys.stderr)
            results.append({"filename": filename, "cluster_id": -1, "folder_name": ""})

    print(json.dumps(results))


if __name__ == '__main__':
    main()
