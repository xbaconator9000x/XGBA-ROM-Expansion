#!/usr/bin/env python3
"""Phase 1: deterministic input-only real-ROM save observation, not a save proof."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

TRACE_CASES = ("menu_navigation", "pallet_null_layout", "pallet_valid",
               "pallet_save_navigation", "pallet_save_dense_confirm")

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def pulse(events, frame, mask, width=2):
    events.extend(((frame, mask), (frame + width, 0)))

def make_schedule(name):
    e = []
    if name == "no_input":
        return e
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
        after = sha(save)
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
    (root / "controller_summary.json").write_text(json.dumps({
        "cases": results, "new_machine_indexed_files": 0,
        "analyst_prepared_complete_file_reviews": 0, "independent_approvals": 0,
        "phase1_gates": "FAIL_INCOMPLETE",
        "limits": ["No TrySavingData PC-entry witness", "No demonstrated game-generated cold-boot player-state recovery",
                   "Synthetic save source", "Controller schedule not equivalent to human verified gameplay"],
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
