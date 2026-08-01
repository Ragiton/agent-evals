#!/usr/bin/env python3
"""Approve or reject a matrix cell.

Usage:
    python harness/update_matrix.py approve <cell_id>
    python harness/update_matrix.py reject <cell_id>
    python harness/update_matrix.py add --spec led-blinky-minimal --agent claude-code --model claude-sonnet-4-6 [--condition baseline]
    python harness/update_matrix.py list
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
MATRIX_PATH = PROJECT_ROOT / "results" / "eval_matrix.json"


def load() -> dict:
    return json.loads(MATRIX_PATH.read_text())


def save(matrix: dict) -> None:
    matrix["updated_at"] = datetime.now(timezone.utc).isoformat()
    MATRIX_PATH.write_text(json.dumps(matrix, indent=2))


def find_cell(matrix: dict, cell_id: str) -> dict | None:
    for cell in matrix["cells"]:
        if cell.get("id") == cell_id:
            return cell
    return None


def cmd_approve(cell_id: str) -> None:
    matrix = load()
    cell = find_cell(matrix, cell_id)
    if not cell:
        sys.exit(f"cell not found: {cell_id}")
    cell["approved"] = True
    save(matrix)
    print(f"approved {cell_id}")


def cmd_reject(cell_id: str) -> None:
    matrix = load()
    cell = find_cell(matrix, cell_id)
    if not cell:
        sys.exit(f"cell not found: {cell_id}")
    cell["approved"] = False
    save(matrix)
    print(f"rejected {cell_id}")


def cmd_add(spec: str, agent: str, model: str, condition: str) -> None:
    matrix = load()
    cell_id = f"{spec}__{agent}__{model}".replace("/", "_")
    if find_cell(matrix, cell_id):
        sys.exit(f"cell already exists: {cell_id}")
    matrix["cells"].append({
        "id": cell_id,
        "spec_id": spec,
        "agent": agent,
        "model": model,
        "condition": condition,
        "approved": False,
        "notes": "",
    })
    save(matrix)
    print(f"added {cell_id}")


def cmd_list() -> None:
    matrix = load()
    for cell in matrix["cells"]:
        flag = "✓" if cell.get("approved") else "·"
        print(f"  {flag} {cell['id']:60s} notes={cell.get('notes','')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("approve")
    p.add_argument("cell_id")
    p = sub.add_parser("reject")
    p.add_argument("cell_id")
    p = sub.add_parser("add")
    p.add_argument("--spec", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--condition", default="baseline")
    sub.add_parser("list")
    args = ap.parse_args()

    if args.cmd == "approve":
        cmd_approve(args.cell_id)
    elif args.cmd == "reject":
        cmd_reject(args.cell_id)
    elif args.cmd == "add":
        cmd_add(args.spec, args.agent, args.model, args.condition)
    elif args.cmd == "list":
        cmd_list()


if __name__ == "__main__":
    main()