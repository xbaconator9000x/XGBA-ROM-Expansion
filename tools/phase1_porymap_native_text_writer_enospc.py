#!/usr/bin/env python3
"""Source-extracted, unmodified Porymap Qt text writers under real Linux ENOSPC."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOB = "d43b0949303433111d4478ad76117c2b3445dd13"
NAMES = ("saveTextFile", "appendTextFile")
STAGES = ("save_positive", "append_positive", "save_failure",
          "append_failure", "save_open_rejected", "append_open_rejected")

def require(ok, message):
    if not ok:
        raise ValueError(message)

def extract(source, name):
    needle = "bool Project::" + name + "("
    require(source.count(needle) == 1, "missing/duplicate pinned " + name)
    start = source.index(needle)
    end = source.find("\n}\n", start)
    require(end > start, "unterminated pinned " + name)
    return source[start:end+2]

def check(source):
    for name, mode in zip(NAMES, ("WriteOnly", "Append")):
        body = extract(source, name)
        require("QFile file(path);" in body, name + " QFile owner changed")
        require("if (!file.open(QIODevice::" + mode + "))" in body,
                name + " open guard changed")
        require(body.count("file.write(text.toUtf8());") == 1,
                name + " unchecked write changed")
        require(body.count("return true;") == 1 and
                body.count("return false;") == 1, name + " result changed")
        require("file.flush()" not in body and "file.error()" not in body,
                name + " post-write error checks added")
    return True

def source_mutations(source):
    mutations = [
        ("saveTextFile", 'file.open(QIODevice::WriteOnly)', 'file.open(QIODevice::ReadOnly)'),
        ("appendTextFile", 'file.open(QIODevice::Append)', 'file.open(QIODevice::WriteOnly)'),
        ("saveTextFile", 'file.write(text.toUtf8());', 'if (file.write(text.toUtf8()) < 0) return false;'),
        ("appendTextFile", 'file.write(text.toUtf8());', 'file.flush();'),
        ("saveTextFile", 'return true;', 'return false;'),
        ("appendTextFile", 'QFile file(path);', 'QFile file("/dev/null");'),
    ]
    count = 0
    for name, old, new in mutations:
        body = extract(source, name)
        require(old in body, "mutation anchor missing in " + name + ": " + old)
        changed_body = body.replace(old, new, 1)
        modified = source.replace(body, changed_body, 1)
        require(modified != source, "ineffective source mutation")
        try:
            check(modified)
        except ValueError:
            count += 1
        else:
            raise ValueError("source mutation escaped: " + name + ": " + old)
    return count

def parse(stdout, trace):
    require("PHASE1_TEXT_FATAL" not in stdout, "native Qt harness failed")
    positions = []
    for stage in STAGES:
        marker = "PHASE1_TEXT_STAGE " + stage
        require(stdout.count(marker + "\n") == 1, "missing/duplicate native stage " + stage)
        match = list(re.finditer(re.escape(marker), trace))
        require(len(match) == 1, "missing/duplicate syscall stage " + stage)
        positions.append(match[0].start())
    require(positions == sorted(positions), "syscall stage chronology changed")
    require("PHASE1_TEXT_RESULT save_failure_return=1" in stdout,
            "actual pinned save failure did not report success")
    require("PHASE1_TEXT_RESULT append_failure_return=1" in stdout,
            "actual pinned append failure did not report success")
    require("PHASE1_TEXT_RESULT positive_bytes=11 open_rejections=2" in stdout,
            "positive and failed-open controls missing")
    require(stdout.count("PHASE1_TEXT_DONE") == 1, "native Qt execution incomplete")
    enospc = []
    for idx in (2, 3):
        section = trace[positions[idx]:positions[idx+1]]
        matches = re.findall(r'write\(\d+</dev/full>,[^\n]*\)\s+=\s+-1 ENOSPC\b', section)
        require(matches, "no actual /dev/full ENOSPC syscall for " + STAGES[idx] +
                "; trace section=" + repr(section[-6000:]))
        enospc.append(len(matches))
    return {"native_original_functions_executed": True,
            "actual_save_enospc_syscalls": enospc[0],
            "actual_append_enospc_syscalls": enospc[1],
            "both_unchecked_write_failures_returned_true": True,
            "positive_write_append_bytes_verified": 11,
            "open_failure_returns_false": 2}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porymap", type=Path, required=True)
    ap.add_argument("--harness", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--trace", type=Path, required=True)
    args = ap.parse_args()
    def git(*cmd):
        return subprocess.check_output(["git", "-C", str(args.porymap), *cmd], text=True).strip()
    require(git("rev-parse", "HEAD") == PIN, "wrong Porymap source commit")
    require(git("hash-object", "src/project.cpp") == BLOB, "Porymap source blob changed")
    source = (args.porymap / "src/project.cpp").read_text()
    check(source)
    n = source_mutations(source)
    harness = args.harness.read_text()
    require(harness.count("PHASE1_INSERT_PINNED_FUNCTIONS") == 1,
            "test entrypoint insertion marker changed")
    require(harness.count('"/dev/full"') == 2,
            "two native ENOSPC paths not present")
    actual = harness.replace("PHASE1_INSERT_PINNED_FUNCTIONS",
                             "\n\n".join(extract(source, name) for name in NAMES))
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "phase1_writer.cpp"
        exe = Path(td) / "phase1_writer"
        src.write_text(actual)
        flags = subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt6Core"],
                                        text=True).split()
        compile_cmd = ["g++", "-std=c++17", "-fPIC", "-O0", "-Wall", "-Wextra",
                       "-Werror", str(src), "-o", str(exe)] + flags
        build = subprocess.run(compile_cmd, text=True, capture_output=True)
        require(build.returncode == 0, "pinned Qt compile failed: " + build.stderr[-4000:])
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.trace.parent.mkdir(parents=True, exist_ok=True)
        run = subprocess.run(["strace", "-f", "-yy", "-s", "512",
                              "-e", "trace=openat,write,close",
                              "-o", str(args.trace), str(exe)],
                             text=True, capture_output=True)
        args.log.write_text(run.stdout + run.stderr)
        require(run.returncode == 0, "native Qt failed: " + run.stderr[-3000:])
        observed = parse(run.stdout + run.stderr, args.trace.read_text())
    evidence = {
        "class": "PINNED_PORYMAP_ORIGINAL_QT_TEXT_WRITERS_NATIVE_ENOSPC",
        "porymap_commit": PIN, "project_cpp_git_blob": BLOB,
        "project_cpp_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "original_function_bodies_unmodified": True,
        "test_only_class_and_logerror_stubs": True,
        "real_mainwindow_or_new_map_save_executed": False,
        "actual_private_qfile_error_instrumented": False,
        "physical_flash_or_rom_executed": False,
        "source_mutations_rejected": n,
        "independent_approvals": 0, "gate": "FAIL_INCOMPLETE",
        **observed,
    }
    def validate(d):
        require(d["source_mutations_rejected"] == 6, "source negatives missing")
        require(d["original_function_bodies_unmodified"] is True,
                "original body provenance changed")
        require(d["both_unchecked_write_failures_returned_true"] is True,
                "false-success observation changed")
        require(d["actual_save_enospc_syscalls"] > 0 and
                d["actual_append_enospc_syscalls"] > 0, "native ENOSPC evidence missing")
        require(d["open_failure_returns_false"] == 2 and
                d["positive_write_append_bytes_verified"] == 11,
                "positive/failed-open controls missing")
        require(d["real_mainwindow_or_new_map_save_executed"] is False and
                d["actual_private_qfile_error_instrumented"] is False,
                "scope overclaimed")
        require(d["independent_approvals"] == 0 and d["gate"] == "FAIL_INCOMPLETE",
                "false semantic approval")
    validate(evidence)
    mutations = [
        {"source_mutations_rejected": 5},
        {"both_unchecked_write_failures_returned_true": False},
        {"actual_save_enospc_syscalls": 0},
        {"actual_append_enospc_syscalls": 0},
        {"open_failure_returns_false": 1},
        {"positive_write_append_bytes_verified": 0},
        {"real_mainwindow_or_new_map_save_executed": True},
        {"actual_private_qfile_error_instrumented": True},
        {"original_function_bodies_unmodified": False},
        {"gate": "PASS"},
        {"independent_approvals": 1},
    ]
    for i, change in enumerate(mutations):
        try:
            validate({**evidence, **change})
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped " + str(i))
    evidence["evidence_mutations_rejected"] = len(mutations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()
