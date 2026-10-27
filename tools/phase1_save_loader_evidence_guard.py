#!/usr/bin/env python3
"""Fail-closed independent Phase 1 classification of pinned real-ROM probe evidence.

This guard does NOT prove loader reachability, correct game saves, or semantic approval.
"""
import argparse
import hashlib
import json
from pathlib import Path

SAVE_C_BLOB = "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c"
SAVE_H_BLOB = "87fb9b615b434b58823d15688056695acda9feab"
HEAD = "b6f0cee6a4b5ec25c2eb39eaf4340b65e8da10d8"
RUN = 40525408728
JOB = 122263516059
CLASSIFICATION = "FRAME_ADVANCE_AND_HOST_FLASH_ONLY"
# name -> mode, frames, mGBA save type, FireRed status, counter, physical byte
KNOWN = {
    "empty": ("probe", 180, 3, 0, 0, 255),
    "slot0": ("probe", 180, 3, 0, 0, 0),
    "both": ("probe", 180, 3, 0, 0, 0),
    "malformed_id14": ("probe", 180, 3, 0, 0, 0),
    "mixed_counters": ("probe", 180, 3, 0, 0, 0),
    "older_slot_fallback": ("probe", 180, 3, 0, 0, 0),
    "flash_program": ("program", 183, 3, 0, 0, 255),
    "flash_verify": ("verify", 180, 3, 0, 0, 90),
    "changed_header": ("probe", 180, 3, 0, 0, 255),
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def git_blob_sha1(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def function_body(source, definition, next_definition):
    start = source.find(definition)
    require(start >= 0, "missing exact function definition: " + definition)
    end = source.find(next_definition, start + len(definition))
    require(end > start, "missing following function boundary: " + next_definition)
    return source[start:end]

def verify_pinned_sources(save_c_raw, save_h_raw):
    require(git_blob_sha1(save_c_raw) == SAVE_C_BLOB, "src/save.c Git blob mismatch")
    require(git_blob_sha1(save_h_raw) == SAVE_H_BLOB, "include/save.h Git blob mismatch")
    c = save_c_raw.decode("utf-8")
    h = save_h_raw.decode("utf-8")
    for status in ("#define SAVE_STATUS_EMPTY    0", "#define SAVE_STATUS_OK       1",
                   "#define NUM_SECTORS_PER_SLOT         14"):
        require(status in h, "missing pinned save ABI anchor: " + status)
    valid = function_body(c, "static u8 GetSaveValidStatus(const struct SaveSectorLocation *locations)\n{",
                          "static u8 TryLoadSaveSector(")
    copy = function_body(c, "static u8 CopySaveSlotData(u16 sectorId, const struct SaveSectorLocation *locations)\n{",
                         "static u8 GetSaveValidStatus(const struct SaveSectorLocation *locations)\n{")
    loader = function_body(c, "u8 LoadGameSave(u8 saveType)\n{", "u32 TryReadSpecialSaveSector(")
    require(valid.count("locations[gSaveDataBufferPtr->id].size") == 2,
            "expected two unchecked save-slot index expressions")
    require("locations[id].size" in copy and "locations[id].data" in copy,
            "expected copy path indexing by unvalidated sector id")
    require("result = TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations);" in loader,
            "missing normal save-loader call")
    require("gSaveFileStatus = result;" in loader, "missing save status assignment")
    # This is a *source-level risk*, not a witnessed runtime out-of-bounds read.
    return {"source_pin_verified": True, "unvalidated_sector_id_index_risk": True}

def verify_observations(data):
    require(data.get("schema") == "xgba.phase1.independent_real_rom_probe_observations.v1",
            "wrong evidence schema")
    require(data.get("run_id") == RUN and data.get("job_id") == JOB and
            data.get("head_sha") == HEAD, "run/job/exact-head mismatch")
    require(data.get("classification") == CLASSIFICATION, "unsupported proof classification")
    require(data.get("independent_approvals") == 0, "fabricated approval count")
    pins = data.get("source_pins", {})
    require(pins.get("src/save.c") == SAVE_C_BLOB and
            pins.get("include/save.h") == SAVE_H_BLOB and
            pins.get("pret/pokefirered") == "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
            "source identity mismatch")
    rows = data.get("observations")
    require(isinstance(rows, list) and len(rows) == len(KNOWN), "missing/extra observations")
    seen = set()
    for row in rows:
        require(isinstance(row, dict), "malformed observation")
        name = row.get("case_name")
        require(name in KNOWN and name not in seen, "unknown or duplicate case")
        seen.add(name)
        values = tuple(row.get(k) for k in
                       ("mode", "frames", "save_type", "save_status", "save_counter", "flash_byte_40"))
        require(values == KNOWN[name], "observation differs from pinned CI job log: " + name)
    require(seen == set(KNOWN), "incomplete coverage")
    # A constant 0/0 status/counter across valid and malformed fixtures cannot
    # distinguish game-side loader outcomes. Frame advancement is not entry proof.
    return {
        "classification": CLASSIFICATION,
        "cases_verified_against_job_log": len(seen),
        "loader_entry_return_witnessed": False,
        "game_side_save_reload_verified": False,
        "malformed_id_runtime_behavior_verified": False,
        "independent_approvals_added": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save-c", type=Path, required=True)
    parser.add_argument("--save-h", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    args = parser.parse_args()
    result = verify_pinned_sources(args.save_c.read_bytes(), args.save_h.read_bytes())
    result.update(verify_observations(json.loads(args.observations.read_text())))
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
