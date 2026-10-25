#!/usr/bin/env python3
"""Cross-packet Phase 1 mGBA review queue; candidate evidence, never approval.

Combines exact-pinned timing/DMA and EEPROM/savestate candidate registers.
Preserves all original source identities, priorities, and machine review statuses.
"""
from __future__ import annotations

import collections
import copy
import csv
import gzip
import hashlib
import io
import json
import sys
from pathlib import Path

import phase1_additive_review_scheduler as timing
import verify_mgba_eeprom_savestate_additive as eeprom

EEPROM_REGISTRY = eeprom.REGISTRY
TARGET = Path("audit-output/architecture_semantic_review_queue_additive_v3.csv.gz")
SUMMARY = Path("audit-output/architecture_semantic_review_priority_additive_v3.json")
EEPROM_TIER = "A0C_PINNED_MGBA_EEPROM_SAVESTATE_ADDITIVE"
REQUIRED_OVERLAP = {
    "EEPROM_WRITE_SETTLING_SCHEDULER": "MGBA_TIMING_REROOT_PROMOTION_AFTER_ROOT_DRAIN",
    "EEPROM_ROM2_EX_16BIT_DISPATCH": "MGBA_DMA3_ROM2_EX_EEPROM_SERVICE",
}


def reject(message):
    raise ValueError(message)


def span(ref):
    path, line_range = ref.rsplit(":", 1)
    start, end = (int(x) for x in line_range.split("-"))
    return path, start, end


def overlaps(first, second):
    p1, a, b = span(first)
    p2, c, d = span(second)
    return p1 == p2 and max(a, c) <= min(b, d)


def validate(rows, base, timing_doc, eeprom_doc, gate):
    original, timing_candidates = timing.validate(rows, base, timing_doc, gate)
    eeprom.validate(eeprom_doc)
    eeprom.validate_snapshot(rows, base, gate, eeprom_doc)

    # The first scheduler must have assigned the original 29 and two timing
    # sources before the second packet can be incorporated. Never silently
    # replace an existing review assignment or source status.
    indexed = {(r["repo"], r["path"]): r for r in rows}
    if len(indexed) != len(rows):
        reject("Duplicate source queue keys")
    expected_timing = set(timing_candidates)
    expected_eeprom = {("mgba-emu/mgba", c["path"]) for c in eeprom_doc["candidates"]}
    if len(expected_eeprom) != 2 or expected_eeprom & (set(original) | expected_timing):
        reject("Cross-packet source overlap or missing EEPROM candidate")
    for row in rows:
        key = (row["repo"], row["path"])
        if (row.get("source_queue_priority_preserved") != row["priority"]
                or row.get("source_queue_machine_review_status_preserved") != row["machine_review_status"]):
            reject("Original priority or machine review status was changed")
        if key in original:
            wanted_tier, wanted_registry = timing.ORIGINAL_TIER, str(timing.BASE)
        elif key in timing_candidates:
            wanted_tier, wanted_registry = timing.EXTRA_TIER, str(timing.ADDITIVE)
        else:
            wanted_tier, wanted_registry = None, ""
        if wanted_tier is not None and (row["architecture_review_tier"] != wanted_tier
                                        or row["curated_candidate_registry"] != wanted_registry):
            reject("Previously scheduled source review assignment drift")
        if wanted_tier is None and row["curated_candidate_registry"]:
            reject("Unrecognised pre-existing curated review assignment")
        if key in expected_eeprom and row["architecture_review_tier"] in (
                timing.ORIGINAL_TIER, timing.EXTRA_TIER):
            reject("EEPROM candidate already claimed by another registry")

    if (collections.Counter(r["architecture_review_tier"] for r in rows)[timing.ORIGINAL_TIER] != 29
            or collections.Counter(r["architecture_review_tier"] for r in rows)[timing.EXTRA_TIER] != 2):
        reject("First-stage review queue did not schedule 29 + 2 candidates")

    # Require the EEPROM write event to land in the exact-pinned timing
    # scheduler candidate, and CPU EEPROM dispatch to overlap the separately
    # mapped DMA ROM2_EX consumer. This is an edge reconciliation, not a
    # dynamic alias/interleaving proof.
    timing_by_path = {c["path"]: c for c in timing_doc["candidates"]}
    eeprom_by_path = {c["path"]: c for c in eeprom_doc["candidates"]}
    ec = {c["id"]: c for c in eeprom_doc["cross_source_contracts"]}
    tc = {c["id"]: c for c in timing_doc["cross_source_contracts"]}
    scheduler_consumer = ec["EEPROM_WRITE_SETTLING_SCHEDULER"]["consumer"]
    scheduler_range = timing_by_path["src/core/timing.c"]["source_lines"]
    if not overlaps(scheduler_consumer,
                    "src/core/timing.c:%d-%d" % tuple(scheduler_range)):
        reject("EEPROM settle callback no longer targets pinned timing candidate")
    if not overlaps(ec["EEPROM_ROM2_EX_16BIT_DISPATCH"]["producer"],
                    tc["MGBA_DMA3_ROM2_EX_EEPROM_SERVICE"]["consumer"]):
        reject("CPU EEPROM and DMA ROM2_EX dependency no longer share memory path")
    for item in eeprom_doc["candidates"]:
        for ref in item["cross_source_consumers"]:
            timing.check_ref(ref, {p for repo, p in indexed if repo == "mgba-emu/mgba"})
    for contract in eeprom_doc["cross_source_contracts"]:
        for endpoint in ("producer", "consumer"):
            timing.check_ref(contract[endpoint],
                             {p for repo, p in indexed if repo == "mgba-emu/mgba"})
    return original, timing_candidates, eeprom_by_path


