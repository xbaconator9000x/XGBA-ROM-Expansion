#!/usr/bin/env python3
"""Phase 1: deterministic input-only real-ROM save observation, not a save proof."""
import argparse
import hashlib
import json
import shutil
import struct
import os
import subprocess
from pathlib import Path

TRACE_CASES = ("menu_navigation", "pallet_null_layout", "pallet_valid",
               "pallet_save_navigation", "pallet_save_dense_confirm", "cold_boot")

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def pulse(events, frame, mask, width=2):
    events.extend(((frame, mask), (frame + width, 0)))

def make_schedule(name):
    e = []
    if name == "no_input":
        return e
    if name == "cold_boot":
        return make_schedule("pallet_valid")
    pulse(e, 260, 0x8)  # START
    if name == "title_continue":
        for f in (390, 520, 680, 850, 980):
            pulse(e, f, 0x1)  # A
        pulse(e, 1150, 0x8)
        for f in (1260, 1360, 1460, 1580, 1720, 1860, 2050, 2250):
            pulse(e, f, 0x1)
    elif name == "repeated_confirm":
        for f in range(320, 1140, 36):
            pulse(e, f, 0x1)
        pulse(e, 1250, 0x8)
        for f in range(1330, 2300, 42):
            pulse(e, f, 0x1)
    elif name == "pallet_save_dense_confirm":
        # Same two-step Save cursor, but dense A pulses across both Yes prompts
        # and slow text. These are ordinary controller inputs, never direct calls.
        for f in range(330, 1000, 60):
            pulse(e, f, 0x1)
        pulse(e, 1100, 0x8)
        for f in (1200, 1260):
            pulse(e, f, 0x80)
        for f in range(1540, 3150, 40):
            pulse(e, f, 0x1)
    elif name == "pallet_save_navigation":
        # Source-pinned start menu with no Pokedex/Pokemon flags:
        # BAG, PLAYER, SAVE, OPTION, EXIT => SAVE at cursor index 2.
        for f in range(330, 1000, 60):
            pulse(e, f, 0x1)
        pulse(e, 1100, 0x8)
        for f in (1200, 1260):
            pulse(e, f, 0x80)
        for f in (1540, 1680, 1820, 1960, 2100, 2260):
            pulse(e, f, 0x1)
    elif name in ("menu_navigation", "pallet_valid", "pallet_null_layout"):
        for f in range(330, 1000, 60):
            pulse(e, f, 0x1)
        pulse(e, 1100, 0x8)
        for f in (1200, 1260, 1320, 1380, 1440):
            pulse(e, f, 0x80)  # DOWN
        for f in (1540, 1680, 1820, 1960, 2100, 2260):
            pulse(e, f, 0x1)
    else:
        raise ValueError(name)
    return sorted(e)

