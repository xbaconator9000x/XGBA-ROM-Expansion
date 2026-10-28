#!/usr/bin/env python3
"""Execute five unchanged pinned Porymap Project JSON writers with Qt6 and real ENOSPC.

No full GUI, project loading, or entire-file review is claimed.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS = {
    "src/project.cpp": "d43b0949303433111d4478ad76117c2b3445dd13",
    "include/lib/orderedjson.h": "cb5139d37d955f2469ebd2eaaf089668b82884fe",
    "src/lib/orderedjson.cpp": "4d3a460c652541371a01132116e508db8c4c872c",
    "include/lib/orderedmap.h": "33fcfc50609722b10ae45eaa847be540c7c72d13",
}
NAMES = ("saveMapLayouts", "saveMapGroups", "saveRegionMapSections",
         "saveWildMonData", "saveHealLocations")
HANDLES = ("layoutsFile", "mapGroupsFile", "file", "wildEncountersFile", "file")

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def extract(source, name):
    anchor = "bool Project::" + name + "("
    require(source.count(anchor) == 1, "pinned function missing or duplicated: " + name)
    start = source.index(anchor)
    end = source.find("\n}\n", start)
    require(end > start, "unterminated function: " + name)
    return source[start:end + 2]

def source_contract(source, ordered):
    require(ordered.count("void dump(QFile *file)") == 1, "serializer API drift")
    require("QTextStream fileStream(file);" in ordered, "serializer write path drift")
    for name, handle in zip(NAMES, HANDLES):
        body = extract(source, name)
        require(body.count("jsonDoc.dump(&" + handle + ");") == 1, "dump changed: " + name)
        require(body.count(handle + ".close();") == 1, "close changed: " + name)
        require(body.count("return true;") >= 1, "success return changed: " + name)
        require("if (!" + handle + ".open(QIODevice::WriteOnly))" in body,
                "open guard changed: " + name)
        tail = body[body.index("jsonDoc.dump(&" + handle + ");"):]
        require(handle + ".error()" not in tail and "commit()" not in tail,
                "post-write error handling changed: " + name)

def validate_transcript(stdout, trace):
    require("PHASE1_FIVE_FATAL" not in stdout, "native harness fatal")
    require(stdout.count("PHASE1_FIVE_DONE") == 1, "native completion missing")
    stages = [("positive_" + name) for name in NAMES] + [
        ("failed_" + name) for name in NAMES]
    positions = []
    for stage in stages:
        marker = "PHASE1_FIVE_STAGE " + stage
        require(stdout.count(marker + "\n") == 1, "stage missing/duplicate: " + stage)
        hits = list(re.finditer(re.escape(marker), trace))
        require(len(hits) == 1, "syscall stage missing/duplicate: " + stage)
        positions.append(hits[0].start())
    require(positions == sorted(positions), "stage order changed")
    for name in NAMES:
        m = re.search(r"PHASE1_FIVE_RESULT positive_" + name + r"_bytes=(\d+)", stdout)
        require(m is not None and int(m[1]) > 10, "positive JSON not observed: " + name)
        require("PHASE1_FIVE_RESULT failed_" + name + "_return=1" in stdout,
                "original false-success not observed: " + name)
    enospc = {}
    for i, name in enumerate(NAMES):
        start = positions[len(NAMES) + i]
        stop = positions[len(NAMES) + i + 1] if i + 1 < len(NAMES) else len(trace)
        section = trace[start:stop]
        matches = re.findall(r"write\(\d+</dev/full[^\n]*\)\s+=\s+-1 ENOSPC\b", section)
        require(matches, "real syscall ENOSPC missing for " + name)
        enospc[name] = len(matches)
    return enospc

def main():
    ap = argparse.ArgumentParser()
    for key in ("porymap", "harness", "output", "log", "trace"):
        ap.add_argument("--" + key, type=Path, required=True)
    args = ap.parse_args()
    def git(*argv):
        return subprocess.check_output(["git", "-C", str(args.porymap), *argv],
                                       text=True).strip()
    require(git("rev-parse", "HEAD") == PIN, "upstream pin changed")
    for path, sha in BLOBS.items():
        require(git("hash-object", path) == sha, "upstream blob drift: " + path)
    source = (args.porymap / "src/project.cpp").read_text()
    ordered = (args.porymap / "include/lib/orderedjson.h").read_text()
    source_contract(source, ordered)
    source_neg = 0
    for name, handle in zip(NAMES, HANDLES):
        original = extract(source, name)
        target = "jsonDoc.dump(&" + handle + ");"
        altered = source.replace(original, original.replace(target, "PHASE1_BAD_DUMP", 1), 1)
        try:
            source_contract(altered, ordered)
        except ValueError:
            source_neg += 1
        else:
            raise ValueError("source mutation escaped " + name)
    harness = args.harness.read_text()
    require(harness.count("PHASE1_INSERT_PINNED_FUNCTIONS") == 1, "harness insertion drift")
    code = harness.replace("PHASE1_INSERT_PINNED_FUNCTIONS",
                           "\n\n".join(extract(source, name) for name in NAMES))
    with tempfile.TemporaryDirectory() as directory:
        src = Path(directory) / "native_five.cpp"
        exe = Path(directory) / "native_five"
        src.write_text(code)
        flags = subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt6Core"],
                                        text=True).split()
        command = ["g++", "-std=c++17", "-fPIC", "-O0", "-Wall", "-Wextra",
                   "-I" + str(args.porymap / "include/lib"),
                   str(src), str(args.porymap / "src/lib/orderedjson.cpp"),
                   "-o", str(exe)] + flags
        built = subprocess.run(command, capture_output=True, text=True)
        require(built.returncode == 0, "native Qt compilation failed: " + built.stderr[-5000:])
        args.trace.parent.mkdir(parents=True, exist_ok=True)
        run = subprocess.run(["strace", "-f", "-yy", "-s", "512",
                              "-e", "trace=openat,write,close",
                              "-o", str(args.trace), str(exe)],
                             capture_output=True, text=True)
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(run.stdout + run.stderr)
        require(run.returncode == 0, "native Qt failed: " + run.stderr[-3000:])
    trace = args.trace.read_text()
    observed = validate_transcript(run.stdout, trace)
    transcript_neg = 0
    for name in NAMES:
        modified = run.stdout.replace("failed_" + name + "_return=1",
                                      "failed_" + name + "_return=0")
        try:
            validate_transcript(modified, trace)
        except ValueError:
            transcript_neg += 1
        else:
            raise ValueError("false-success transcript mutation escaped: " + name)
        modified_trace = trace.replace("ENOSPC", "EIO", 1)
        # Force removal of the exact stage's ENOSPC evidence, not an arbitrary earlier stage.
        marker = "PHASE1_FIVE_STAGE failed_" + name
        start = trace.index(marker)
        next_start = trace.find("PHASE1_FIVE_STAGE failed_", start + len(marker))
        if next_start < 0: next_start = len(trace)
        section = trace[start:next_start].replace("ENOSPC", "EIO")
        modified_trace = trace[:start] + section + trace[next_start:]
        try:
            validate_transcript(run.stdout, modified_trace)
        except ValueError:
            transcript_neg += 1
        else:
            raise ValueError("ENOSPC trace mutation escaped: " + name)
    evidence = {
        "class": "PINNED_PORYMAP_FIVE_PROJECT_JSON_WRITERS_NATIVE_QT_ENOSPC",
        "porymap_commit": PIN,
        "source_blobs": BLOBS,
        "unchanged_original_project_function_bodies_compiled": list(NAMES),
        "positive_json_files_validated": len(NAMES),
        "actual_linux_enospc_syscalls_by_writer": observed,
        "original_writer_false_success_returns": len(NAMES),
        "source_mutations_rejected": source_neg,
        "transcript_mutations_rejected": transcript_neg,
        "test_only_empty_project_data_and_config": True,
        "real_project_constructor_or_gui_executed": False,
        "upstream_porymap_patched": False,
        "whole_file_approvals": 0,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
        "harness_sha256": hashlib.sha256(args.harness.read_bytes()).hexdigest(),
    }
    require(source_neg == 5 and transcript_neg == 10, "negative-control count wrong")
    require(evidence["independent_approvals"] == 0 and
            evidence["phase1_gate"] == "FAIL_INCOMPLETE", "approval overclaim")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()
