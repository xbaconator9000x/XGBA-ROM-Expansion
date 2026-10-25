#!/usr/bin/env python3
"""Source-pinned mGBA EEPROM/savestate dependency evidence; no signoffs."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
REGISTRY = Path("semantic-snapshots/curated/mgba_eeprom_savestate_additive_candidates_2026-10-26.json")
OUT = Path("audit-output/mgba_eeprom_savestate_source_evidence.json")
EXPECTED = {
    "src/gba/savedata.c": "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
    "include/mgba/internal/gba/savedata.h": "6227be25e8c9d2c1cc14c06ded34389b96138577",
    "src/gba/memory.c": "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
    "src/gba/serialize.c": "a307a51e751f412c64a7378323c56758304ebe85",
    "src/core/timing.c": "cebd619957b0845deedfc03b1e9c89d168861ea1",
}
CONTRACTS = {
    "EEPROM_ROM2_EX_16BIT_DISPATCH": ("src/gba/memory.c:611-625", "src/gba/savedata.c:560-583"),
    "EEPROM_WRITE_SETTLING_SCHEDULER": ("src/gba/savedata.c:524-540", "src/core/timing.c:36-63"),
    "EEPROM_SAVESTATE_RELATIVE_EVENT_RESTORE": ("src/gba/savedata.c:715-756", "src/gba/serialize.c:229-240"),
}
CHECKS = [
    ("EEPROM_SAVEDATA_COMMAND_STRUCT", "include/mgba/internal/gba/savedata.h",
     r"struct GBASavedata \{.*?enum SavedataCommand command;.*?int8_t readBitsRemaining;.*?uint32_t readAddress;.*?uint32_t writeAddress;.*?struct mTimingEvent dust;"),
    ("EEPROM_SETTLE_115000_CYCLES", "src/gba/savedata.c",
     r"#define EEPROM_SETTLE_CYCLES 115000"),
    ("EEPROM_SETTLE_CALLBACK_REGISTERED", "src/gba/savedata.c",
     r"void GBASavedataInit\([^)]*\)\s*\{.*?savedata->dust.priority = 0x70;.*?savedata->dust.callback = _ashesToAshes;"),
    ("EEPROM_AUTODETECT_DEFAULT_512", "src/gba/savedata.c",
     r"void GBASavedataInitEEPROM\([^)]*\)\s*\{.*?GBA_SAVEDATA_AUTODETECT\) \{\s*savedata->type = GBA_SAVEDATA_EEPROM512;"),
    ("EEPROM_GROWTH_512_TO_8K", "src/gba/savedata.c",
     r"static void _ensureEeprom\([^)]*\)\s*\{.*?savedata->type = GBA_SAVEDATA_EEPROM;.*?vf->unmap.*?vf->map"),
    ("EEPROM_WRITE_RESCHEDULE_SETTLING", "src/gba/savedata.c",
     r"void GBASavedataWriteEEPROM\([^)]*\)\s*\{.*?savedata->dirty \|= mSAVEDATA_DIRT_NEW;.*?mTimingDeschedule\(&savedata->p->timing, &savedata->dust\);\s*mTimingSchedule\(&savedata->p->timing, &savedata->dust, EEPROM_SETTLE_CYCLES\);"),
    ("EEPROM_READ_BUSY_BIT", "src/gba/savedata.c",
     r"uint16_t GBASavedataReadEEPROM\([^)]*\)\s*\{.*?if \(!mTimingIsScheduled\(&savedata->p->timing, &savedata->dust\)\) \{\s*return 1;\s*\} else \{\s*return 0;"),
    ("EEPROM_SERIALIZE_REMAINING_SETTLE_CYCLES", "src/gba/savedata.c",
     r"void GBASavedataSerialize\([^)]*\)\s*\{.*?mTimingIsScheduled\(&savedata->p->timing, &savedata->dust\).*?savedata->dust.when - mTimingCurrentTime\(&savedata->p->timing\)"),
    ("EEPROM_DESERIALIZE_RESTORES_EVENT", "src/gba/savedata.c",
     r"void GBASavedataDeserialize\([^)]*\)\s*\{.*?GBASerializedSavedataFlagsIsDustSettling\(flags\).*?mTimingSchedule\(&savedata->p->timing, &savedata->dust, when\);"),
    ("EEPROM_ROM2_EX_READ_PRIORITY", "src/gba/memory.c",
     r"case GBA_REGION_ROM2_EX:.*?GBA_SAVEDATA_EEPROM512\) \{\s*value = GBASavedataReadEEPROM\(&memory->savedata\);"),
    ("EEPROM_ROM2_EX_WRITE_AUTODETECT", "src/gba/memory.c",
     r"case GBA_REGION_ROM2_EX:.*?GBA_SAVEDATA_AUTODETECT\) \{.*?GBASavedataInitEEPROM\(&memory->savedata\);.*?GBASavedataWriteEEPROM\(&memory->savedata, value, 1\);"),
    ("EEPROM_SAVESTATE_ORDER_BEFORE_MATRIX", "src/gba/serialize.c",
     r"GBASavedataDeserialize\(&gba->memory.savedata, state\);\s*if \(gba->memory.matrix.size\) \{\s*GBAMatrixDeserialize\(gba, state\);\s*\}\s*mTimingInterrupt\(&gba->timing\);"),
    ("EEPROM_TIMING_SCHEDULE_REROOT", "src/core/timing.c",
     r"void mTimingSchedule\([^)]*\)\s*\{.*?if \(timing->reroot\) \{\s*previous = &timing->reroot;"),
]


def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def validate(doc):
    if (doc.get("schema") != "xgba.phase1.additive_eeprom_savestate_semantic_candidates.v1"
            or doc.get("source_repository") != "mgba-emu/mgba"
            or doc.get("pinned_revision") != PIN
            or doc.get("parent_curated_count_unchanged") != 29
            or doc.get("additional_source_files") != 2
            or doc.get("independent_whole_file_approvals") != 0
            or doc.get("phase1_mapping_complete") is not False):
        raise ValueError("EEPROM registry schema, source pin or approval count invalid")
    wanted = set(EXPECTED) - {"src/gba/memory.c", "src/gba/serialize.c", "src/core/timing.c"}
    candidates = doc.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise ValueError("Expected two additive EEPROM sources")
    seen = set()
    for item in candidates:
        path = item.get("path")
        if path not in wanted or path in seen or item.get("git_blob_sha1") != EXPECTED[path]:
            raise ValueError("EEPROM source identity changed or duplicated")
        if item.get("independent_signoff") is not False or not item.get("unresolved"):
            raise ValueError("EEPROM candidate falsely approved or missing obligations")
        if not item.get("semantic_roles") or not item.get("cross_source_consumers"):
            raise ValueError("Missing EEPROM semantic roles or consumers")
        lines = item.get("source_lines")
        if not isinstance(lines, list) or len(lines) != 2 or not all(type(x) is int for x in lines) or lines[0] < 1 or lines[1] < lines[0]:
            raise ValueError("Invalid source range")
        for reference in item["cross_source_consumers"]:
            if not isinstance(reference, str) or not re.fullmatch(r"[a-zA-Z0-9_./-]+:[0-9]+-[0-9]+", reference):
                raise ValueError("Invalid source consumer reference")
            if reference.split(":")[0] not in EXPECTED:
                raise ValueError("Consumer outside pinned source set")
        seen.add(path)
    if seen != wanted:
        raise ValueError("Missing EEPROM candidate")
    contracts = doc.get("cross_source_contracts")
    if not isinstance(contracts, list) or len(contracts) != 3:
        raise ValueError("Missing EEPROM cross-source contracts")
    seen = set()
    for item in contracts:
        ident = item.get("id")
        if ident not in CONTRACTS or ident in seen:
            raise ValueError("Unknown or duplicate EEPROM dependency")
        if (item.get("producer"), item.get("consumer")) != CONTRACTS[ident]:
            raise ValueError("EEPROM dependency endpoints changed")
        if item.get("proof_level") != "PINNED_SOURCE_INTERPRETATION_ONLY":
            raise ValueError("False source-contract proof level")
        seen.add(ident)
    if seen != set(CONTRACTS):
        raise ValueError("Missing EEPROM dependency")
    return True


def self_test(doc):
    validate(doc)
    cases = [
        ("pin", lambda x: x.update(pinned_revision="unverified")),
        ("approval", lambda x: x.update(independent_whole_file_approvals=1)),
        ("filecount", lambda x: x.update(additional_source_files=3)),
        ("hash", lambda x: x["candidates"][0].update(git_blob_sha1="0" * 40)),
        ("signoff", lambda x: x["candidates"][0].update(independent_signoff=True)),
        ("obligations", lambda x: x["candidates"][0].update(unresolved=[])),
        ("endpoint", lambda x: x["cross_source_contracts"][0].update(consumer="src/gb/memory.c:1-2")),
        ("proof", lambda x: x["cross_source_contracts"][0].update(proof_level="APPROVED")),
    ]
    for name, mutate in cases:
        changed = copy.deepcopy(doc)
        mutate(changed)
        try:
            validate(changed)
        except ValueError:
            continue
        raise AssertionError("Fail-open EEPROM source review guard: " + name)
    print("EEPROM source review schema: 8 negative controls PASS")


def verify(root, doc):
    validate(doc)
    revision = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if revision != PIN:
        raise ValueError("mGBA source checkout is not pinned")
    sources = {}
    for path, sha in EXPECTED.items():
        raw = (root / path).read_bytes()
        if git_blob_sha(raw) != sha:
            raise ValueError("Pinned Git blob changed: " + path)
        sources[path] = raw.decode("utf-8", "surrogateescape")
    evidence = []
    for ident, path, pattern in CHECKS:
        match = re.search(pattern, sources[path], re.S)
        if not match:
            raise ValueError("Pinned source expression missing: " + ident)
        text = sources[path]
        evidence.append({
            "contract_id": ident,
            "source_path": path,
            "git_blob_sha1": EXPECTED[path],
            "line_start": text.count("\n", 0, match.start()) + 1,
            "line_end": text.count("\n", 0, match.end()) + 1,
            "matched_expression_sha256": hashlib.sha256(match.group(0).encode("utf-8", "surrogateescape")).hexdigest(),
            "status": "PINNED_SOURCE_ASSERTION_ONLY",
            "independent_whole_file_signoff": False,
        })
    return {
        "schema": "xgba.phase1.additive_eeprom_savestate_source_evidence.v1",
        "source_pin": PIN,
        "verified_source_blobs": len(EXPECTED),
        "verified_source_expressions": len(evidence),
        "additional_candidates": 2,
        "original_curated_registry_unchanged": 29,
        "independent_whole_file_approvals": 0,
        "phase1_mapping_complete": False,
        "source_evidence": evidence,
        "limitations": [
            "Source expression checks do not establish all callback interleavings or ABI compatibility",
            "No native emulator regression was run by this verifier",
            "Not a Phase 1 semantic signoff or XGBA runtime implementation",
        ],
    }


if __name__ == "__main__":
    try:
        doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self_test(doc)
        evidence = verify(Path(sys.argv[1] if len(sys.argv) > 1 else "upstream/mgba"), doc)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("Pinned mGBA EEPROM/savestate: 5/5 exact source blobs, " + str(len(CHECKS)) + " source expressions PASS; 0 approvals")
    except Exception as error:
        print("EEPROM source verification FAILED:", error, file=sys.stderr)
        sys.exit(2)
