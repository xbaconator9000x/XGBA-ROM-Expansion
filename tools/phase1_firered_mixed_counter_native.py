#!/usr/bin/env python3
"""Phase 1: native FireRed mixed-counter last-sector selection, not a safety approval."""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

import phase1_firered_slot_counter_coherence as source_contract

SECTOR = 4096
SIGNATURE = 0x08012025
PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PROFILES = {
    "mixed_counter_tail0": ([1] * 13 + [0], 0, 0xA5),
    "mixed_counter_tail1": ([2] * 13 + [1], 1, 0x5A),
    "mixed_counter_tail3": ([1] * 13 + [3], 3, 0x5A),
    "mixed_counter_all_sectors": ([1] * 13 + [3], 3, 0x5A),
}

def require(condition, detail):
    if not condition:
        raise AssertionError(detail)

def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def check_fixture(raw, profile, all_sectors=False):
    counters, _, _ = profile
    require(len(raw) == 32 * SECTOR, "physical Flash1M length changed")
    for slot in (0, 1):
        for i in range(14):
            base = (slot * 14 + i) * SECTOR
            ident, check, signature, counter = struct.unpack_from("<HHII", raw, base + 0xFF4)
            expected_counter = 0 if slot == 0 else counters[i]
            expected_marker = ((0xA5 if slot == 0 else 0x5A) if i == 0
                               else ((0x40+i if slot == 0 else
                                      (0xED if i == 13 else 0x80+i))
                                     if all_sectors else 0))
            require(ident == i, f"sector ID drift slot={slot} i={i}: {ident}")
            require(signature == SIGNATURE, f"signature drift slot={slot} i={i}")
            require(counter == expected_counter, f"counter drift slot={slot} i={i}: {counter}")
            require(raw[base + (0xB80 if i == 0 else 0x100)] == expected_marker, f"payload marker drift slot={slot} i={i}")
            # All other payload bytes are zero in this deliberately synthetic fixture.
            require(check == expected_marker, f"checksum drift slot={slot} i={i}")
    return True

def check_trace(d, expected, all_sectors=False):
    _, counter, marker = expected
    require(d.get("mode") == "trace", "missing native trace mode")
    require(d.get("frames", 0) >= 180 and d.get("trace_steps", 0) > 0, "native execution missing")
    require(d.get("load_game_save_arg") == 0, "not SAVE_NORMAL")
    for name in ("load_game_save_entry_hits", "get_save_valid_status_entry_hits",
                 "copy_save_slot_data_entry_hits"):
        require(d.get(name, 0) >= 1, "compiled function not reached: " + name)
    require(d.get("save_status") == 1, "unexpected native status")
    require(d.get("save_counter") == counter, "last-sector counter not selected")
    require(d.get("saveblock2_filler_marker") == marker, "wrong physical payload slot")
    require(0x02000000 <= d.get("saveblock2_ptr", 0) < 0x02040000,
            "SaveBlock2 pointer outside EWRAM")
    if all_sectors:
        require(0x02000000 <= d.get("saveblock1_ptr", 0) < 0x02040000,
                "SaveBlock1 pointer outside EWRAM")
        require(0x02000000 <= d.get("pokemon_storage_ptr", 0) < 0x02040000,
                "storage pointer outside EWRAM")
        require(d.get("load_game_save_entry_hits", 0) >= 2, "second title loader not observed")
        require(d.get("copy_save_slot_data_entry_hits", 0) >= 2, "second title copy not observed")
        require(d.get("storage_ready_copy_hits", 0) >= 1, "no initialized-storage copy")
        require(0x02000000 <= d.get("second_loader_storage_ptr", 0) < 0x02040000,
                "second loader storage pointer not EWRAM")
        require(0x02000000 <= d.get("second_copy_storage_ptr", 0) < 0x02040000,
                "second copy storage pointer not EWRAM")
        expected_markers = [0x5A] + [0x80+i for i in range(1, 13)] + [0xED]
        require(d.get("saveblock_sector_markers") == expected_markers,
                "native reconstructed 14-sector payload differs from physical slot1")
    return True

def rejected(callback):
    try:
        callback()
    except (AssertionError, ValueError):
        return True
    raise AssertionError("negative control escaped validation")