def negative_controls(rows, base, timing_doc, eeprom_doc, gate):
    cases = [
        ("EEPROM false approval", lambda r, b, t, e, g: e.update(independent_whole_file_approvals=1)),
        ("EEPROM false signoff", lambda r, b, t, e, g: e["candidates"][0].update(independent_signoff=True)),
        ("EEPROM changed blob", lambda r, b, t, e, g: e["candidates"][0].update(git_blob_sha1="0" * 40)),
        ("EEPROM removed candidate", lambda r, b, t, e, g: e["candidates"].pop()),
        ("EEPROM changed dependency", lambda r, b, t, e, g: e["cross_source_contracts"][1].update(consumer="src/gba/memory.c:1-2")),
        ("EEPROM false proof", lambda r, b, t, e, g: e["cross_source_contracts"][0].update(proof_level="APPROVED")),
        ("timing false approval", lambda r, b, t, e, g: t.update(independent_whole_file_approvals=1)),
        ("gate false approval", lambda r, b, t, e, g: g.update(approved_semantic_dispositions=1)),
        ("original false signoff", lambda r, b, t, e, g: b["candidate_files"][0].update(independent_whole_file_signoff=True)),
        ("source hash drift", lambda r, b, t, e, g: next(x for x in r if x["path"] == "src/gba/savedata.c" and x["repo"] == "mgba-emu/mgba").update(blob_sha="0" * 40)),
        ("first-stage tier drift", lambda r, b, t, e, g: next(x for x in r if x["path"] == "src/core/timing.c" and x["repo"] == "mgba-emu/mgba").update(architecture_review_tier="A5_P2_QUEUE")),
        ("source status drift", lambda r, b, t, e, g: r[0].update(source_queue_machine_review_status_preserved="APPROVED")),
    ]
    for label, mutate in cases:
        r, b, t, e, g = copy.deepcopy((rows, base, timing_doc, eeprom_doc, gate))
        mutate(r, b, t, e, g)
        try:
            validate(r, b, t, e, g)
        except ValueError:
            continue
        raise AssertionError("Fail-open cross-packet review control: " + label)
    return len(cases)


