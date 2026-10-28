#!/usr/bin/env python3
"""Phase 1: native controller movement -> game-written Flash -> cold-boot x/y.

The source-pinned Pallet Town Continue-warp fixture is synthetic.
Movement, the first real save, and cold boot use controller input only.
"""
import argparse
import json
import shutil
import struct
from pathlib import Path

from phase1_firered_repeat_save import TRACE_NAMES, run, sha, verify_game_written_slot

SECTOR_SIZE = 4096


def saved_xy(flash, slot, counter):
    """Pinned save.c sSaveSlotLayout: sector ID1 starts SaveBlock1, pos at +0."""
    ids = verify_game_written_slot(flash, slot, counter)
    assert ids.count(1) == 1, ("Missing SaveBlock1 first sector", ids)
    for physical in range(slot * 14, (slot + 1) * 14):
        sector = flash[physical * SECTOR_SIZE:(physical + 1) * SECTOR_SIZE]
        ident = struct.unpack_from("<H", sector, 0xFF4)[0]
        if ident == 1:
            return struct.unpack_from("<hh", sector)
    raise AssertionError("SaveBlock1 first sector not found")


def assert_native_xy(native, xy, name):
    observed = (native["saveblock1_pos_x"], native["saveblock1_pos_y"])
    assert observed == xy, (name, "emulator SaveBlock1.pos disagrees with Flash", observed, xy)
    assert native["field_get_player_input_hits"] > 0
    assert (native["saveblock1_map_group"], native["saveblock1_map_num"],
            native["saveblock1_layout_id"]) == (3, 0, 78)
    assert native["saveblock2_player_name_u32"] == 0xFFBEBFCD


