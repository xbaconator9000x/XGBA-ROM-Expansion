#!/usr/bin/env python3
"""Phase 1 test-only private QFile::error() observation in pinned Porymap.

The instrumented binary differs from the pristine pinned source by a logging
statement only. The prior pristine Qt GUI + strace checkpoint remains separate.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOB = "d43b0949303433111d4478ad76117c2b3445dd13"
BEFORE = "    jsonDoc.dump(&mapFile);\n    mapFile.close();"
AFTER = (
    '    jsonDoc.dump(&mapFile);\n'
    '    const bool phase1ObserveMapFile = mapFilepath.contains(QStringLiteral("PalletTown/map.json"));\n'
    '    const int phase1BeforeClose = static_cast<int>(mapFile.error());\n'
    '    if (phase1ObserveMapFile) {\n'
    '        std::fprintf(stderr, "PHASE1_PRIVATE_QFILE_ERROR status=%d\\n", phase1BeforeClose);\n'
    '        std::fflush(stderr);\n'
    '    }\n'
    '    mapFile.close();\n'
    '    const int phase1AfterClose = static_cast<int>(mapFile.error());'
)
POST_CLEAN_BEFORE = "    map->setClean();\n\n    if (!skipLayout"
POST_CLEAN_AFTER = (
    '    map->setClean();\n'
    '    if (phase1ObserveMapFile) {\n'
    '        std::fprintf(stderr, "PHASE1_PRIVATE_QFILE_FINAL before=%d after=%d dirty=%d\\n",\n'
    '                     phase1BeforeClose, phase1AfterClose,\n'
    '                     static_cast<int>(map->hasUnsavedChanges()));\n'
    '        std::fflush(stderr);\n'
    '    }\n\n    if (!skipLayout'
)
FINAL = re.compile(r"^PHASE1_PRIVATE_QFILE_FINAL before=(\d+) after=(\d+) dirty=(\d+)$")

POSITIVE = "PHASE1_GUI_STAGE isolated_single_map_positive_save"
NEGATIVES = ("PHASE1_GUI_STAGE injected_failure_gui_save",
             "PHASE1_GUI_STAGE isolated_single_map_failed_save")
END = "PHASE1_GUI_STAGE close_after_failed_single_map_save"
STAGE = "PHASE1_GUI_STAGE "
ERROR = re.compile(r"^PHASE1_PRIVATE_QFILE_ERROR status=(\d+)$")

def require(ok, why):
    if not ok:
        raise ValueError(why)

def instrument(root):
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"],
                                   text=True).strip()
    require(head == PIN, "wrong pinned Porymap revision")
    blob = subprocess.check_output(["git", "-C", str(root),
                                    "hash-object", "src/project.cpp"], text=True).strip()
    require(blob == BLOB, "wrong pristine Project source blob")
    path = root/"src/project.cpp"
    content = path.read_text()
    require(content.count(BEFORE) == 1, "private map QFile site changed")
    require(content.count(POST_CLEAN_BEFORE) == 1, "private map clean site changed")
    require("PHASE1_PRIVATE_QFILE_ERROR" not in content,
            "instrumentation already installed")
    modified = "#include <cstdio>\n" + content.replace(BEFORE, AFTER, 1)
    modified = modified.replace(POST_CLEAN_BEFORE, POST_CLEAN_AFTER, 1)
    require(modified.count("mapFile.close();") == content.count("mapFile.close();"),
            "instrumentation changed close count")
    require(modified.count("map->setClean();") == content.count("map->setClean();"),
            "instrumentation changed dirty-state logic")
    path.write_text(modified)
    return {"pinned_source": PIN, "pristine_blob": BLOB,
            "test_only_instrumentation": True, "control_flow_modified": False,
            "private_handle_observed_before_close": True,
            "private_handle_observed_after_close_and_clean": True}

def inspect(lines):
    stages = [i for i, s in enumerate(lines) if s.startswith(STAGE)]
    require(stages, "no actual GUI stage markers in stderr")
    stage_names = [lines[i] for i in stages]
    require(len(stage_names) == len(set(stage_names)),
            "duplicate stage markers")
    for name in (POSITIVE, *NEGATIVES, END):
        require(stage_names.count(name) == 1, "missing/duplicate GUI stage: " + name)
    def statuses(stage):
        i = lines.index(stage)
        later = next((j for j in stages if j > i), len(lines))
        observed = []
        final = []
        for line in lines[i+1:later]:
            m = ERROR.fullmatch(line.strip())
            if m:
                observed.append(int(m.group(1)))
            m = FINAL.fullmatch(line.strip())
            if m:
                final.append(tuple(map(int, m.groups())))
        require(len(observed) == 1 and len(final) == 1,
                "expected paired private QFile before/after/clean observations: " + stage)
        before, after, dirty = final[0]
        require(before == observed[0], "private QFile before-close readings disagree")
        require(dirty == 0, "actual map not clean after save return pathway")
        return {"before": before, "after": after, "dirty_after_clean": dirty}
    positive = statuses(POSITIVE)
    require(positive["before"] == 0, "successful Save has nonzero QFile error")
    failed = [statuses(stage) for stage in NEGATIVES]
    require(all(value["before"] != 0 for value in failed),
            "actual failed GUI Save private QFile did not report error")
    require(lines.index(POSITIVE) < lines.index(NEGATIVES[1]) < lines.index(END),
            "stage chronology changed")
    return {"positive_qfile_status": positive["before"],
            "positive_qfile_after_close": positive["after"],
            "failed_qfile_statuses": [v["before"] for v in failed],
            "failed_qfile_after_close_statuses": [v["after"] for v in failed],
            "actual_private_handle_error_observed": True,
            "private_error_ignored_before_clean": True}

def controls():
    good = [
        POSITIVE, "PHASE1_PRIVATE_QFILE_ERROR status=0",
        "PHASE1_PRIVATE_QFILE_FINAL before=0 after=0 dirty=0",
        NEGATIVES[0], "PHASE1_PRIVATE_QFILE_ERROR status=4",
        "PHASE1_PRIVATE_QFILE_FINAL before=4 after=4 dirty=0",
        NEGATIVES[1], "PHASE1_PRIVATE_QFILE_ERROR status=4",
        "PHASE1_PRIVATE_QFILE_FINAL before=4 after=4 dirty=0",
        END
    ]
    require(inspect(good)["private_error_ignored_before_clean"],
            "positive synthetic log failed")
    mutated = (
        good[:2] + good[3:],  # missing final
        good[:5] + [good[5], good[5]] + good[6:],  # duplicate final
        [x.replace("dirty=0", "dirty=1") for x in good],
        [x.replace("before=4", "before=0") for x in good],
        [x.replace("status=4", "status=0") for x in good],
        [x.replace("status=0", "status=4") for x in good],
        [x.replace(NEGATIVES[0], "PHASE1_GUI_STAGE other") for x in good],
        good[:7] + [END] + good[7:9],
        [x.replace("after=4", "after=bogus") for x in good],
        good[:4] + good[5:],  # missing failed status
    )
    for i, case in enumerate(mutated):
        try:
            inspect(case)
        except ValueError:
            continue
        raise AssertionError(f"private QFile sequence mutation escaped: {i}")
    return len(mutated)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--instrument", type=Path)
    ap.add_argument("--trace", type=Path)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    require(bool(args.instrument) != bool(args.trace), "choose instrument or trace")
    if args.instrument:
        result = instrument(args.instrument)
    else:
        result = inspect(args.trace.read_text(errors="replace").splitlines())
        result.update({"pinned_source": PIN, "pristine_blob": BLOB,
                       "test_only_instrumented_binary": True,
                       "private_qfile_error_negative_controls": controls(),
                       "unmodified_pinned_binary_qfile_error_observed": False,
                       "previous_unmodified_gui_syscall_witness_is_separate": True})
    result.update({"phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
