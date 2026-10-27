#!/usr/bin/env python3
"""Native mGBA adversarial save observations. Observations are not safety approvals."""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

CASES = (
    ("control_slot0", "slot0", False),
    ("changed_header_slot0", "slot0", True),
    ("malformed_id15", "malformed_id15", False),
    ("malformed_id65535", "malformed_id65535", False),
)

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((Path(args.fixtures) / "fixture_manifest.json").read_text())
    entries = {item["name"]: item for item in manifest["cases"]}
    assert sha256(Path(args.rom)) == manifest["source_rom_sha256"], "source ROM digest drift"
    assert sha256(Path(args.changed_rom)) == entries["header_changed"]["sha256"], "changed-header ROM digest drift"
    assert Path(args.rom).read_bytes()[0xAC:0xB0] == b"BPRE", "unexpected original game code"
    assert Path(args.changed_rom).read_bytes()[0xAC:0xB0] == b"ZZZZ", "unexpected changed game code"
    results = []
    for name, fixture, changed_header in CASES:
        assert fixture in entries, (name, "missing pinned fixture manifest entry")
        save = out / (name + ".sav")
        shutil.copyfile(Path(args.fixtures) / (fixture + ".sav"), save)
        rom = Path(args.changed_rom if changed_header else args.rom)
        before = sha256(save)
        assert before == entries[fixture]["sha256"], (name, "fixture SHA256 mismatch")
        assert save.stat().st_size == 32 * 4096, (name, "fixture size drift")
        if name.startswith("malformed_id"):
            observed_id = struct.unpack_from("<H", save.read_bytes(), (14 + 6) * 4096 + 0xFF4)[0]
            assert observed_id == int(name.removeprefix("malformed_id")), (name, observed_id)
        command = [
            args.probe, str(rom), str(save), "trace",
            args.status, args.counter, args.loader, args.valid, args.copy, args.sb2,
        ]
        try:
            p = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"{name}: native emulator timed out without a classified outcome") from e
        parsed = []
        for line in p.stdout.splitlines():
            if line.startswith('{"mode":"trace"'):
                parsed.append(json.loads(line))
        record = {
            "case": name, "fixture": fixture,
            "rom_variant": "changed_header" if changed_header else "pinned_unmodified",
            "save_sha256_before": before,
            "save_sha256_after": sha256(save),
            "save_file_changed_during_trace": before != sha256(save),
            "process_returncode": p.returncode,
            "stdout_tail": p.stdout[-1200:],
            "stderr_tail": p.stderr[-1200:],
            "runtime_result": None,
            "observation": None,
            "phase1_gate": "FAIL_INCOMPLETE",
            "independent_approval": False,
        }
        if p.returncode == 0:
            assert len(parsed) == 1, (name, "expected exactly one native JSON trace", len(parsed))
            d = parsed[0]
            assert d["frames"] >= 180 and d["trace_steps"] > 0, (name, d)
            record["runtime_result"] = "native_trace_observed"
            record["observation"] = d
        elif p.returncode < 0:
            assert not parsed, (name, "partial native result before signal", parsed)
            record["runtime_result"] = "native_process_signal_terminated"
        elif p.returncode == 2 and "ERROR:" in p.stderr:
            assert not parsed, (name, "unexpected partial native trace", parsed)
            record["runtime_result"] = "probe_reported_error"
        else:
            raise RuntimeError(f"{name}: unclassified native process failure: rc={p.returncode}; {p.stderr[-600:]}")
        if name == "control_slot0":
            assert record["runtime_result"] == "native_trace_observed", record
            d = record["observation"]
            assert d["load_game_save_entry_hits"] >= 1, d
            assert d["get_save_valid_status_entry_hits"] >= 1, d
            assert d["copy_save_slot_data_entry_hits"] >= 1, d
            assert (d["save_status"], d["save_counter"], d["saveblock2_filler_marker"]) == (1, 0, 0xA5), d
        (out / (name + ".json")).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        summary = {k: record[k] for k in ("case", "rom_variant", "runtime_result", "process_returncode", "save_file_changed_during_trace")}
        if record["observation"] is not None:
            d = record["observation"]
            summary.update({k: d[k] for k in ("frames", "save_status", "save_counter", "saveblock2_filler_marker", "load_game_save_entry_hits", "get_save_valid_status_entry_hits", "copy_save_slot_data_entry_hits")})
        results.append(summary)
        print(json.dumps(results[-1], sort_keys=True), flush=True)
    (out / "adversarial_summary.json").write_text(json.dumps({
        "cases": results,
        "fixture_source_rom_sha256": manifest["source_rom_sha256"],
        "interpretation": "native observation only; no proof of in-game write, playable recovery or out-of-range safety",
        "phase1_gates": "FAIL_INCOMPLETE",
        "new_machine_indexed_files": 0,
        "independent_approvals": 0,
    }, indent=2) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for arg in ("probe", "rom", "changed-rom", "fixtures", "output", "status", "counter", "loader", "valid", "copy", "sb2"):
        parser.add_argument("--" + arg, required=True)
    run(parser.parse_args())
