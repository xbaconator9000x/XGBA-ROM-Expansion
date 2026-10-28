#!/usr/bin/env python3
"""Phase 1: real second game save, fresh-process reload, and post-save corruption control.

Input-only mGBA controller navigation. No host Flash bus writes. The first
playable Pallet Town fixture was synthetic; this tests two subsequent genuine
FireRed TrySavingData transactions, not human new-game progression.
"""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

from phase1_firered_game_controller import make_schedule

SECTOR_SIZE = 4096
FLASH_SIZE = 131072
SIGNATURE = 0x08012025
TRACE_NAMES = (
    "start_menu_save", "dialog_do_save", "try_saving_data", "title_task",
    "init_main_menu", "execute_main_menu", "return_to_field",
    "continue_saved_game", "return_field_local", "overworld",
    "cb1_overworld", "show_start_menu", "field_get_player_input", "gmain", "sb1",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_game_written_slot(flash, slot, expected_counter):
    assert len(flash) == FLASH_SIZE
    ids = []
    for physical in range(slot * 14, (slot + 1) * 14):
        sector = flash[physical * SECTOR_SIZE:(physical + 1) * SECTOR_SIZE]
        ident, checksum, signature, counter = struct.unpack_from("<HHII", sector, 0xFF4)
        assert signature == SIGNATURE and counter == expected_counter, (
            "Bad native sector signature/counter", physical, ident, signature, counter)
        assert 0 <= ident < 14, ("Invalid native sector ID", physical, ident)
        total = sum(struct.unpack_from("<992I", sector, 0)) & 0xFFFFFFFF
        computed = ((total >> 16) + total) & 0xFFFF
        assert checksum == computed, (
            "Native sector checksum mismatch", physical, ident, checksum, computed)
        ids.append(ident)
    assert sorted(ids) == list(range(14)), ("Duplicate/missing sector IDs", slot, ids)
    return ids


def run(a, name, save, schedule_name, budget):
    keys_path = Path(a.output) / (name + ".keys")
    keys_path.write_text("".join(
        f"{frame} {keys:03x}\n" for frame, keys in make_schedule(schedule_name)))
    command = [a.probe, a.rom, str(save), str(keys_path), str(budget),
               a.status, a.counter, a.sb2] + [getattr(a, key) for key in TRACE_NAMES]
    before = sha(save)
    proc = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
    if proc.returncode:
        raise RuntimeError(f"{name}: native rc={proc.returncode}: {proc.stderr[-1800:]}")
    lines = [json.loads(line) for line in proc.stdout.splitlines()
             if line.startswith('{"mode":"controller"')]
    assert len(lines) == 1, (name, "Missing unique native result", proc.stdout[-500:])
    native = lines[0]
    after = sha(save)
    assert native["trace_mode"] and native["trace_steps"] > 0 and native["frames"] >= budget, (name, native)
    assert native["save_type"] == 3 and native["baseline_frame"] > 0, (name, native)
    assert native["host_flash_writes"] == 0, (name, native)
    record = {
        "case": name, "native": native, "before_sha256": before,
        "after_sha256": after, "physical_save_changed": before != after,
        "schedule_sha256": sha(keys_path), "synthetic_initial_player_fixture": True,
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approval": False,
    }
    (Path(a.output) / (name + ".json")).write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "case": name, "status": native["save_status"], "counter": native["save_counter"],
        "try_save_entries": native["try_saving_data_entry_hits"],
        "try_save_returns": native["try_saving_data_return_hits"],
        "return_value": native["first_try_saving_data_return_value"],
        "flash_changed_bytes": native["flash_changed_bytes"],
        "physical_save_changed": before != after,
        "field_input_hits": native["field_get_player_input_hits"],
    }), flush=True)
    return record


