#!/usr/bin/env python3
"""Execute the pinned mGBA SaveConverter body with native Qt6 QIODevice fault injection."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
SOURCE = "src/platform/qt/SaveConverter.cpp"
BLOB = "4c32280c9c5288e806ffd237119186e2a633c4a7"
STAGES = {
    "full": (22, 22, 22, 1, 0),
    "short": (22, 1, 1, 1, 0),
    "negative": (22, 0, -1, 1, 0),
    "open_failure": (0, 0, 0, 0, 1),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def extract_convert(source):
    needle = "void SaveConverter::convert()"
    require(source.count(needle) == 1, "missing or ambiguous pinned convert()")
    start = source.index(needle)
    brace = source.index("{", start)
    depth = 0
    for offset in range(brace, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start:offset + 1]
    raise ValueError("unbalanced pinned convert() body")


def check_source(source):
    body = extract_convert(source)
    anchors = (
        "QByteArray converted = input.convertTo(output);",
        "if (converted.isEmpty()) {",
        "QFile out(m_ui.outputFile->text());",
        "if (out.open(QIODevice::WriteOnly | QIODevice::Truncate)) {",
        "out.write(converted);",
        "out.close();",
        "} else {",
        'tr("Failed to open output file.")',
    )
    for anchor in anchors:
        require(body.count(anchor) == 1, "pinned convert() anchor drift: " + anchor)
    return body


def source_mutations(source):
    mutations = (
        ("out.write(converted);", "if (out.write(converted) != converted.size()) return;"),
        ("if (out.open(QIODevice::WriteOnly | QIODevice::Truncate)) {",
         "if (!out.open(QIODevice::WriteOnly | QIODevice::Truncate)) {"),
        ("out.close();", "/* close removed */"),
    )
    rejected = 0
    for old, new in mutations:
        require(source.count(old) == 1, "mutation source anchor is not unique: " + old)
        mutated = source.replace(old, new, 1)
        try:
            check_source(mutated)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + old)
    return rejected


def parse_output(output):
    require(output.count("PHASE1_SAVECONVERTER_DONE\n") == 1,
            "native Qt harness did not finish")
    observed = {}
    pattern = re.compile(
        r"^PHASE1_SAVECONVERTER_CASE "
        r"(full|short|negative|open_failure) "
        r"requested=(\d+) accepted=(\d+) qt_write=(-?\d+) "
        r"close=(\d+) dialogs=(\d+)$",
        re.M,
    )
    for match in pattern.finditer(output):
        stage = match.group(1)
        require(stage not in observed, "duplicate native stage: " + stage)
        actual = tuple(int(value) for value in match.groups()[1:])
        require(actual == STAGES[stage],
                "native stage differs from expected " + stage + ": " + repr(actual))
        observed[stage] = actual
    require(set(observed) == set(STAGES), "missing native Qt cases")
    return observed


def validate(evidence):
    require(evidence["original_convert_body_executed"] is True,
            "source body provenance missing")
    require(evidence["native_qt6_qiodevice"] is True,
            "native Qt6 QIODevice execution missing")
    require(evidence["source_mutations_rejected"] == 3,
            "source negative controls missing")
    require(evidence["evidence_mutations_rejected"] == 11,
            "evidence negative controls missing")
    require(evidence["cases"] == STAGES, "native write cases changed")
    require(evidence["qfile_execution"] is False,
            "custom QIODevice must not be represented as QFile")
    require(evidence["native_filesystem_or_kernel_failure"] is False,
            "fault injection must not be represented as a real filesystem failure")
    require(evidence["stock_gameplay"] is False and
            evidence["sav_file_interoperability"] is False and
            evidence["physical_flash"] is False,
            "evidence scope was overclaimed")
    require(evidence["independent_approvals"] == 0 and
            evidence["gate"] == "FAIL_INCOMPLETE",
            "Phase 1 approval/gate status changed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    def git(*command):
        return subprocess.check_output(
            ["git", "-C", str(args.checkout), *command], text=True
        ).strip()

    require(git("rev-parse", "HEAD") == PIN, "wrong pinned mGBA commit")
    require(git("rev-parse", "HEAD:" + SOURCE) == BLOB,
            "pinned SaveConverter tree blob mismatch")
    require(git("hash-object", SOURCE) == BLOB,
            "pinned SaveConverter worktree blob mismatch")
    source = (args.checkout / SOURCE).read_text(encoding="utf-8")
    body = check_source(source)
    source_mutation_count = source_mutations(source)
    require(source_mutation_count == 3, "not all source mutations were rejected")

    inserted = body.replace("QFile", "FaultInjectingDevice")
    require(inserted != body and body.count("QFile") == 1,
            "test adapter substitution changed")
    harness = args.harness.read_text(encoding="utf-8")
    marker = "PHASE1_INSERT_PINNED_CONVERT_BODY"
    require(harness.count(marker) == 1, "harness extraction marker drift")
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-saveconverter-") as directory:
        source_path = Path(directory) / "saveconverter.cpp"
        binary_path = Path(directory) / "saveconverter"
        source_path.write_text(harness.replace(marker, inserted), encoding="utf-8")
        flags = subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "Qt6Core"], text=True
        ).split()
        compile_result = subprocess.run(
            ["g++", "-std=c++17", "-fPIC", "-O0", "-Wall", "-Wextra",
             "-Werror", str(source_path), "-o", str(binary_path), *flags],
            text=True, capture_output=True,
        )
        require(compile_result.returncode == 0,
                "native Qt6 compile failed: " + compile_result.stderr[-4000:])
        run = subprocess.run([str(binary_path)], text=True, capture_output=True)
        require(run.returncode == 0,
                "native Qt6 harness failed: " + run.stdout + run.stderr)
        cases = parse_output(run.stdout + run.stderr)

    evidence = {
        "class": "PINNED_MGBA_SAVECONVERTER_NATIVE_QT6_QIODEVICE_FAULT_INJECTION",
        "mgba_commit": PIN,
        "saveconverter_cpp_git_blob": BLOB,
        "saveconverter_cpp_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "original_convert_body_executed": True,
        "native_qt6_qiodevice": True,
        "qfile_execution": False,
        "native_filesystem_or_kernel_failure": False,
        "source_mutations_rejected": source_mutation_count,
        "evidence_mutations_rejected": 11,
        "cases": cases,
        "stock_gameplay": False,
        "sav_file_interoperability": False,
        "physical_flash": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    validate(evidence)
    for change in (
        {"original_convert_body_executed": False},
        {"native_qt6_qiodevice": False},
        {"source_mutations_rejected": 2},
        {"qfile_execution": True},
        {"native_filesystem_or_kernel_failure": True},
        {"cases": {}},
        {"stock_gameplay": True},
        {"sav_file_interoperability": True},
        {"physical_flash": True},
        {"independent_approvals": 1},
        {"gate": "PASS"},
    ):
        try:
            validate({**evidence, **change})
        except ValueError:
            continue
        raise ValueError("evidence mutation escaped: " + repr(change))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
