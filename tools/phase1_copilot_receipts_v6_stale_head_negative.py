#!/usr/bin/env python3
"""Assert that the unmodified seven-receipt validator rejects a newer PR8 head.

This is a CURRENT-HEAD negative control, not historical approval or a v7 pass.
The separate v6 historical replay proves the seven-receipt success at its
immutable original head; the v7 live job validates the current eight receipts.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import phase1_copilot_receipts_v6_adapter as v6

STALE_BLOCKER = "Pull request head differs from exact validation head"


def verify_stale_head_rejection(returncode: int, stdout: str) -> int:
    """Require seven distinct exact stale-head rejections and exit code two."""
    if returncode != 2:
        raise ValueError("The unchanged v6 validator did not fail closed with exit code 2")
    try:
        rows = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    except json.JSONDecodeError as exc:
        raise ValueError("The v6 validator emitted non-JSON evidence") from exc
    expected = {f"{repo}:{path}" for repo, path in v6.EXPECTED_ORDER}
    if len(expected) != 7 or len(rows) != 7:
        raise ValueError("Expected exactly seven distinct original v6 source identities")
    if any(
        not isinstance(row, dict)
        or row.get("status") != "BLOCKED"
        or row.get("blocker") != STALE_BLOCKER
        or set(row) != {"source", "status", "blocker"}
        for row in rows
    ):
        raise ValueError("Unexpected v6 status, blocker or evidence fields")
    observed = [row["source"] for row in rows]
    if len(set(observed)) != 7 or set(observed) != expected:
        raise ValueError("V6 stale-head rejection did not cover all seven pinned sources")
    return len(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr8-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args(argv)
    proc = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).with_name("phase1_copilot_receipts_v6_adapter.py")),
            "--pr8-root", str(args.pr8_root),
            "--source-root", str(args.source_root),
        ],
        capture_output=True, text=True, check=False,
    )
    try:
        count = verify_stale_head_rejection(proc.returncode, proc.stdout)
    except ValueError as exc:
        print(f"V6_STALE_HEAD_NEGATIVE_FAIL: {exc}", file=sys.stderr)
        print(proc.stdout[-2000:], file=sys.stderr)
        print(proc.stderr[-2000:], file=sys.stderr)
        return 1
    print(f"V6_STALE_HEAD_REJECTION_PASS count={count} historical_only=true current_approval=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
