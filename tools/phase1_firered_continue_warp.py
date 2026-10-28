#!/usr/bin/env python3
"""Source-pinned synthetic Continue-warp precondition -> native avatar/movement test.

This is a controlled synthetic SaveBlock2 warp flag and SaveBlock1 WarpData
fixture. All subsequent gameplay is emulated controller input, not RAM writes.
"""
import argparse
import json
import shutil
import struct
from pathlib import Path
from phase1_firered_repeat_save import TRACE_NAMES, run, sha

def main(a):
    root = Path(a.output)
    root.mkdir(parents=True, exist_ok=True)
    original = (Path(a.fixtures) / "pallet_continue_warp.sav").read_bytes()
    assert len(original) == 131072
    # Source global.h SaveBlock2 specialSaveWarpFlags +0x009, SaveBlock1
    # continueGameWarp +0x00C; save_location.h CONTINUE_GAME_WARP = 1.
    assert original[9] & 1
    assert struct.unpack_from("<bbbBhh", original, 4096 + 0x0C) == (3, 0, -1, 0, 11, 10)
    # Negative: ordinary fixture MUST NOT claim the forced warp precondition.
    plain = (Path(a.fixtures) / "pallet_valid.sav").read_bytes()
    assert (plain[9] & 1) == 0
    assert plain != original
    target = root / "continue_warp_movement.sav"
    target.write_bytes(original)
    witness = run(a, "continue_warp_movement", target, "pallet_move_no_save", 2400)
    n = witness["native"]
    diagnostic = {
        "fixture_is_synthetic": True,
        "source_proven_warp_flag": True,
        "normal_fixture_warp_flag_absent": True,
        "cb2_load_map_hits": n["cb2_load_map_hits"],
        "load_map_steps_hits": n["load_map_steps_hits"],
        "init_objects_local_hits": n["init_objects_local_hits"],
        "init_avatar_hits": n["init_avatar_hits"],
        "avatar_controllable_frames": n["avatar_controllable_frames"],
        "player_object_active_frames": n["player_object_active_frames"],
        "position_changed_frames": n["position_changed_frames"],
        "initial_xy": [11, 10],
        "runtime_xy": [n["saveblock1_pos_x"], n["saveblock1_pos_y"]],
        "physical_flash_unchanged": not witness["physical_save_changed"],
        "independent_approval": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    (root / "continue_warp_diagnostic.json").write_text(json.dumps(diagnostic, indent=2, sort_keys=True)+"\n")
    print(json.dumps(diagnostic, sort_keys=True), flush=True)
    assert n["cb2_load_map_hits"] > 0 and n["load_map_steps_hits"] > 0, ("Continue warp failed to select compiled map loader", diagnostic)
    assert n["init_objects_local_hits"] > 0 and n["init_avatar_hits"] > 0, ("Map loader failed to create player avatar", diagnostic)
    assert n["avatar_controllable_frames"] > 0 and n["player_object_active_frames"] > 0, ("Player avatar not controllable/active", diagnostic)
    assert n["position_changed_frames"] > 0 and (n["saveblock1_pos_x"], n["saveblock1_pos_y"]) != (11, 10), ("Controller input did not move initialized player", diagnostic)
    assert n["try_saving_data_entry_hits"] == 0 and n["flash_changed_bytes"] == 0
    assert not witness["physical_save_changed"] and target.read_bytes() == original

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ("rom", "probe", "status", "counter", "sb2", "fixtures", "output"):
        p.add_argument("--"+key, required=True)
    for key in TRACE_NAMES:
        p.add_argument("--"+key.replace("_","-"), required=True)
    main(p.parse_args())
