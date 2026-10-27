#!/usr/bin/env python3
"""Phase 1: deterministic input-only real-ROM save observation, not a save proof."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

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
    elif name == "menu_navigation":
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
    for name in ("no_input", "title_continue", "repeated_confirm", "menu_navigation"):
        save = root / (name + ".sav")
        shutil.copyfile(Path(a.fixtures) / "slot0.sav", save)
        assert sha(save) == entries["slot0"]["sha256"]
        schedule = root / (name + ".keys")
        schedule.write_text("".join(f"{f} {keys:03x}\n" for f, keys in make_schedule(name)))
        before = sha(save)
        command = [a.probe, a.rom, str(save), str(schedule), "2400", a.status, a.counter, a.sb2]
        p = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
        if p.returncode:
            raise RuntimeError(f"{name}: native probe rc={p.returncode}, stderr={p.stderr[-1500:]}")
        lines = [json.loads(line) for line in p.stdout.splitlines() if line.startswith('{"mode":"controller"')]
        assert len(lines) == 1, (name, p.stdout[-500:])
        d = lines[0]
        assert d["frames"] >= 2400 and d["host_flash_writes"] == 0, (name, d)
        after = sha(save)
        record = {
            "case": name, "source_fixture": "synthetic_slot0",
            "input_schedule_sha256": sha(schedule), "before_sha256": before,
            "after_sha256": after, "physical_save_changed": before != after,
            "native": d, "game_initiated_save_verified": False,
            "cold_boot_player_state_verified": False,
            "interpretation": "Input-driven real-ROM observation. Changed Flash alone is insufficient to prove save callsite or complete game roundtrip.",
            "phase1_gate": "FAIL_INCOMPLETE", "independent_approval": False,
        }
        (root / (name + ".json")).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"case": name, "physical_save_changed": before != after,
                          "flash_changed_bytes": d["flash_changed_bytes"],
                          "first_flash_change_frame": d["first_flash_change_frame"],
                          "save_status": d["save_status"], "save_counter": d["save_counter"]}),
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
    main(p.parse_args())
