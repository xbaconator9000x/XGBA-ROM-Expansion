#!/usr/bin/env python3
"""Phase 1: pinned IWRAM no-Flash fault at real game TrySavingData entry.

This deliberately uses a host RAM write, NOT an input-only save, and never
writes emulated Flash. Preserve distinction from hardware Flash failure.
"""
import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from phase1_firered_game_controller import make_schedule
from phase1_firered_repeat_save import TRACE_NAMES, sha


def main(a):
    root = Path(a.output)
    root.mkdir(parents=True, exist_ok=True)
    original = root / "pallet_save_dense_confirm.sav"
    first = json.loads((root / "pallet_save_dense_confirm.json").read_text())
    assert first["native"]["first_try_saving_data_return_value"] == 1
    assert first["native"]["save_counter"] == 1
    save = root / "no_flash_ram_fault.sav"
    shutil.copyfile(original, save)
    before = sha(save)
    keys = root / "no_flash_ram_fault.keys"
    keys.write_text("".join(f"{f} {k:03x}\n" for f, k in make_schedule("pallet_save_dense_confirm")))
    command = [a.probe, a.rom, str(save), str(keys), "3200", a.status,
               a.counter, a.sb2] + [getattr(a, key) for key in TRACE_NAMES]
    env = os.environ.copy()
    env["XGBA_PHASE1_FLASH_PRESENT_ADDR"] = a.flash_present
    env["XGBA_PHASE1_SAVE_ATTEMPT_STATUS_ADDR"] = a.attempt_status
    env["XGBA_PHASE1_INJECT_NO_FLASH"] = "1"
    # Fail-closed harness controls: missing and invalid RAM identity.
    for label, invalid in (("missing", None), ("invalid", "0xDEADBEEF"),
                           ("wrong_in_range", a.sb1)):
        bad = env.copy()
        if invalid is None:
            bad.pop("XGBA_PHASE1_FLASH_PRESENT_ADDR")
        else:
            bad["XGBA_PHASE1_FLASH_PRESENT_ADDR"] = invalid
        p = subprocess.run(command, env=bad, capture_output=True, text=True, timeout=900)
        assert p.returncode == 2, (label, p.returncode, p.stderr[-300:])
        expected_error = ("no-Flash fault injection requires" if invalid is None else
                          "invalid pinned field-control diagnostic address" if label == "invalid" else
                          "expected Flash present before fault")
        assert expected_error in p.stderr, (label, p.stderr[-300:])
        assert sha(save) == before, ("negative control modified Flash", label)
    # Same counter-1 fixture and controller schedule, with no host RAM fault.
    positive_save = root / "no_flash_matched_positive.sav"
    shutil.copyfile(original, positive_save)
    positive_command = command.copy()
    positive_command[2] = str(positive_save)
    positive_env = env.copy()
    positive_env.pop("XGBA_PHASE1_INJECT_NO_FLASH")
    positive = subprocess.run(positive_command, env=positive_env,
                              capture_output=True, text=True, timeout=900)
    assert positive.returncode == 0, ("matched positive failed", positive.stderr[-600:])
    positive_records = [json.loads(line) for line in positive.stdout.splitlines()
                        if line.startswith('{"mode":"controller"')]
    assert len(positive_records) == 1
    good = positive_records[0]
    assert good["try_saving_data_entry_hits"] == 1
    assert good["try_saving_data_return_hits"] == 1
    assert good["first_try_saving_data_return_value"] == 1
    assert good["first_try_save_attempt_status"] == 1
    assert good["save_counter"] == 2 and good["flash_changed_bytes"] > 0
    assert sha(positive_save) != before and sha(save) == before
    p = subprocess.run(command, env=env, capture_output=True, text=True, timeout=900)
    if p.returncode:
        raise RuntimeError(f"no-Flash native probe rc={p.returncode}: {p.stderr[-1200:]}")
    records = [json.loads(line) for line in p.stdout.splitlines()
               if line.startswith('{"mode":"controller"')]
    assert len(records) == 1, ("missing native result", p.stdout[-500:])
    n = records[0]
    assert n["host_ram_fault_injection"] is True
    assert n["no_flash_fault_entries"] == 1 and n["no_flash_original"] == 1
    assert n["try_saving_data_entry_hits"] == 1 and n["try_saving_data_return_hits"] == 1
    assert n["first_try_saving_data_return_value"] == 255, (
        "Expected pinned SAVE_STATUS_ERROR=0xFF", n["first_try_saving_data_return_value"])
    assert n["first_try_save_attempt_status"] == 255
    assert n["no_flash_restored"] is True
    assert n["flash_changed_bytes"] == 0 and n["host_flash_writes"] == 0
    assert n["save_counter"] == 1 and n["save_status"] == 1
    assert sha(save) == before, "Faulted save changed physical Flash bytes"
    summary = {
        "case": "game_TrySavingData_no_flash_ram_fault",
        "game_save_entry_and_return_verified": True,
        "returned_SAVE_STATUS_ERROR_0xFF": True,
        "gFlashMemoryPresent_injected_before_game_call": True,
        "injection_type": "host_IWRAM_bool32_not_Flash_bus_write",
        "fault_injection_entries": n["no_flash_fault_entries"],
        "flash_changed_bytes": n["flash_changed_bytes"],
        "physical_save_unchanged": True,
        "counter": n["save_counter"],
        "missing_invalid_and_wrong_symbol_negative_controls": True,
        "matched_no_injection_save_success": True,
        "matched_positive_counter": good["save_counter"],
        "gSaveAttemptStatus_at_return": n["first_try_save_attempt_status"],
        "gFlashMemoryPresent_restored": n["no_flash_restored"],
        "source_provenance": {
            "firered_commit": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
            "src_load_save_c_blob": "8b723dd044c6024b3671bb890b25b56a53f99ec5",
            "src_save_c_blob": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
            "mgba_commit": "fd9dc5c2cbf234365068855851107e762fc6211b",
        },
        "independent_approval": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    (root / "no_flash_ram_fault_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for key in ("rom", "probe", "status", "counter", "sb2", "output", "flash_present", "attempt_status"):
        p.add_argument("--" + key.replace("_", "-"), required=True)
    for key in TRACE_NAMES:
        p.add_argument("--" + key.replace("_", "-"), required=True)
    main(p.parse_args())