def main():
    # Generate the first stage from the immutable queue using the previously
    # verified scheduler, then verify its provenance before deriving v3.
    timing.main()
    with gzip.open(timing.TARGET, "rt", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    base = json.loads(timing.BASE.read_text(encoding="utf-8"))
    timing_doc = json.loads(timing.ADDITIVE.read_text(encoding="utf-8"))
    eeprom_doc = json.loads(EEPROM_REGISTRY.read_text(encoding="utf-8"))
    gate = json.loads(timing.GATE.read_text(encoding="utf-8"))
    stage2 = json.loads(timing.SUMMARY.read_text(encoding="utf-8"))
    if (stage2.get("decision") != "FAIL_INCOMPLETE"
            or stage2.get("independent_whole_file_approvals") != 0
            or stage2.get("output_queue_sha256") != hashlib.sha256(timing.TARGET.read_bytes()).hexdigest()
            or stage2.get("source_queue_sha256") != hashlib.sha256(timing.SOURCE.read_bytes()).hexdigest()
            or stage2.get("total_curated_candidates_pending_review") != 31):
        reject("First-stage evidence is stale, incomplete or claims approvals")
    original, timing_candidates, eeprom_candidates = validate(
        rows, base, timing_doc, eeprom_doc, gate)
    checks = negative_controls(rows, base, timing_doc, eeprom_doc, gate)

    output = []
    for row in rows:
        item = dict(row)
        if item["repo"] == "mgba-emu/mgba" and item["path"] in eeprom_candidates:
            candidate = eeprom_candidates[item["path"]]
            item.update({
                "architecture_review_tier": EEPROM_TIER,
                "architecture_review_reason": "Exact-pinned EEPROM/savestate dependency candidate; independent whole-file review pending",
                "curated_semantic_roles": ",".join(candidate["semantic_roles"]),
                "curated_candidate_registry": str(EEPROM_REGISTRY),
            })
        output.append(item)
    rank = {
        timing.ORIGINAL_TIER: 0, timing.EXTRA_TIER: 1, EEPROM_TIER: 2,
        "A1_ARCHITECTURE_CRITICAL_P0": 3, "A2_OTHER_P0": 4,
        "A3_P0_GAMEPLAY_SCRIPT_FIXTURE": 5, "A4_P1_QUEUE": 6,
        "A5_P2_QUEUE": 7, "A6_P3_QUEUE": 8,
    }
    counts = collections.Counter(r["architecture_review_tier"] for r in output)
    if (len(output) != 14834 or counts[timing.ORIGINAL_TIER] != 29
            or counts[timing.EXTRA_TIER] != 2 or counts[EEPROM_TIER] != 2
            or counts["A3_P0_GAMEPLAY_SCRIPT_FIXTURE"] != 163
            or collections.Counter(r["priority"] for r in output)["P0"] != 338
            or any(r["architecture_review_tier"] not in rank for r in output)):
        reject("Cross-packet review queue lost or misclassified source records")
    output.sort(key=lambda r: (rank[r["architecture_review_tier"]], r["repo"], r["path"]))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("wb") as file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=file, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(output)
    result = {
        "schema": "xgba.phase1.architecture_review_additive.v3",
        "source_queue_sha256": hashlib.sha256(timing.SOURCE.read_bytes()).hexdigest(),
        "original_registry_sha256": hashlib.sha256(timing.BASE.read_bytes()).hexdigest(),
        "timing_registry_sha256": hashlib.sha256(timing.ADDITIVE.read_bytes()).hexdigest(),
        "eeprom_registry_sha256": hashlib.sha256(EEPROM_REGISTRY.read_bytes()).hexdigest(),
        "stage2_queue_sha256": hashlib.sha256(timing.TARGET.read_bytes()).hexdigest(),
        "output_queue_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        "source_files_preserved": 14834,
        "original_P0_preserved": 338,
        "original_P0_gameplay_scripts_preserved": 163,
        "original_curated_pending": len(original),
        "timing_candidates_pending": len(timing_candidates),
        "eeprom_candidates_pending": len(eeprom_candidates),
        "total_candidates_pending": 33,
        "tier_counts": dict(sorted(counts.items())),
        "cross_packet_dependency_intersections": list(REQUIRED_OVERLAP),
        "additional_negative_controls_passed": checks,
        "independent_whole_file_approvals": 0,
        "phase1_mapping_complete": False,
        "decision": "FAIL_INCOMPLETE",
        "limitations": [
            "Source identities and typed line references are review evidence only",
            "No whole-file semantic, compiled ABI, DMA/CPU interleaving, emulator or editor compatibility signoff",
            "No Phase 2 implementation and no modification to the authoritative source census",
        ],
    }
    SUMMARY.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("Cross-packet Phase 1 queue: 14,834 source rows; 29 original + 2 timing + 2 EEPROM = 33 pending; 338 P0; %d negative controls; zero approvals; FAIL_INCOMPLETE" % checks)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Cross-packet Phase 1 scheduler FAILED:", error, file=sys.stderr)
        sys.exit(2)
