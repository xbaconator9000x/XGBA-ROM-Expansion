#!/usr/bin/env python3
"""Phase 1 only: exact-pinned whole-file FireRed Flash source-contract verifier.

No runtime, emulator, or independent reviewer approval is asserted.
"""
import copy
import hashlib
import json
import re
import urllib.request
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
REPO = "pret/pokefirered"
MANIFEST = Path("docs/phase1-flash-review/flash-wholefile-manifest.json")
SCHEMA = "xgba-phase1-firered-flash-wholefile-v1"
FUNC = re.compile(r"^(?:static\s+)?(?:u8|u16|u32|void)\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*$")
BINARY = re.compile(r"^[0-9a-f]{40}$")


def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def lines_of(data):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Non-UTF-8 source") from exc
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return lines


def functions_of(lines):
    found = []
    for i, line in enumerate(lines):
        match = FUNC.fullmatch(line)
        if not match:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j == len(lines) or lines[j].strip() != "{":
            continue
        depth = 0
        for end in range(j, len(lines)):
            depth += lines[end].count("{") - lines[end].count("}")
            if depth == 0:
                found.append({"name": match.group(1), "start_line": i + 1, "end_line": end + 1})
                break
        else:
            raise ValueError("Unbalanced function braces")
    return found


def verify(manifest, blobs):
    if manifest.get("schema") != SCHEMA or manifest.get("phase") != "Phase 1 source-only":
        raise ValueError("Wrong review schema/phase")
    if manifest.get("authoritative_gate") != "FAIL_INCOMPLETE":
        raise ValueError("Gate not fail-closed")
    if manifest.get("inventory") != 14834 or manifest.get("registered_prepared_baseline") != 113 or manifest.get("independent_approved") != 0:
        raise ValueError("Census, baseline, or approvals forged")
    if manifest.get("source_pins") != {REPO: PIN}:
        raise ValueError("Pinned source drift")
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 4:
        raise ValueError("Expected four distinct whole-file records")
    paths = set()
    for rec in records:
        path = rec["path"]
        if path in paths or path not in blobs:
            raise ValueError("Duplicate or missing source")
        paths.add(path)
        if rec.get("repository") != REPO or rec.get("pinned_commit") != PIN or rec.get("independent_approval") is not False:
            raise ValueError("Identity or false approval")
        if rec.get("review_status") != "proposed_complete_file_candidate_pending_independent_review":
            raise ValueError("Incorrect review state")
        sha = rec.get("git_blob_sha1")
        if not isinstance(sha, str) or not BINARY.fullmatch(sha) or blob_sha(blobs[path]) != sha:
            raise ValueError("Git blob SHA-1 mismatch")
        lines = lines_of(blobs[path])
        if rec.get("source_lines") != len(lines) or rec.get("nonblank_lines") != sum(bool(x.strip()) for x in lines):
            raise ValueError("Whole-file line inventory drift")
        includes = re.findall(r'^#include "([^"]+)"', "\n".join(lines), re.M)
        if rec.get("includes") != includes:
            raise ValueError("Include dependency drift")
        if rec.get("functions") != functions_of(lines):
            raise ValueError("Complete function inventory drift")
        symbols = rec.get("file_scope_symbols")
        if not isinstance(symbols, list) or len({s["name"] for s in symbols}) != len(symbols):
            raise ValueError("Bad file-scope symbol inventory")
        for s in symbols:
            line_num = s["line"]
            if not isinstance(line_num, int) or not 1 <= line_num <= len(lines):
                raise ValueError("Bad symbol line")
            line = lines[line_num - 1]
            if not re.search(r"\b" + re.escape(s["name"]) + r"\b", line) or not line.startswith(("static ", "COMMON_DATA ", "const ")):
                raise ValueError("File-scope symbol drift")
    expected_paths = {"src/agb_flash.c", "src/agb_flash_1m.c", "src/agb_flash_mx.c", "src/agb_flash_le.c"}
    if paths != expected_paths:
        raise ValueError("Unexpected source set")
    dependencies = manifest.get("dependency_blobs")
    if not isinstance(dependencies, list) or {d["path"] for d in dependencies} != {"include/gba/flash_internal.h", "src/save.c"}:
        raise ValueError("Missing dependency endpoints")
    for d in dependencies:
        if d["path"] not in blobs or blob_sha(blobs[d["path"]]) != d["git_blob_sha1"]:
            raise ValueError("Dependency source hash mismatch")
    if not manifest.get("limitations"):
        raise ValueError("Missing reviewer obligations")
    return {"verified_complete_source_files": len(paths), "verified_function_definitions": sum(len(r["functions"]) for r in records),
            "verified_source_lines": sum(r["source_lines"] for r in records), "verified_dependency_blobs": len(dependencies),
            "independent_approvals": 0, "gate": "FAIL_INCOMPLETE"}


def negative_controls(manifest, blobs):
    cases = []
    def mutated(name, change, byte_change=None):
        m, b = copy.deepcopy(manifest), dict(blobs)
        change(m)
        if byte_change is not None:
            byte_change(b)
        try:
            verify(m, b)
        except (ValueError, KeyError, IndexError, TypeError):
            cases.append(name)
        else:
            raise AssertionError("Negative control incorrectly passed: " + name)
    mutated("false approval", lambda m: m["records"][0].update(independent_approval=True))
    mutated("gate bypass", lambda m: m.update(authoritative_gate="PASS"))
    mutated("count inflation", lambda m: m.update(registered_prepared_baseline=117))
    mutated("pinned commit drift", lambda m: m["source_pins"].update({REPO: "0" * 40}))
    mutated("duplicate identity", lambda m: m["records"][1].update(path=m["records"][0]["path"]))
    mutated("missing function", lambda m: m["records"][0]["functions"].pop())
    mutated("wrong function anchor", lambda m: m["records"][0]["functions"][0].update(start_line=999))
    mutated("missing symbol", lambda m: m["records"][0]["file_scope_symbols"].pop())
    mutated("forged dependency hash", lambda m: m["dependency_blobs"][0].update(git_blob_sha1="0" * 40))
    mutated("forged line count", lambda m: m["records"][0].update(source_lines=1))
    mutated("missing include", lambda m: m["records"][0].update(includes=[]))
    mutated("wrong schema", lambda m: m.update(schema="xgba-phase2"))
    mutated("altered source bytes", lambda m: None, lambda b: b.update({"src/agb_flash.c": b["src/agb_flash.c"] + b"\n"}))
    mutated("truncated dependency", lambda m: None, lambda b: b.update({"src/save.c": b["src/save.c"][:-1]}))
    return cases


def fetch_pinned(path):
    url = f"https://raw.githubusercontent.com/{REPO}/{PIN}/{path}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "xgba-phase1-review-verifier"}), timeout=30) as response:
        return response.read()


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths = {r["path"] for r in manifest["records"]} | {d["path"] for d in manifest["dependency_blobs"]}
    blobs = {p: fetch_pinned(p) for p in sorted(paths)}
    result = verify(manifest, blobs)
    negatives = negative_controls(manifest, blobs)
    result["negative_controls_passed"] = len(negatives)
    result["negative_control_names"] = negatives
    result["pinned_revision"] = PIN
    print(json.dumps(result, sort_keys=True, indent=2))
    Path("docs/phase1-flash-review/verification-evidence.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
