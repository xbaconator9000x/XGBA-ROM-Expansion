#!/usr/bin/env python3
"""Pinned mGBA timing/DMA source candidate verifier; not independent signoff."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
REGISTRY = Path("semantic-snapshots/curated/mgba_timing_dma_additive_candidates_2026-10-26.json")
EXPECTED = {
    "src/core/timing.c": "cebd619957b0845deedfc03b1e9c89d168861ea1",
    "include/mgba/core/timing.h": "6e938970e9ffdaa2c8c6f20d71319c0df9eccb5e",
    "src/gba/dma.c": "da2a800ba48cb32d6e10e42c3b3527ef406bad22",
}
CHECKS = [
    ("MGBA_TIMING_EVENT_ABI", "include/mgba/core/timing.h",
     r"void \(\*callback\)\(struct mTiming\*, void\* context, uint32_t\);"),
    ("MGBA_TIMING_ROOT_REROOT_STATE", "include/mgba/core/timing.h",
     r"struct mTimingEvent\* root;\s*struct mTimingEvent\* reroot;"),
    ("MGBA_TIMING_INTERRUPT_REROOT", "src/core/timing.c",
     r"void mTimingInterrupt\([^)]*\)\s*\{.*?timing->reroot = timing->root;\s*timing->root = NULL;"),
    ("MGBA_TIMING_SCHEDULE_REROOT_CHOICE", "src/core/timing.c",
     r"void mTimingSchedule\([^)]*\)\s*\{.*?if \(timing->reroot\) \{\s*previous = &timing->reroot;"),
    ("MGBA_TIMING_ROOT_CALLBACK_BEFORE_REROOT_PROMOTION", "src/core/timing.c",
     r"int32_t mTimingTick\([^)]*\)\s*\{.*?while \(timing->root\) \{.*?next->callback\(timing, next->context, -nextWhen\);.*?if \(UNLIKELY\(timing->reroot\)\) \{\s*timing->root = timing->reroot;"),
    ("MGBA_DMA_CALLBACK_SLOT", "src/gba/dma.c",
     r"void GBADMAInit\([^)]*\)\s*\{.*?dmaEvent.callback = _dmaEvent;"),
    ("MGBA_DMA_THREE_CYCLE_START", "src/gba/dma.c",
     r"GBADMARegisterGetTiming\(currentDma->reg\) == GBA_DMA_TIMING_NOW.*?currentDma->when = mTimingCurrentTime\(&gba->timing\) \+ 3;"),
    ("MGBA_DMA_EVENT_SCHEDULER_CONSUMER", "src/gba/dma.c",
     r"void GBADMAUpdate\([^)]*\)\s*\{.*?mTimingDeschedule\(&gba->timing, &memory->dmaEvent\);\s*mTimingSchedule\(&gba->timing, &memory->dmaEvent,"),
    ("MGBA_DMA_16BIT_EEPROM_PRIORITY", "src/gba/dma.c",
     r"sourceRegion == GBA_REGION_ROM2_EX && .*?GBASavedataReadEEPROM\(&memory->savedata\).*?destRegion == GBA_REGION_ROM2_EX.*?GBASavedataWriteEEPROM\(&memory->savedata,"),
]


def blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def validate_registry(doc):
    if doc.get("schema") != "xgba.phase1.additive_timing_dma_semantic_candidates.v1":
        raise ValueError("Unexpected additive timing candidate schema")
    if doc.get("pinned_revision") != PIN or doc.get("source_repository") != "mgba-emu/mgba":
        raise ValueError("Source revision mismatch")
    if (doc.get("additional_source_files") != 2 or doc.get("parent_curated_count_unchanged") != 29
            or doc.get("independent_whole_file_approvals") != 0
            or doc.get("phase1_mapping_complete") is not False):
        raise ValueError("Unverified source review count/signoff changed")
    candidates = doc.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise ValueError("Expected two additive source candidates")
    wanted = set(EXPECTED) - {"src/gba/dma.c"}
    seen = set()
    for item in candidates:
        path = item.get("path")
        if path not in wanted or path in seen or item.get("git_blob_sha1") != EXPECTED[path]:
            raise ValueError("Unrecognized, duplicate or changed source candidate")
        if item.get("independent_signoff") is not False or not item.get("unresolved"):
            raise ValueError("Candidate incorrectly signed off or missing review obligations")
        if not item.get("semantic_roles") or not item.get("cross_source_consumers"):
            raise ValueError("Missing source semantics or dependency consumers")
        seen.add(path)
    if seen != wanted:
        raise ValueError("Missing timing source candidate")
    contracts = doc.get("cross_source_contracts")
    if not isinstance(contracts, list) or len(contracts) != 3:
        raise ValueError("Missing cross-source semantic contracts")
    if len({x.get("id") for x in contracts}) != 3:
        raise ValueError("Duplicate semantic contract IDs")
    return True


def self_test(doc):
    validate_registry(doc)
    cases = [
        ("revision", lambda d: d.update(pinned_revision="unknown")),
        ("signoff", lambda d: d.update(independent_whole_file_approvals=1)),
        ("filecount", lambda d: d.update(additional_source_files=3)),
        ("candidatehash", lambda d: d["candidates"][0].update(git_blob_sha1="0"*40)),
        ("candidateapproval", lambda d: d["candidates"][0].update(independent_signoff=True)),
        ("missingconsumer", lambda d: d["candidates"][0].update(cross_source_consumers=[])),
        ("missingcontract", lambda d: d.update(cross_source_contracts=[])),
    ]
    for label, mutate in cases:
        altered = copy.deepcopy(doc)
        mutate(altered)
        try:
            validate_registry(altered)
        except ValueError:
            pass
        else:
            raise AssertionError("Fail-open timing semantic candidate guard: " + label)
    print("Pinned timing/DMA semantic candidate schema: 7 negative controls PASS")


def verify(root, doc):
    validate_registry(doc)
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if revision != PIN:
        raise ValueError("mGBA checkout is not the exact pinned revision")
    sources = {}
    for path, expected in EXPECTED.items():
        data = (root / path).read_bytes()
        if blob_sha(data) != expected:
            raise ValueError("Pinned mGBA Git blob mismatch: " + path)
        sources[path] = data.decode("utf-8", "surrogateescape")
    evidence = []
    for name, path, pattern in CHECKS:
        source = sources[path]
        match = re.search(pattern, source, re.S)
        if not match:
            raise ValueError("Pinned timing/DMA source contract missing: " + name)
        evidence.append({
            "contract_id": name, "source_path": path,
            "source_git_blob_sha1": EXPECTED[path],
            "line_start": source.count("\n", 0, match.start()) + 1,
            "line_end": source.count("\n", 0, match.end()) + 1,
            "matched_source_sha256": hashlib.sha256(
                match.group(0).encode("utf-8", "surrogateescape")).hexdigest(),
            "evidence_status": "PINNED_SOURCE_ASSERTION_ONLY",
            "independent_whole_file_signoff": False,
        })
    return {
        "schema": "xgba.phase1.additive_timing_dma_source_evidence.v1",
        "pinned_mgba_revision": PIN,
        "source_blobs_verified": len(EXPECTED),
        "source_contracts_passed": len(evidence),
        "candidate_files_added": 2,
        "baseline_curated_files_unchanged": 29,
        "independent_whole_file_signoffs": 0,
        "phase1_mapping_complete": False,
        "source_evidence": evidence,
        "limitations": ["No independent whole-file review", "No new native runtime tests",
                        "Not an XGBA compatibility approval"],
    }


if __name__ == "__main__":
    try:
        document = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self_test(document)
        root = Path(sys.argv[1] if len(sys.argv) > 1 else "upstream/mgba")
        result = verify(root, document)
        out = Path("audit-output/mgba_timing_dma_source_evidence.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print("Pinned mGBA timing/DMA: 3/3 exact source blobs, 9/9 source contracts PASS; 0 signoffs")
    except Exception as exc:
        print("Timing/DMA source evidence FAILED:", exc, file=sys.stderr)
        sys.exit(2)