def main(a):
    root = Path(a.output)
    root.mkdir(parents=True, exist_ok=True)
    first = root / "pallet_save_dense_confirm.sav"
    first_evidence = json.loads((root / "pallet_save_dense_confirm.json").read_text())
    assert first_evidence["native"]["first_try_saving_data_return_value"] == 1
    assert first_evidence["native"]["save_counter"] == 1
    assert first_evidence["physical_save_changed"]
    assert first_evidence["native"]["host_flash_writes"] == 0
    first_slot = verify_game_written_slot(first.read_bytes(), 1, 1)

    repeated = root / "second_game_save.sav"
    shutil.copyfile(first, repeated)
    repeat = run(a, "second_game_save", repeated, "pallet_save_dense_confirm", 3200)
    r = repeat["native"]
    assert r["start_menu_save_hits"] >= 1 and r["save_dialog_do_save_hits"] >= 1
    assert r["try_saving_data_entry_hits"] >= 1 and r["try_saving_data_return_hits"] >= 1
    assert r["first_try_saving_data_return_value"] == 1, ("Second save did not return OK", r)
    assert r["save_counter"] == 2 and r["flash_changed_bytes"] > 0, (
        "Second save counter/Flash mutation missing", r)
    assert repeat["physical_save_changed"], "Second game save did not persist to physical Flash"
    second_flash = repeated.read_bytes()
    second_slot = verify_game_written_slot(second_flash, 0, 2)
    assert second_flash[14 * SECTOR_SIZE:] == first.read_bytes()[14 * SECTOR_SIZE:], (
        "Second slot0 save unexpectedly modified older slot1 bytes")

    cold = root / "second_game_save_coldboot.sav"
    shutil.copyfile(repeated, cold)
    recovered = run(a, "second_game_save_coldboot", cold, "cold_boot", 2400)
    c = recovered["native"]
    assert (c["save_status"], c["save_counter"]) == (1, 2), (
        "Fresh emulator did not select second game-written slot", c)
    assert (c["saveblock1_map_group"], c["saveblock1_map_num"],
            c["saveblock1_layout_id"]) == (3, 0, 78)
    assert c["saveblock2_player_name_u32"] == 0xFFBEBFCD
    assert c["field_get_player_input_hits"] > 0 and c["callback2_overworld_frames"] > 0
    assert c["try_saving_data_entry_hits"] == 0 and c["flash_changed_bytes"] == 0
    assert not recovered["physical_save_changed"], "Cold boot unexpectedly wrote Flash"

    # Negative control: simulate one corrupted checksum AFTER a completed second
    # save. This is not an actual interrupted in-flight Flash transaction.
    damaged = root / "second_save_corrupt_slot0_checksum.sav"
    altered = bytearray(second_flash)
    altered[0xFF6] ^= 1
    damaged.write_bytes(altered)
    assert damaged.read_bytes() != second_flash
    try:
        verify_game_written_slot(damaged.read_bytes(), 0, 2)
    except AssertionError:
        pass
    else:
        raise AssertionError("Corrupted slot0 checksum was not detected by offline validator")
    fallback = run(a, "second_save_corrupt_slot0_checksum", damaged, "cold_boot", 2400)
    f = fallback["native"]
    assert f["try_saving_data_entry_hits"] == 0 and f["flash_changed_bytes"] == 0
    assert not fallback["physical_save_changed"], "Corrupt-slot cold boot modified physical save"
    fallback_observed = (f["save_counter"] == 1 and
                         f["saveblock1_map_group"] == 3 and
                         f["saveblock1_map_num"] == 0 and
                         f["saveblock1_layout_id"] == 78 and
                         f["saveblock2_player_name_u32"] == 0xFFBEBFCD and
                         f["field_get_player_input_hits"] > 0)
    assert fallback_observed and f["save_status"] == 255, (
        "Corrupted newest slot did not recover the older game-written slot", f)
    summary = {
        "first_save_slot1_ids": first_slot,
        "second_save_slot0_ids": second_slot,
        "second_game_save_return_ok": True,
        "second_game_save_physical_flash_persisted": True,
        "second_save_fresh_process_player_state_recovered": True,
        "corrupt_newest_slot_fallback_observed": fallback_observed,
        "corrupt_newest_slot_save_status": f["save_status"],
        "corrupt_newest_slot_counter": f["save_counter"],
        "corruption_is_post_save_surrogate_not_real_power_loss": True,
        "synthetic_initial_player_fixture": True,
        "host_flash_writes": 0,
        "independent_approval": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    (root / "repeated_save_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("rom", "probe", "status", "counter", "sb2", "output"):
        parser.add_argument("--" + name, required=True)
    for name in TRACE_NAMES:
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    main(parser.parse_args())
