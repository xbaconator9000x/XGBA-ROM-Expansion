#!/usr/bin/env python3
"""Fail-closed native Qt new-map retry transcript verification."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
FR = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
EXPECTED = {
    "original_porymap_project_executed": True,
    "original_firered_project_loaded": True,
    "case_a_matched_qfile_error": True,
    "case_a_save_returned_true": True,
    "case_a_persisted_flag_true": True,
    "case_a_script_absent_after_retry": True,
    "case_a_event_include_count_after_retry": 1,
    "case_b_map_json_open_rejected": True,
    "case_b_save_returned_false_twice": True,
    "case_b_persisted_flag_false": True,
    "case_b_event_include_count_after_retry": 2,
    "native_qt_project": True,
    "real_gui_new_map": False,
    "physical_durability_tested": False,
    "phase1_gate": "FAIL_INCOMPLETE",
    "independent_approvals": 0,
}
def need(ok, msg):
    if not ok: raise ValueError(msg)
def check(log):
    rows = [x.split("=",1)[1] for x in log.splitlines()
            if x.startswith("PHASE1_NEW_MAP_QT=")]
    need(len(rows) == 1, "missing/duplicate original Qt result")
    data = json.loads(rows[0])
    need(data == EXPECTED, "Qt new-map result/scope changed")
    need("FAIL " not in log, "native failure marker")
    return data
def negatives(log):
    count = 0
    for key, value in EXPECTED.items():
        data = dict(EXPECTED)
        data[key] = (not value if isinstance(value, bool) else
                     value + 1 if isinstance(value, int) else "PASS")
        changed = "PHASE1_NEW_MAP_QT=" + json.dumps(data, sort_keys=True) + "\n"
        need(changed != log, "ineffective negative mutation")
        try: check(changed)
        except ValueError: count += 1
        else: raise AssertionError("escaped transcript mutation " + key)
    need(count == len(EXPECTED), "transcript negative count changed")
    return count
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--porymap", type=Path, required=True)
    p.add_argument("--firered", type=Path, required=True)
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    def git(root,*args):
        return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
    need(git(a.porymap,"rev-parse","HEAD") == PIN, "Porymap pin drift")
    need(git(a.firered,"rev-parse","HEAD") == FR, "FireRed pin drift")
    need(git(a.porymap,"hash-object","src/project.cpp") ==
         "d43b0949303433111d4478ad76117c2b3445dd13", "Project source drift")
    log = a.log.read_text()
    data = check(log)
    rejected = negatives(log)
    out = {
        "evidence_class": "NATIVE_QT_ORIGINAL_PROJECT_TEST_ONLY_NEW_MAPS",
        "porymap_pin": PIN, "firered_pin": FR,
        "result": data, "transcript_negative_controls_rejected": rejected,
        "log_sha256": hashlib.sha256(log.encode()).hexdigest(),
        "full_gui_executed": False, "physical_durability": False,
        "independent_approvals": 0, "phase1_gate": "FAIL_INCOMPLETE",
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(out, indent=2, sort_keys=True)+"\n")
    print("PINNED_QT_NEW_MAP_RETRY_PASS negatives=%d gate=FAIL_INCOMPLETE approvals=0" % rejected)
if __name__ == "__main__":
    main()
