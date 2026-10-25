#!/usr/bin/env python3
"""Versioned additive Phase 1 review scheduler; never a semantic signoff.

Reads the immutable 14,834-file snapshot and two separately pinned candidate
registers. No source file, original priority, or machine status is changed.
"""
from __future__ import annotations

import collections
import copy
import csv
import gzip
import hashlib
import io
import json
import re
import sys
from pathlib import Path

from phase1_architecture_review_priorities import tier

ROOT = Path("semantic-snapshots/current")
BASE = Path("semantic-snapshots/curated/p0_semantic_review_candidates_2026-10-26.json")
ADDITIVE = Path("semantic-snapshots/curated/mgba_timing_dma_additive_candidates_2026-10-26.json")
SOURCE = ROOT / "semantic_review_queue.csv.gz"
GATE = ROOT / "phase1_mapping_gate.json"
TARGET = Path("audit-output/architecture_semantic_review_queue_additive_v2.csv.gz")
SUMMARY = Path("audit-output/architecture_semantic_review_priority_additive_v2.json")
EXTRA_TIER = "A0B_PINNED_MGBA_TIMING_DMA_ADDITIVE"
ORIGINAL_TIER = "A0_PINNED_CROSS_SOURCE_CONTRACT_OWNER"
REQUIRED_CONTRACTS = {
    "MGBA_TIMING_REROOT_PROMOTION_AFTER_ROOT_DRAIN": (
        "src/core/timing.c:104-124", "src/gba/dma.c:233-254"),
    "MGBA_DMA_IMMEDIATE_START_THREE_CYCLES": (
        "src/gba/dma.c:137-140", "src/core/timing.c:36-63"),
    "MGBA_DMA3_ROM2_EX_EEPROM_SERVICE": (
        "src/gba/dma.c:259-315", "src/gba/memory.c:586-625"),
}
REF = re.compile(r"^([a-zA-Z0-9_./-]+):(\\d+)-(\\d+)$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def reject(message):
    raise ValueError(message)


def check_ref(value, paths):
    match = REF.fullmatch(value) if isinstance(value, str) else None
    if not match:
        reject("Malformed pinned-source line reference")
    path, start, end = match.group(1), int(match.group(2)), int(match.group(3))
    if path not in paths or ".." in Path(path).parts or start < 1 or end < start:
        reject("Unresolved pinned-source dependency or invalid line range: " + value)


def validate(rows, base, extra, gate):
    if gate.get("decision") != "FAIL_INCOMPLETE" or gate.get("approved_semantic_dispositions") != 0:
        reject("Authoritative mapping gate changed or claimed approvals")
    if gate.get("verified_source_manifest_entries") != 14834 or gate.get("p0_review_candidates") != 338:
        reject("Authoritative source inventory changed; rebaseline required")
    if len(rows) != 14834 or collections.Counter(r["priority"] for r in rows)["P0"] != 338:
        reject("Immutable source queue count or P0 distribution changed")
    if base.get("candidate_file_count") != 29 or base.get("independent_review_approvals") != 0 or base.get("phase1_mapping_complete") is not False:
        reject("Original curated registry changed or claimed approval")
    pins = base.get("repository_pins")
    if not isinstance(pins, dict) or len(pins) != 5:
        reject("Expected five pinned upstream revisions")
    if (extra.get("schema") != "xgba.phase1.additive_timing_dma_semantic_candidates.v1"
            or extra.get("source_repository") != "mgba-emu/mgba"
            or extra.get("pinned_revision") != pins.get("mgba-emu/mgba")
            or extra.get("parent_curated_registry") != str(BASE)
            or extra.get("parent_curated_count_unchanged") != 29
            or extra.get("additional_source_files") != 2
            or extra.get("independent_whole_file_approvals") != 0
            or extra.get("phase1_mapping_complete") is not False):
        reject("Additive registry pin, parent or approval claim invalid")
    index = {}
    for row in rows:
        key = (row["repo"], row["path"])
        if key in index or row["repo"] not in pins or not HEX40.fullmatch(row["blob_sha"]):
            reject("Duplicate or unpinned source queue entry: " + str(key))
        index[key] = row
    original = {}
    for item in base.get("candidate_files", []):
        key = (item["repository"], item["source_path"])
        if key in original or key not in index:
            reject("Duplicate or missing original curated file")
        if (item.get("revision") != pins.get(key[0])
                or item.get("expected_git_blob_sha1") != index[key]["blob_sha"]
                or item.get("independent_whole_file_signoff") is not False
                or item.get("path_complete_alias_lifetime_proof") is not False
                or item.get("status") != "CANDIDATE_AWAITING_INDEPENDENT_WHOLE_FILE_REVIEW"
                or not item.get("interpreted_semantic_roles")):
            reject("Original curated source identity or pending status invalid")
        original[key] = item["interpreted_semantic_roles"]
    if len(original) != 29:
        reject("Original 29-file curated register incomplete")
    additions = {}
    expected = {
        "src/core/timing.c": "cebd619957b0845deedfc03b1e9c89d168861ea1",
        "include/mgba/core/timing.h": "6e938970e9ffdaa2c8c6f20d71319c0df9eccb5e",
    }
    for item in extra.get("candidates", []):
        path = item.get("path")
        key = ("mgba-emu/mgba", path)
        if path not in expected or key in additions or key in original or key not in index:
            reject("Unknown, duplicate or missing additive source")
        if item.get("git_blob_sha1") != expected[path] or index[key]["blob_sha"] != expected[path]:
            reject("Additive source Git blob mismatch with immutable queue")
        if item.get("independent_signoff") is not False or not item.get("unresolved") or not item.get("semantic_roles"):
            reject("Additive source falsely signed off or lacks obligations")
        lines = item.get("source_lines")
        if not isinstance(lines, list) or len(lines) != 2 or not all(isinstance(x, int) for x in lines) or lines[0] < 1 or lines[1] < lines[0]:
            reject("Invalid additive source line range")
        paths = {key[1] for key in index if key[0] == "mgba-emu/mgba"}
        for reference in item.get("cross_source_consumers", []):
            check_ref(reference, paths)
        if not item.get("cross_source_consumers"):
            reject("Missing cross-source consumer")
        additions[key] = item["semantic_roles"]
    if set(k[1] for k in additions) != set(expected):
        reject("Expected both additive timing sources")
    contracts = extra.get("cross_source_contracts")
    if not isinstance(contracts, list) or len(contracts) != 3:
        reject("Expected three typed cross-source contracts")
    seen_contracts = set()
    paths = {key[1] for key in index if key[0] == "mgba-emu/mgba"}
    for contract in contracts:
        ident = contract.get("id")
        if ident not in REQUIRED_CONTRACTS or ident in seen_contracts:
            reject("Unknown or duplicate cross-source contract")
        if (contract.get("producer"), contract.get("consumer")) != REQUIRED_CONTRACTS[ident]:
            reject("Cross-source contract endpoints changed")
        if contract.get("proof_level") != "PINNED_SOURCE_INTERPRETATION_WITH_EXISTING_NATIVE_FIXTURE":
            reject("Cross-source contract evidence level changed")
        check_ref(contract["producer"], paths)
        check_ref(contract["consumer"], paths)
        seen_contracts.add(ident)
    if seen_contracts != set(REQUIRED_CONTRACTS):
        reject("Cross-source dependency chain incomplete")
    return original, additions


def self_test(rows, base, extra, gate):
    validate(rows, base, extra, gate)
    cases = [
        ("approval", lambda b, e, g: e.update(independent_whole_file_approvals=1)),
        ("baseline-approval", lambda b, e, g: g.update(approved_semantic_dispositions=1)),
        ("blob", lambda b, e, g: e["candidates"][0].update(git_blob_sha1="0" * 40)),
        ("missing-source", lambda b, e, g: e["candidates"].pop()),
        ("contract-endpoint", lambda b, e, g: e["cross_source_contracts"][0].update(consumer="src/gb/memory.c:1-2")),
        ("contract-proof", lambda b, e, g: e["cross_source_contracts"][0].update(proof_level="APPROVED")),
        ("missing-obligations", lambda b, e, g: e["candidates"][0].update(unresolved=[])),
        ("original-signoff", lambda b, e, g: b["candidate_files"][0].update(independent_whole_file_signoff=True)),
    ]
    for label, change in cases:
        b, e, g = copy.deepcopy((base, extra, gate))
        change(b, e, g)
        try:
            validate(rows, b, e, g)
        except ValueError:
            continue
        raise AssertionError("Fail-open additive scheduler negative control: " + label)
    print("Additive review scheduler: 8 false-approval/identity/dependency controls PASS")


def main():
    with gzip.open(SOURCE, "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    base = json.loads(BASE.read_text(encoding="utf-8"))
    extra = json.loads(ADDITIVE.read_text(encoding="utf-8"))
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    self_test(rows, base, extra, gate)
    original, additions = validate(rows, base, extra, gate)
    output = []
    counts = collections.Counter()
    original_p0 = collections.Counter()
    for row in rows:
        key = (row["repo"], row["path"])
        if key in additions:
            tag = EXTRA_TIER
            reason = "Exact-pinned mGBA scheduler/DMA dependency candidate; independent review pending"
            roles = ",".join(additions[key])
            registry = str(ADDITIVE)
        else:
            tag, reason, roles = tier(row["repo"], row["path"], row["priority"], original)
            registry = str(BASE) if key in original else ""
        item = dict(row)
        item.update({
            "architecture_review_tier": tag,
            "architecture_review_reason": reason,
            "curated_semantic_roles": roles,
            "curated_candidate_registry": registry,
            "source_queue_priority_preserved": row["priority"],
            "source_queue_machine_review_status_preserved": row["machine_review_status"],
        })
        output.append(item)
        counts[tag] += 1
        original_p0[row["priority"]] += (row["priority"] == "P0")
    rank = {ORIGINAL_TIER: 0, EXTRA_TIER: 1,
            "A1_ARCHITECTURE_CRITICAL_P0": 2, "A2_OTHER_P0": 3,
            "A3_P0_GAMEPLAY_SCRIPT_FIXTURE": 4, "A4_P1_QUEUE": 5,
            "A5_P2_QUEUE": 6, "A6_P3_QUEUE": 7}
    output.sort(key=lambda row: (rank[row["architecture_review_tier"]], row["repo"], row["path"]))
    if (len(output) != 14834 or counts[ORIGINAL_TIER] != 29
            or counts[EXTRA_TIER] != 2 or counts["A3_P0_GAMEPLAY_SCRIPT_FIXTURE"] != 163
            or original_p0["P0"] != 338):
        reject("Additive scheduling dropped source entries or changed original P0")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("wb") as file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=file, mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as out:
                writer = csv.DictWriter(out, fieldnames=list(rows[0]) + [
                    "architecture_review_tier", "architecture_review_reason",
                    "curated_semantic_roles", "curated_candidate_registry",
                    "source_queue_priority_preserved", "source_queue_machine_review_status_preserved"])
                writer.writeheader()
                writer.writerows(output)
    summary = {
        "schema": "xgba.phase1.architecture_review_additive.v2",
        "source_queue_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "baseline_registry_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
        "additive_registry_sha256": hashlib.sha256(ADDITIVE.read_bytes()).hexdigest(),
        "output_queue_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        "original_tracked_files": 14834,
        "original_P0_retained": 338,
        "original_curated_candidates": 29,
        "additional_source_candidates": 2,
        "total_curated_candidates_pending_review": 31,
        "original_P0_gameplay_scripts_retained": 163,
        "tier_counts": dict(sorted(counts.items())),
        "negative_controls_passed": 8,
        "independent_whole_file_approvals": 0,
        "phase1_mapping_complete": False,
        "decision": "FAIL_INCOMPLETE",
        "limitation": "Review ordering and source-line dependency references are candidate evidence, not runtime, alias or whole-file semantic proof.",
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Additive architecture queue: 14,834 source rows, 29 original + 2 timing candidates, 338 original P0, 0 approvals; FAIL_INCOMPLETE")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Additive Phase 1 review scheduler FAILED:", error, file=sys.stderr)
        sys.exit(2)