def main(a):
    root = Path(a.output)
    root.mkdir(parents=True, exist_ok=True)
    fixture = Path(a.fixtures) / "pallet_continue_warp.sav"
    original = fixture.read_bytes()
    assert len(original) == 131072
    # Source-defined SaveBlock2.specialSaveWarpFlags bit0, and SaveBlock1.continueGameWarp.
    assert original[9] & 1, "Continue-warp precondition missing"
    assert struct.unpack_from("<bbbBhh", original, SECTOR_SIZE + 0x0C) == (3, 0, -1, 0, 11, 10)
    plain = (Path(a.fixtures) / "pallet_valid.sav").read_bytes()
    assert (plain[9] & 1) == 0, "No-warp negative fixture unexpectedly set warp bit"
    assert plain != original
    start_xy = (11, 10)

    # Negative control: movement without Save changes runtime coordinates only.
    # A fresh process reloads the original synthetic fixture.
    unsaved = root / "position_move_without_save.sav"
    shutil.copyfile(fixture, unsaved)
    moved = run(a, "position_move_without_save", unsaved, "pallet_move_no_save", 2400)
    m = moved["native"]
    moved_xy = (m["saveblock1_pos_x"], m["saveblock1_pos_y"])
    diagnostic = {
        "case": "position_move_without_save",
        "saved_initial_xy": list(start_xy), "runtime_final_xy": list(moved_xy),
        "first_overworld_xy": [m["first_overworld_pos_x"], m["first_overworld_pos_y"]],
        "new_direction_key_overworld_frames": m["new_direction_key_overworld_frames"],
        "held_direction_key_overworld_frames": m["held_direction_key_overworld_frames"],
        "position_changed_frames": m["position_changed_frames"],
        "first_position_change_frame": m["first_position_change_frame"],
        "field_input_hits": m["field_get_player_input_hits"],
        "locked_overworld_frames": m["locked_overworld_frames"],
        "player_step_hits": m["player_step_hits"],
        "player_step_nonzero_direction_hits": m["player_step_nonzero_direction_hits"],
        "avatar_first_flags": m["avatar_first_flags"],
        "avatar_last_flags": m["avatar_last_flags"],
        "avatar_last_running": m["avatar_last_running"],
        "avatar_last_transition": m["avatar_last_transition"],
        "avatar_last_object_event_id": m["avatar_last_object_event_id"],
        "init_avatar_hits": m["init_avatar_hits"],
        "clear_avatar_hits": m["clear_avatar_hits"],
        "set_avatar_state_hits": m["set_avatar_state_hits"],
        "init_objects_local_hits": m["init_objects_local_hits"],
        "cb2_load_map_hits": m["cb2_load_map_hits"],
        "load_map_steps_hits": m["load_map_steps_hits"],
        "avatar_controllable_frames": m["avatar_controllable_frames"],
        "avatar_prevent_step_frames": m["avatar_prevent_step_frames"],
        "camera_move_hits": m["camera_move_hits"],
        "player_object_changed_frames": m["player_object_changed_frames"],
        "player_object_active_frames": m["player_object_active_frames"],
        "player_object_camera_tracked_frames": m["player_object_camera_tracked_frames"],
        "player_object_is_player_frames": m["player_object_is_player_frames"],
        "player_object_first_xy": [m["player_object_first_x"], m["player_object_first_y"]],
        "player_object_last_xy": [m["player_object_last_x"], m["player_object_last_y"]],
        "player_object_last_action": m["player_object_last_action"],
        "player_object_last_behavior": m["player_object_last_behavior"],
    }
    print(json.dumps(diagnostic, sort_keys=True), flush=True)
    (root / "position_move_without_save_diagnostic.json").write_text(json.dumps(diagnostic, indent=2, sort_keys=True) + "\n")
    assert m["new_direction_key_overworld_frames"] > 0 and m["held_direction_key_overworld_frames"] > 0, (
        "Directional controller keys were not registered in overworld", diagnostic)
    assert moved_xy != start_xy and m["position_changed_frames"] > 0, (
        "Directional inputs registered but no saved-position movement", diagnostic)
    assert m["save_counter"] == 0 and m["try_saving_data_entry_hits"] == 0
    assert m["cb2_load_map_hits"] > 0 and m["init_avatar_hits"] > 0
    assert m["avatar_controllable_frames"] > 0 and m["player_object_active_frames"] > 0
    assert m["flash_changed_bytes"] == 0 and not moved["physical_save_changed"]
    assert unsaved.read_bytes() == original

    unsaved_reload = root / "position_unsaved_coldboot.sav"
    shutil.copyfile(unsaved, unsaved_reload)
    unsaved_cold = run(a, "position_unsaved_coldboot", unsaved_reload,
                       "pallet_stationary_coldboot", 2400)
    assert_native_xy(unsaved_cold["native"], start_xy, "unsaved cold boot")
    assert unsaved_cold["native"]["save_counter"] == 0
    assert unsaved_cold["native"]["try_saving_data_entry_hits"] == 0
    assert unsaved_cold["native"]["flash_changed_bytes"] == 0
    assert not unsaved_cold["physical_save_changed"]

    # Positive: the same initialized movement followed by genuine controller Save
    # must commit changed coordinates to physical sector ID1 in counter1 slot1.
    saved = root / "position_move_then_save.sav"
    shutil.copyfile(fixture, saved)
    changed = run(a, "position_move_then_save", saved, "pallet_move_save", 3200)
    n = changed["native"]
    assert n["start_menu_save_hits"] >= 1 and n["save_dialog_do_save_hits"] >= 1
    assert n["try_saving_data_entry_hits"] >= 1 and n["try_saving_data_return_hits"] >= 1
    assert n["first_try_saving_data_return_value"] == 1
    assert n["save_counter"] == 1 and n["flash_changed_bytes"] > 0
    assert n["cb2_load_map_hits"] > 0 and n["init_avatar_hits"] > 0
    assert n["position_changed_frames"] > 0 and n["avatar_controllable_frames"] > 0
    assert changed["physical_save_changed"] and saved.read_bytes() != original
    flash = saved.read_bytes()
    assert flash[:14 * SECTOR_SIZE] == original[:14 * SECTOR_SIZE], (
        "Game-written slot1 modified original synthetic slot0")
    saved_pos = saved_xy(flash, 1, 1)
    assert saved_pos != start_xy, ("Save did not preserve a changed player position", saved_pos, start_xy)
    assert_native_xy(n, saved_pos, "game-written SaveBlock1")

    # New emulator, input-only Continue, NO movement and NO save: recovery
    # must select counter1 and reproduce the precise game-written coordinates.
    fresh = root / "position_move_save_coldboot.sav"
    shutil.copyfile(saved, fresh)
    cold = run(a, "position_move_save_coldboot", fresh,
               "pallet_stationary_coldboot", 2400)
    r = cold["native"]
    assert (r["save_status"], r["save_counter"]) == (1, 1)
    assert_native_xy(r, saved_pos, "cold-boot recovered position")
    assert r["try_saving_data_entry_hits"] == 0 and r["flash_changed_bytes"] == 0
    assert not cold["physical_save_changed"]
    assert fresh.read_bytes() == flash

    summary = {
        "initial_synthetic_warp_xy": list(start_xy),
        "unsaved_runtime_xy": list(moved_xy),
        "unsaved_coldboot_xy": [unsaved_cold["native"]["saveblock1_pos_x"],
                               unsaved_cold["native"]["saveblock1_pos_y"]],
        "game_written_counter1_saved_xy": list(saved_pos),
        "fresh_coldboot_counter1_xy": [r["saveblock1_pos_x"], r["saveblock1_pos_y"]],
        "game_save_try_saving_data_return_ok": True,
        "unsaved_movement_did_not_persist": True,
        "fresh_emulator_player_xy_roundtrip": True,
        "no_host_flash_writes": True,
        "initial_playable_fixture_synthetic": True,
        "source_proven_continue_warp_precondition": True,
        "native_game_written_sector_ids": verify_game_written_slot(flash, 1, 1),
        "independent_approval": False,
        "phase1_gate": "FAIL_INCOMPLETE",
        "source_provenance": {
            "firered_commit": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
            "include_global_h_blob": "77155b09014aa854fcf87260e6ad2969e222da53",
            "src_save_c_blob": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
            "src_fieldmap_c_blob": "41567772299000ba5855419e5c39ad9373a34c20",
            "src_fieldmap_c_pos_update": "CameraMove",
            "src_field_camera_c_blob": "88f94bff08ef951523facf2b579fbc3d4d8455b2",
            "src_field_camera_c_caller": "CameraUpdate",
        },
    }
    (root / "position_roundtrip_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for k in ("rom", "probe", "status", "counter", "sb2", "fixtures", "output"):
        p.add_argument("--" + k, required=True)
    for k in TRACE_NAMES:
        p.add_argument("--" + k.replace("_", "-"), required=True)
    main(p.parse_args())
