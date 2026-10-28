#!/usr/bin/env python3
"""Phase 1: fail-closed kernel syscall attribution for real Porymap GUI saves.

The matched QFile device control runs before the stage marker. Requiring
large ENOSPC writes after real QAction stage markers distinguishes them
from that one-byte control. This is not private QFile::error() inspection.
"""
import argparse
import json
import re
from pathlib import Path

STAGES = (
    "PHASE1_GUI_STAGE injected_failure_gui_save",
    "PHASE1_GUI_STAGE isolated_single_map_failed_save",
)
# strace -f -yy annotates the kernel fd target (the symlink resolves to /dev/full).
# strace -yy identifies /dev/full as </dev/full<char 1:7>>.
WRITE_ERROR = re.compile(
    r'(?P<pid>\d+)\s+write\(\d+</dev/full(?:<[^>\n]+>)?(?: \(deleted\))?>, .*?, (?P<requested>\d+)\)\s+= -1 ENOSPC\b'
)
DEMOTE_WRITE = re.compile(
    r'(?P<before>write\(\d+</dev/full(?:<[^>\n]+>)?(?: \(deleted\))?>, .*?, )(?P<count>\d+)(?P<after>\)\s+= -1 ENOSPC\b)'
)
WRITE_ANY = re.compile(r'write\(')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def inspect(lines):
    require(len(lines) > 50, "missing real strace output")
    stage_indexes = []
    for stage in STAGES:
        hits = [i for i, line in enumerate(lines) if stage in line]
        require(len(hits) == 1, f"expected exactly one real GUI stage {stage}: {hits}")
        require(WRITE_ANY.search(lines[hits[0]]), "stage marker not emitted by traced process")
        require(re.match(r'\s*\d+\s+write\(', lines[hits[0]]),
                "stage marker lacks strace process identity")
        stage_indexes.append(hits[0])
    require(stage_indexes[0] < stage_indexes[1], "GUI stage order drift")
    results = []
    for i, (stage, start) in enumerate(zip(STAGES, stage_indexes)):
        end = stage_indexes[i+1] if i+1 < len(stage_indexes) else len(lines)
        stage_pid = re.match(r'\s*(\d+)\s+write\(', lines[start]).group(1)
        errors = []
        for line in lines[start+1:end]:
            match = WRITE_ERROR.search(line)
            if (match and match.group("pid") == stage_pid
                    and int(match.group("requested")) > 1):
                errors.append({"requested_bytes": int(match.group("requested")),
                               "syscall_excerpt": line[:350]})
        require(errors, "no actual >1-byte /dev/full ENOSPC write by GUI PID after " + stage)
        results.append({"stage": stage, "gui_pid": stage_pid,
                        "real_gui_action_precedes_kernel_error": True,
                        "enospc_writes": errors[:8], "enospc_count": len(errors)})
    return results

def rejected(lines):
    try:
        inspect(lines)
    except ValueError:
        return True
    raise AssertionError("mutated syscall trace escaped fail-closed verifier")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    lines = a.trace.read_text(errors="replace").splitlines()
    records = inspect(lines)
    # Negative controls must reject missing stage, missing ENOSPC,
    # demoted one-byte control, and swapped stage chronology.
    checks = 0
    altered = [line for line in lines if STAGES[0] not in line]
    require(rejected(altered), "missing stage negative escaped")
    checks += 1
    altered = [line.replace("ENOSPC", "EIO") for line in lines]
    require(rejected(altered), "wrong errno negative escaped")
    checks += 1
    altered = [DEMOTE_WRITE.sub(lambda m: m.group("before") + "1" + m.group("after"), line)
               for line in lines]
    require(rejected(altered), "one-byte-only negative escaped")
    checks += 1
    altered = list(lines)
    first = next(i for i, line in enumerate(altered) if STAGES[0] in line)
    second = next(i for i, line in enumerate(altered) if STAGES[1] in line)
    altered[first], altered[second] = altered[second], altered[first]
    require(rejected(altered), "stage-order negative escaped")
    checks += 1
    altered = [line.replace("</dev/full", "</tmp/dev/full") for line in lines]
    require(rejected(altered), "impostor device path negative escaped")
    checks += 1
    altered = [re.sub(r'^\s*\d+(?=\s+write\(\d+</dev/full)', "999999", line)
               for line in lines]
    require(rejected(altered), "other-process ENOSPC negative escaped")
    checks += 1
    result = {"status": "NATIVE_PORYMAP_GUI_ENOSPC_SYSCALL_ATTRIBUTION",
              "actual_stage_records": records, "negative_controls_rejected": checks,
              "source_porymap_revision": "26b919d7ff4b54152de010abd5bf344af2ebe116",
              "source_project_cpp_blob": "d43b0949303433111d4478ad76117c2b3445dd13",
              "interpretation": "kernel write ENOSPC after actual QAction, not private QFile error-state introspection",
              "limitations": ["No source patch or direct Project::saveMap QFile::error() read",
                              "Linux strace syscall observation, not cross-platform Qt guarantee",
                              "No independent semantic approval; Phase 1 FAIL_INCOMPLETE"],
              "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0}
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": result["status"],
                      "stages": [r["stage"] for r in records],
                      "negative_controls_rejected": checks}, sort_keys=True))

if __name__ == "__main__":
    main()