def main():
    ap = argparse.ArgumentParser()
    for name in ("probe", "rom", "fixtures", "output", "status", "counter",
                 "loader", "valid", "copy", "sb2", "sb1", "storage", "firered-source"):
        ap.add_argument("--" + name, required=True)
    a = ap.parse_args()
    source = Path(a.firered_source)
    raw_save = (source / "src/save.c").read_bytes()
    raw_header = (source / "include/save.h").read_bytes()
    require(git_blob(raw_save) == source_contract.BLOB_SAVE, "pinned src/save.c blob drift")
    require(git_blob(raw_header) == source_contract.BLOB_HEADER, "pinned include/save.h blob drift")
    anchors = source_contract.contract(raw_save.decode(), raw_header.decode())
    require(anchors >= 10, "save-loader source dependency closure weakened")
    fixtures = Path(a.fixtures)
    manifest = json.loads((fixtures / "fixture_manifest.json").read_text())
    rom_hash = hashlib.sha256(Path(a.rom).read_bytes()).hexdigest()
    require(rom_hash == manifest["source_rom_sha256"], "pinned ROM SHA drift")
    records = {r["name"]: r for r in manifest["cases"]}
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    controls = 0
    for name, profile in PROFILES.items():
        raw = (fixtures / (name + ".sav")).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == records[name]["sha256"],
                name + " fixture manifest mismatch")
        all_sectors = name == "mixed_counter_all_sectors"
        check_fixture(raw, profile, all_sectors)
        # Five independent negative controls for each physical fixture.
        for offset, fmt, value in (
            (27 * SECTOR + 0xFFC, "<I", 77),     # last sector counter
            (27 * SECTOR + 0xFF8, "<I", 0),      # signature
            (27 * SECTOR + 0xFF6, "<H", 99),     # checksum
            (27 * SECTOR + 0xFF4, "<H", 14),     # sector ID
            (14 * SECTOR + 0xB80, "<B", 0),      # slot1 marker
        ):
            altered = bytearray(raw)
            struct.pack_into(fmt, altered, offset, value)
            require(rejected(lambda data=altered: check_fixture(data, profile, all_sectors)),
                    "offline mutation accepted")
            controls += 1
        if all_sectors:
            for physical in (0, 1):
                for i in range(1, 14):
                    altered = bytearray(raw)
                    altered[(physical*14+i)*SECTOR+0x100] ^= 1
                    require(rejected(lambda data=altered: check_fixture(data, profile, True)),
                            "per-sector physical payload mutation escaped")
                    controls += 1
        sav = out / ("trace_" + name + ".sav")
        sav.write_bytes(raw)
        before = hashlib.sha256(sav.read_bytes()).hexdigest()
        command = [a.probe, a.rom, str(sav), "trace", a.status, a.counter,
                   a.loader, a.valid, a.copy, a.sb2]
        if all_sectors:
            command.extend([a.sb1, a.storage])
        proc = subprocess.run(command, text=True, capture_output=True, timeout=240, check=False)
        require(proc.returncode == 0, f"{name}: native rc={proc.returncode}: {proc.stderr[-600:]}")
        traces = [json.loads(line) for line in proc.stdout.splitlines()
                  if line.startswith('{"mode":"trace"')]
        require(len(traces) == 1, f"{name}: expected one actual native trace")
        d = traces[0]
        check_trace(d, profile, all_sectors)
        require(hashlib.sha256(sav.read_bytes()).hexdigest() == before,
                name + ": native loader unexpectedly changed physical Flash")
        for key, value in (
            ("save_counter", 99), ("saveblock2_filler_marker", 0),
            ("get_save_valid_status_entry_hits", 0), ("save_status", 255),
        ):
            altered = dict(d)
            altered[key] = value
            require(rejected(lambda record=altered: check_trace(record, profile, all_sectors)),
                    "native trace mutation accepted")
            controls += 1
        if all_sectors:
            for field in ("second_loader_storage_ptr", "second_copy_storage_ptr",
                          "storage_ready_copy_hits"):
                altered = dict(d)
                altered[field] = 0
                require(rejected(lambda record=altered: check_trace(record, profile, True)),
                        "second-load pointer/control mutation escaped")
                controls += 1
            for i in range(14):
                altered = dict(d)
                altered["saveblock_sector_markers"] = list(d["saveblock_sector_markers"])
                altered["saveblock_sector_markers"][i] ^= 1
                require(rejected(lambda record=altered: check_trace(record, profile, True)),
                        "per-sector native memory mutation escaped")
                controls += 1
        cases.append({
            "case": name, "physical_slot0_counters": [0] * 14,
            "physical_slot1_counters": profile[0], "native_status": d["save_status"],
            "native_counter": d["save_counter"],
            "native_saveblock2_marker": d["saveblock2_filler_marker"],
            "native_loader_entries": d["load_game_save_entry_hits"],
            "native_validator_entries": d["get_save_valid_status_entry_hits"],
            "native_copy_entries": d["copy_save_slot_data_entry_hits"],
            "physical_flash_unchanged": True, "synthetic_fixture": True,
            "all_14_payload_sections_observed": all_sectors,
            "native_sector_markers": d.get("saveblock_sector_markers") if all_sectors else None,
        })
        print(json.dumps(cases[-1], sort_keys=True), flush=True)
    report = {
        "status": "PINNED_NATIVE_MIXED_COUNTER_SELECTION_OBSERVED",
        "source_revision": PIN,
        "source_blobs": {"src/save.c": source_contract.BLOB_SAVE,
                         "include/save.h": source_contract.BLOB_HEADER},
        "source_anchor_checks": anchors, "negative_controls_rejected": controls,
        "cases": cases, "limitations": [
            "Synthetic checksum-valid sector metadata, not naturally occurring interrupted saves.",
            "Native FireRed/mGBA loader selection, not a proof of arbitrary malformed-save safety.",
            "No in-game write in these cases; no hardware power-loss durability evidence.",
            "No independent semantic approval; all Phase 1 gates FAIL_INCOMPLETE.",
        ], "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0,
    }
    (out / "mixed_counter_native.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    main()