def main(a):
    root = Path(a.output)
    root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((Path(a.fixtures) / "fixture_manifest.json").read_text())
    entries = {x["name"]: x for x in manifest["cases"]}
    assert sha(a.rom) == manifest["source_rom_sha256"]
    assert entries["slot0"]["fixture_not_game_generated"]
    results = []
    for name in ("no_input", "title_continue", "repeated_confirm", "menu_navigation",
                 "pallet_null_layout", "pallet_valid", "pallet_save_navigation",
                 "pallet_save_dense_confirm"):
        save = root / (name + ".sav")
        fixture = ("pallet_valid" if name in ("pallet_save_navigation", "pallet_save_dense_confirm") else
                   name if name.startswith("pallet_") else "slot0")
        shutil.copyfile(Path(a.fixtures) / (fixture + ".sav"), save)
        assert sha(save) == entries[fixture]["sha256"]
        schedule = root / (name + ".keys")
        schedule.write_text("".join(f"{f} {keys:03x}\n" for f, keys in make_schedule(name)))
        before = sha(save)
        budget = 3200 if name == "pallet_save_dense_confirm" else 2400
        command = [a.probe, a.rom, str(save), str(schedule), str(budget), a.status, a.counter, a.sb2]
        if name in TRACE_CASES:
            command.extend((a.start_menu_save, a.dialog_do_save, a.try_saving_data,
                            a.title_task, a.init_main_menu, a.execute_main_menu,
                            a.return_to_field, a.continue_saved_game,
                            a.return_field_local, a.overworld, a.cb1_overworld,
                            a.show_start_menu, a.field_get_player_input, a.gmain, a.sb1))
        p = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
        if p.returncode:
            raise RuntimeError(f"{name}: native probe rc={p.returncode}, stderr={p.stderr[-1500:]}")
        lines = [json.loads(line) for line in p.stdout.splitlines() if line.startswith('{"mode":"controller"')]
        assert len(lines) == 1, (name, p.stdout[-500:])
        d = lines[0]
        assert d["frames"] >= budget and d["host_flash_writes"] == 0, (name, d)
        assert d["save_type"] == 3 and d["baseline_frame"] > 0, (name, "Flash1M baseline absent", d)
        assert d["trace_mode"] == (name in TRACE_CASES), (name, d)
        if name in TRACE_CASES:
            assert d["trace_steps"] > 0, (name, "missing instruction trace", d)
            for key in ("start_menu_save_hits", "save_dialog_do_save_hits",
                        "try_saving_data_entry_hits", "first_try_save_arg",
                        "title_task_hits", "init_main_menu_hits",
                        "execute_main_menu_hits", "return_to_field_hits",
                        "continue_saved_game_hits", "return_field_local_hits",
                        "overworld_hits", "cb1_overworld_hits", "show_start_menu_hits",
                        "field_get_player_input_hits", "callback2_overworld_frames",
                        "first_callback2_overworld_frame", "new_start_key_frames",
                        "new_start_key_overworld_frames", "callback2_return_local_frames",
                        "return_local_state_hist", "last_gmain_state", "last_callback2",
                        "saveblock1_map_group", "saveblock1_map_num", "saveblock1_layout_id"):
                assert key in d, (name, key)
        if name == "pallet_valid":
            assert d["field_get_player_input_hits"] > 0 and d["show_start_menu_hits"] > 0, d
        if name == "pallet_save_dense_confirm":
            assert d["start_menu_save_hits"] > 0, ("Save cursor path regressed", d)
            assert d["save_dialog_do_save_hits"] > 0 and d["try_saving_data_entry_hits"] > 0, (
                "Compiled in-game save callsite not observed", d)
            assert d["flash_changed_bytes"] > 0 and d["save_counter"] == 1, (
                "No native Flash transaction/counter increment", d)
        after = sha(save)
        if name == "pallet_save_dense_confirm":
            assert before != after, ("No persisted game-controlled Flash write", before, after)
        record = {
            "case": name, "source_fixture": "synthetic_" + fixture,
            "input_schedule_sha256": sha(schedule), "before_sha256": before,
            "after_sha256": after, "physical_save_changed": before != after,
            "native": d, "game_initiated_save_verified": False,
            "cold_boot_player_state_verified": False,
            "overworld_input_path_observed": bool(d["field_get_player_input_hits"] and d["callback2_overworld_frames"]),
            "save_menu_index_two_attempted": name in ("pallet_save_navigation", "pallet_save_dense_confirm"),
            "interpretation": "Input-driven real-ROM observation. Changed Flash alone is insufficient to prove save callsite or complete game roundtrip.",
            "phase1_gate": "FAIL_INCOMPLETE", "independent_approval": False,
        }
        (root / (name + ".json")).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"case": name, "physical_save_changed": before != after,
                          "flash_changed_bytes": d["flash_changed_bytes"],
                          "first_flash_change_frame": d["first_flash_change_frame"],
                          "save_status": d["save_status"], "save_counter": d["save_counter"],
                          "trace_steps": d["trace_steps"],
                          "start_menu_save_hits": d["start_menu_save_hits"],
                          "save_dialog_do_save_hits": d["save_dialog_do_save_hits"],
                          "try_saving_data_entry_hits": d["try_saving_data_entry_hits"],
                          "title_task_hits": d["title_task_hits"],
                          "init_main_menu_hits": d["init_main_menu_hits"],
                          "execute_main_menu_hits": d["execute_main_menu_hits"],
                          "return_to_field_hits": d["return_to_field_hits"],
                          "continue_saved_game_hits": d["continue_saved_game_hits"],
                          "return_field_local_hits": d["return_field_local_hits"],
                          "overworld_hits": d["overworld_hits"],
                          "cb1_overworld_hits": d["cb1_overworld_hits"],
                          "show_start_menu_hits": d["show_start_menu_hits"],
                          "field_get_player_input_hits": d["field_get_player_input_hits"],
                          "callback2_overworld_frames": d["callback2_overworld_frames"],
                          "first_callback2_overworld_frame": d["first_callback2_overworld_frame"],
                          "new_start_key_frames": d["new_start_key_frames"],
                          "new_start_key_overworld_frames": d["new_start_key_overworld_frames"],
                          "callback2_return_local_frames": d["callback2_return_local_frames"],
                          "return_local_state_hist": d["return_local_state_hist"],
                          "last_gmain_state": d["last_gmain_state"],
                          "last_callback2": d["last_callback2"],
                          "saveblock1_map_group": d["saveblock1_map_group"],
                          "saveblock1_map_num": d["saveblock1_map_num"],
                          "saveblock1_layout_id": d["saveblock1_layout_id"]}),
              flush=True)
        results.append(record)

    # Validate physical Flash written by the compiled game before cold boot.
    # Source-pinned save.c rotates all 14 logical sectors into physical slot 1
    # on the first normal save (counter 1); each sector is 4096 bytes with
    # id/checksum/signature/counter at 0xFF4/0xFF6/0xFF8/0xFFC.
    dense = next(x for x in results if x["case"] == "pallet_save_dense_confirm")
    generated = root / "pallet_save_dense_confirm.sav"
    flash = generated.read_bytes()
    assert len(flash) == 131072, "Game-generated Flash must be 128 KiB"
    ids = []
    for physical in range(14, 28):
        sector = flash[physical * 4096:(physical + 1) * 4096]
        ident, stored_sum, signature, counter = struct.unpack_from("<HHII", sector, 0xFF4)
        assert signature == 0x08012025 and counter == 1, (
            "Game-generated slot1 signature/counter invalid", physical, ident, signature, counter)
        assert 0 <= ident < 14, ("Game-generated sector ID invalid", physical, ident)
        # save.c zero-initializes the sector before copying the sized payload,
        # so a full 0xF80 checksum equals the source-sized checksum.
        words = struct.unpack_from("<992I", sector, 0)
        total = sum(words) & 0xFFFFFFFF
        computed = ((total >> 16) + total) & 0xFFFF
        assert stored_sum == computed, (
            "Game-generated sector checksum mismatch", physical, ident, stored_sum, computed)
        ids.append(ident)
    assert sorted(ids) == list(range(14)), ("Missing/duplicate game-written sectors", ids)
    assert dense["native"]["saveblock2_player_name_u32"] == 0xFFBEBFCD, (
        "Expected synthetic RED player name absent before cold boot", dense["native"])

    # A *new emulator process* loads the physical .sav produced by the real
    # controller-driven TrySavingData path. No host writes and no save-menu
    # confirmations are permitted on this second boot.
    cold = root / "cold_boot_game_generated.sav"
    shutil.copyfile(generated, cold)
    cold_before = sha(cold)
    cold_keys = root / "cold_boot.keys"
    cold_keys.write_text("".join(f"{f} {keys:03x}\n" for f, keys in make_schedule("cold_boot")))
    command = [a.probe, a.rom, str(cold), str(cold_keys), "2400",
               a.status, a.counter, a.sb2,
               a.start_menu_save, a.dialog_do_save, a.try_saving_data,
               a.title_task, a.init_main_menu, a.execute_main_menu,
               a.return_to_field, a.continue_saved_game,
               a.return_field_local, a.overworld, a.cb1_overworld,
               a.show_start_menu, a.field_get_player_input, a.gmain, a.sb1]
    p = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
    if p.returncode:
        raise RuntimeError(f"cold boot: native probe rc={p.returncode}, stderr={p.stderr[-1500:]}")
    records = [json.loads(line) for line in p.stdout.splitlines()
               if line.startswith('{"mode":"controller"')]
    assert len(records) == 1, ("Cold boot missing native result", p.stdout[-500:])
    cb = records[0]
    assert cb["trace_mode"] and cb["trace_steps"] > 0 and cb["frames"] >= 2400
    assert cb["host_flash_writes"] == 0 and cb["save_type"] == 3 and cb["baseline_frame"] > 0
    assert (cb["save_status"], cb["save_counter"]) == (1, 1), (
        "Cold boot did not validate newly written slot", cb)
    assert (cb["saveblock1_map_group"], cb["saveblock1_map_num"],
            cb["saveblock1_layout_id"]) == (3, 0, 78), (
        "Cold boot did not restore authored PalletTown player map", cb)
    assert cb["saveblock2_player_name_u32"] == 0xFFBEBFCD and cb["saveblock2_marker"] == 0xA5, (
        "Cold boot did not recover named player and original payload", cb)
    assert cb["field_get_player_input_hits"] > 0 and cb["callback2_overworld_frames"] > 0, (
        "Cold boot failed to recover playable field", cb)
    assert cb["try_saving_data_entry_hits"] == 0 and cb["flash_changed_bytes"] == 0, (
        "Cold boot control unexpectedly performed a second save", cb)
    assert sha(cold) == cold_before, "Cold boot modified physical save without Save command"
    cold_record = {
        "case": "cold_boot_game_generated",
        "source_fixture": "physical_flash_written_by_compiled_TrySavingData",
        "before_sha256": cold_before, "after_sha256": sha(cold),
        "physical_save_changed": False, "native": cb,
        "slot1_sector_ids": ids,
        "slot1_all_sector_checksums_verified": True,
        "named_player_map_and_field_recovered": True,
        "try_saving_data_return_status_not_traced": True,
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approval": False,
    }
    (root / "cold_boot_game_generated.json").write_text(
        json.dumps(cold_record, indent=2, sort_keys=True) + "\n")
    results.append(cold_record)
    dense["game_controlled_flash_and_coldboot_observed"] = True
    (root / "pallet_save_dense_confirm.json").write_text(
        json.dumps(dense, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "case": "cold_boot_game_generated",
        "physical_save_sha256": cold_before,
        "slot1_sector_ids": ids,
        "save_status": cb["save_status"], "save_counter": cb["save_counter"],
        "player_name_u32": cb["saveblock2_player_name_u32"],
        "map_group": cb["saveblock1_map_group"], "map_num": cb["saveblock1_map_num"],
        "layout_id": cb["saveblock1_layout_id"],
        "field_input_hits": cb["field_get_player_input_hits"],
        "try_saving_data_entry_hits": cb["try_saving_data_entry_hits"],
        "host_flash_writes": cb["host_flash_writes"],
    }), flush=True)

    # Deliberate missing-baseline negative control. The native probe must fail,
    # rather than report zero Flash mutations from an uninitialized baseline.
    bad_env = os.environ.copy()
    bad_env["XGBA_PHASE1_FORCE_MISSING_BASELINE"] = "1"
    p = subprocess.run([a.probe, a.rom, str(cold), str(cold_keys), "180",
                        a.status, a.counter, a.sb2],
                       capture_output=True, text=True, env=bad_env, timeout=120, check=False)
    assert p.returncode != 0 and "Flash1M baseline/final mapping unavailable" in p.stderr, (
        "Missing-baseline negative control did not fail closed", p.returncode, p.stderr[-400:])
    print("Native missing-Flash-baseline negative control rejected as required", flush=True)
    (root / "controller_summary.json").write_text(json.dumps({
        "cases": results, "new_machine_indexed_files": 0,
        "analyst_prepared_complete_file_reviews": 0, "independent_approvals": 0,
        "phase1_gates": "FAIL_INCOMPLETE",
        "limits": ["TrySavingData entry observed but function return/result not yet traced",
                   "Original playable fixture was synthetic, although subsequent Flash was game-written",
                   "Controller schedule not equivalent to human verified gameplay",
                   "No XGBA-expanded ROM interoperability or independent semantic approval"],
    }, indent=2, sort_keys=True) + "\n")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for arg in ("rom", "fixtures", "probe", "status", "counter", "sb2", "output"):
        p.add_argument("--" + arg, required=True)
    for arg in ("start_menu_save", "dialog_do_save", "try_saving_data",
                "title_task", "init_main_menu", "execute_main_menu",
                "return_to_field", "continue_saved_game", "return_field_local",
                "overworld", "cb1_overworld", "show_start_menu",
                "field_get_player_input", "gmain", "sb1"):
        p.add_argument("--" + arg.replace("_", "-"), required=True)
    main(p.parse_args())
