#!/usr/bin/env python3
"""Read-only discovery of GBA ROM identity; NEVER authorizes conversion.

XGBA's platform-wide goal includes existing modified ROM hacks. This Phase 1
preflight is deliberately conservative: header/title/game-code similarity is
not an engine identification; a candidate profile match is not independent
semantic review, runtime certification, or permission to transform.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HEADER_BYTES = 0xC0
MAX_ROM_BYTES = 1024 * 1024 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def _read_ascii(value):
    return value.rstrip(b"\0 ").decode("ascii", "replace")


def _checksum(header):
    # GBA complement check over bytes A0..BC inclusive.
    return (-sum(header[0xA0:0xBD]) - 0x19) & 0xFF


def _catalog(path):
    if path is None:
        return []
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise ValueError("Profile catalog schema must equal 1")
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or len(profiles) > 10000:
        raise ValueError("Profile catalog requires bounded profiles list")
    ids, signatures = set(), set()
    for entry in profiles:
        if not isinstance(entry, dict):
            raise ValueError("Invalid catalog profile")
        profile_id, sha, size, code = (
            entry.get("profile_id"), entry.get("sha256"), entry.get("byte_length"),
            entry.get("game_code"),
        )
        if not isinstance(profile_id, str) or not PROFILE_ID.fullmatch(profile_id):
            raise ValueError("Invalid catalog profile identifier")
        if not isinstance(sha, str) or not SHA256.fullmatch(sha):
            raise ValueError("Invalid catalog profile SHA-256")
        if type(size) is not int or not HEADER_BYTES <= size <= MAX_ROM_BYTES:
            raise ValueError("Invalid catalog expected size")
        if not isinstance(code, str) or len(code) != 4:
            raise ValueError("Invalid catalog game code")
        if profile_id in ids or (sha, size) in signatures:
            raise ValueError("Ambiguous duplicate exact-ROM catalog entry")
        ids.add(profile_id)
        signatures.add((sha, size))
    return profiles


def inspect(path, catalog=None, max_size=MAX_ROM_BYTES):
    if type(max_size) is not int or max_size < HEADER_BYTES:
        raise ValueError("Invalid read limit")
    rom = Path(path)
    sha = hashlib.sha256()
    total = 0
    header = b""
    with rom.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > max_size:
                raise ValueError("ROM exceeds configured read limit")
            if len(header) < HEADER_BYTES:
                header += block[:HEADER_BYTES - len(header)]
            sha.update(block)
    metadata = {
        "filename": rom.name, "bytes": total, "sha256": sha.hexdigest(),
        "read_only": True, "engine_confirmed": False,
        "conversion_permitted": False, "semantic_approval_claimed": False,
        "status": "UNKNOWN_ROM", "matched_profile": None,
    }
    if total < HEADER_BYTES:
        metadata.update(status="INVALID_OR_UNSAFE_INPUT",
                        reason="GBA header incomplete")
        return metadata
    marker = header[0xB2] == 0x96
    checksum = _checksum(header)
    checksum_ok = checksum == header[0xBD]
    metadata.update({
        "game_title": _read_ascii(header[0xA0:0xAC]),
        "game_code": _read_ascii(header[0xAC:0xB0]),
        "maker_code": _read_ascii(header[0xB0:0xB2]),
        "version": header[0xBC],
        "fixed_header_byte_valid": marker,
        "header_checksum_valid": checksum_ok,
        "header_checksum_expected": checksum,
        "header_checksum_actual": header[0xBD],
    })
    if not marker or not checksum_ok:
        metadata.update(status="INVALID_OR_UNSAFE_INPUT",
                        reason="Malformed GBA header; cannot select adapter")
        return metadata
    found = [
        item for item in _catalog(catalog)
        if item["sha256"] == metadata["sha256"]
        and item["byte_length"] == total
        and item["game_code"] == metadata["game_code"]
    ]
    if len(found) > 1:
        raise ValueError("Ambiguous ROM compatibility profiles")
    if found:
        metadata["matched_profile"] = found[0]["profile_id"]
        metadata["status"] = "EXACT_PROFILE_IDENTITY_ONLY"
        metadata["reason"] = (
            "Exact identity found, but source/runtime evidence and independent "
            "approval remain separate gates; no conversion authorized."
        )
    else:
        metadata["reason"] = (
            "No exact pinned profile. Header similarities cannot prove engine "
            "or patch compatibility; no automatic conversion."
        )
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", help="existing GBA ROM to inspect without modifying")
    parser.add_argument("--profiles", help="optional versioned exact-digest catalog")
    parser.add_argument("--max-bytes", type=int, default=MAX_ROM_BYTES)
    parser.add_argument("--out", help="write JSON compatibility discovery report")
    args = parser.parse_args()
    try:
        result = inspect(args.rom, args.profiles, args.max_bytes)
        serialized = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.out:
            Path(args.out).write_text(serialized, encoding="utf-8")
        print(serialized, end="")
        return 2 if result["status"] == "INVALID_OR_UNSAFE_INPUT" else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("XGBA_PREFLIGHT_FAIL_CLOSED: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
