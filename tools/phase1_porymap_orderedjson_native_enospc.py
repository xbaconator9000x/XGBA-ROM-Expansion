#!/usr/bin/env python3
"""Compile unchanged Porymap OrderedJsonDoc and observe real Qt /dev/full error."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS = {
    "include/lib/orderedjson.h": "cb5139d37d955f2469ebd2eaaf089668b82884fe",
    "src/lib/orderedjson.cpp": "4d3a460c652541371a01132116e508db8c4c872c",
    "include/lib/orderedmap.h": "33fcfc50609722b10ae45eaa847be540c7c72d13",
    "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
}
WRITERS = ("saveMapLayouts", "saveMapGroups", "saveRegionMapSections",
           "saveWildMonData", "saveHealLocations")
def require(ok, message):
    if not ok: raise ValueError(message)
def git(root, *cmd):
    return subprocess.check_output(["git", "-C", str(root), *cmd], text=True).strip()
def extract(source, name):
    start = source.index("bool Project::" + name + "(")
    end = source.index("\n}\n", start)
    return source[start:end+2]
def source_contract(h, project):
    required = ("void dump(QFile *file)", "QTextStream fileStream(file);",
                "fileStream << m_obj->dump(&m_indent);",
                'fileStream << "\\n";')
    for token in required:
        require(h.count(token) == 1, "pinned OrderedJsonDoc drift: " + token)
    body = h[h.index("void dump(QFile *file)"):h.index("\n    }", h.index("void dump(QFile *file)"))]
    require("fileStream.status()" not in body and "file->error()" not in body,
            "dump now checks error; reevaluate")
    for name in WRITERS:
        body = extract(project, name)
        require("jsonDoc.dump(&" in body and ".close();" in body and
                body.rstrip().endswith("return true;\n}"),
                "Project writer result propagation changed: " + name)
        require("file.error()" not in body and "File.error()" not in body,
                "Project writer has new error check: " + name)
def check_output(out, trace):
    require("PHASE1_JSON_FATAL" not in out, "Qt harness fatal")
    require(out.count("PHASE1_JSON_STAGE positive\n") == 1 and
            out.count("PHASE1_JSON_STAGE failed\n") == 1 and
            out.count("PHASE1_JSON_DONE\n") == 1, "missing/duplicate native stages")
    m = re.search(r"PHASE1_JSON_RESULT positive_bytes=(\d+) positive_error=(\d+)", out)
    require(m is not None and int(m[1]) > 10 and int(m[2]) == 0,
            "positive bytes or Qt error wrong")
    require("PHASE1_JSON_RESULT failure_before=4 failure_after=4" in out,
            "actual QFile error status not retained")
    stages = [trace.find('PHASE1_JSON_STAGE positive'),
              trace.find('PHASE1_JSON_STAGE failed')]
    require(stages[0] >= 0 and stages[1] > stages[0],
            "native syscall stage ordering absent")
    tail = trace[stages[1]:]
    require(bool(re.search(r'write\(\d+</dev/full[^\n]*\)\s+=\s+-1 ENOSPC\b', tail)),
            "no real /dev/full ENOSPC syscall")
    return int(m[1])
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--porymap", type=Path, required=True)
    p.add_argument("--harness", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--trace", type=Path, required=True)
    a = p.parse_args()
    require(git(a.porymap, "rev-parse", "HEAD") == PIN, "Porymap pin mismatch")
    for path, sha in BLOBS.items():
        require(git(a.porymap, "hash-object", path) == sha, "blob drift " + path)
    h = (a.porymap / "include/lib/orderedjson.h").read_text()
    project = (a.porymap / "src/project.cpp").read_text()
    source_contract(h, project)
    source_neg = 0
    for token in ('void dump(QFile *file)', 'QTextStream fileStream(file);',
                  'fileStream << m_obj->dump(&m_indent);'):
        modified = h.replace(token, "PHASE1_MUTATION", 1)
        try: source_contract(modified, project)
        except ValueError: source_neg += 1
        else: raise ValueError("serializer source mutation escaped " + token)
    for name in WRITERS:
        old = extract(project, name)
        last = old.rfind("return true;")
        require(last >= 0, "writer success return missing: " + name)
        mutated = old[:last] + old[last:].replace("return true;", "return false;", 1)
        modified = project.replace(old, mutated, 1)
        try: source_contract(h, modified)
        except ValueError: source_neg += 1
        else: raise ValueError("writer mutation escaped " + name)
    flags = subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt6Core"],
                                    text=True).split()
    executable = a.output.parent / "phase1_porymap_orderedjson_native"
    compile = subprocess.run(
        ["g++", "-std=c++17", "-fPIC", "-O0", "-Wall", "-Wextra",
         "-I" + str(a.porymap / "include/lib"), str(a.harness),
         str(a.porymap / "src/lib/orderedjson.cpp"), "-o", str(executable)] + flags,
        text=True, capture_output=True)
    require(compile.returncode == 0, "native compile failed: " + compile.stderr[-4000:])
    a.trace.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(["strace", "-f", "-yy", "-s", "256", "-e",
                          "trace=openat,write,close", "-o", str(a.trace),
                          str(executable.resolve())], text=True, capture_output=True)
    a.log.parent.mkdir(parents=True, exist_ok=True)
    a.log.write_text(run.stdout + run.stderr)
    require(run.returncode == 0, "native Qt failed: " + run.stderr[-2000:])
    observed = check_output(run.stdout, a.trace.read_text())
    negatives = [
        run.stdout.replace("failure_before=4", "failure_before=0"),
        run.stdout.replace("failure_after=4", "failure_after=0"),
        run.stdout.replace("positive_error=0", "positive_error=4"),
        run.stdout.replace("PHASE1_JSON_DONE", "PHASE1_JSON_ABORT"),
        run.stdout.replace("PHASE1_JSON_STAGE failed", "PHASE1_JSON_STAGE missing"),
    ]
    output_neg = 0
    for modified in negatives:
        try: check_output(modified, a.trace.read_text())
        except ValueError: output_neg += 1
        else: raise ValueError("Qt transcript mutation escaped")
    bad_trace = a.trace.read_text().replace("ENOSPC", "EIO")
    try: check_output(run.stdout, bad_trace)
    except ValueError: output_neg += 1
    else: raise ValueError("syscall mutation escaped")
    record = {
        "class": "PINNED_PORYMAP_ORDEREDJSONDOC_NATIVE_QT_ENOSPC",
        "porymap_pin": PIN, "blobs": BLOBS,
        "positive_serialized_bytes": observed,
        "native_qt_serializer_executed": True,
        "real_linux_enospc_observed": True,
        "qfile_error_before_after_close": [4, 4],
        "source_mutations_rejected": source_neg,
        "transcript_mutations_rejected": output_neg,
        "project_writer_functions_executed": False,
        "gui_new_map_executed": False,
        "five_json_writers_source_only": True,
        "independent_approvals": 0, "phase1_gate": "FAIL_INCOMPLETE",
        "harness_sha256": hashlib.sha256(a.harness.read_bytes()).hexdigest(),
    }
    a.output.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps(record, sort_keys=True))
if __name__ == "__main__":
    main()
