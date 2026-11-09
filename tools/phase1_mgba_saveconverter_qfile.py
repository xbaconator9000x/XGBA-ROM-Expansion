#!/usr/bin/env python3
"""Execute the pinned SaveConverter::convert body through native Qt6 QFile."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
SOURCE = "src/platform/qt/SaveConverter.cpp"
SOURCE_BLOB = "4c32280c9c5288e806ffd237119186e2a633c4a7"
SOURCE_SHA256 = "3a6498a4fa69064d9b3723b49398cfe9d8e827ada3d8be26215db3a5ead2184f"
FIXTURE_SHA256 = "9ac9be1aaaf91bbf3d818f791f839f76ba76ce00a556d5f7462f1392cf7fcd55"
CONVERT_BODY_SHA256 = "d38981bdacba444256aa2dc69f8d856d95321fb2ed18aff8a3e99c45d66ef410"
BODY_ANCHORS = (
    "QByteArray converted = input.convertTo(output);",
    "QFile out(m_ui.outputFile->text());",
    "if (out.open(QIODevice::WriteOnly | QIODevice::Truncate)) {",
    "out.write(converted);",
    "out.close();",
    'tr("Failed to open output file.")',
)
CASE_PATTERN = re.compile(
    r"^PHASE1_QFILE_CASE temporary open=(\d) open_error=(-?\d+) "
    r"write=(-?\d+) "
    r"write_error=(-?\d+) close=(\d) close_error=(-?\d+) "
    r"bytes_match=(\d) dialogs=(\d)$\n"
    r"^PHASE1_QFILE_CASE dev_full open=(\d) open_error=(-?\d+) "
    r"write=(-?\d+) "
    r"write_error=(-?\d+) close=(\d) close_error=(-?\d+) "
    r"close_error_text_hex=([0-9a-f]+) bytes_match=(\d) dialogs=(\d)$\n"
    r"^PHASE1_QFILE_CASE open_failure open=(\d) open_error=(-?\d+) "
    r"open_error_text_hex=([0-9a-f]+) write=(-?\d+) close=(\d) dialogs=(\d)$",
    re.M,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *command):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *command], text=True
    ).strip()


def extract_body(source):
    signature = "void SaveConverter::convert()"
    require(source.count(signature) == 1, "missing or ambiguous pinned convert()")
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                body = source[start:offset + 1]
                for anchor in BODY_ANCHORS:
                    require(body.count(anchor) == 1,
                            "pinned convert() anchor drift: " + anchor)
                return body
    raise ValueError("unbalanced pinned convert() body")


def reject_source_mutations(source):
    mutations = (
        ("out.write(converted);",
         "if (out.write(converted) != converted.size()) return;"),
        ("if (out.open(QIODevice::WriteOnly | QIODevice::Truncate)) {",
         "if (!out.open(QIODevice::WriteOnly | QIODevice::Truncate)) {"),
        ("out.close();", "/* close removed */"),
    )
    for original, replacement in mutations:
        require(source.count(original) == 1,
                "mutation anchor is not unique: " + original)
        mutated = source.replace(original, replacement, 1)
        try:
            extract_body(mutated)
        except ValueError:
            continue
        raise ValueError("source mutation escaped: " + original)
    return len(mutations)


def parse_output(output):
    end_marker = "\nPHASE1_QFILE_DONE\n"
    require(output.endswith(end_marker) and
            output.count("PHASE1_QFILE_DONE\n") == 1,
            "native QFile output missing unique terminal marker")
    match = CASE_PATTERN.fullmatch(output[:-len(end_marker)])
    require(match is not None, "native QFile observations missing or malformed")
    groups = match.groups()
    text_groups = {14, 19}
    values = tuple(int(value) for index, value in enumerate(groups)
                   if index not in text_groups)
    temporary = values[:8]
    dev_full = values[8:16]
    close_error_text_hex = groups[14]
    open_failure = values[16:21]
    open_error_text_hex = groups[19]
    require(temporary[0] == 1 and temporary[1] == 0 and
            temporary[2] == len("pinned-converter-qfile-payload") and
            temporary[3] == 0 and
            temporary[4] == 1 and temporary[5] == 0 and
            temporary[6] == 1 and temporary[7] == 0,
            "native temporary-file QFile control did not persist exact payload")
    require(dev_full[0] == 1 and dev_full[1] == 0 and
            dev_full[2] == temporary[2] and dev_full[3] == 0 and
            dev_full[4] == 1 and dev_full[5] == 4 and
            bytes.fromhex(close_error_text_hex).decode("utf-8") ==
            "No space left on device" and
            dev_full[6:8] == (0, 0),
            "native /dev/full QFile write/close error not observed as expected")
    require(open_failure[0] == 0 and open_failure[1] == 5 and
            bool(open_error_text_hex) and open_failure[2] == -2 and
            open_failure[3] == 0 and open_failure[4] == 1,
            "native QFile failed-open warning control changed")
    return {
        "temporary": {
            "open": temporary[0],
            "error_after_open": temporary[1],
            "write_return": temporary[2],
            "error_after_write": temporary[3],
            "close_called": temporary[4],
            "error_after_close": temporary[5],
            "payload_matches": temporary[6],
            "dialogs": temporary[7],
        },
        "dev_full": {
            "open": dev_full[0],
            "error_after_open": dev_full[1],
            "write_return": dev_full[2],
            "error_after_write": dev_full[3],
            "close_called": dev_full[4],
            "error_after_close": dev_full[5],
            "close_error_text_hex": close_error_text_hex,
            "payload_matches": dev_full[6],
            "dialogs": dev_full[7],
        },
        "open_failure": {
            "open": open_failure[0],
            "error_after_open": open_failure[1],
            "open_error_text_hex": open_error_text_hex,
            "write_not_called": open_failure[2] == -2,
            "close_called": open_failure[3],
            "dialogs": open_failure[4],
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path)
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    require(bool(args.checkout) != bool(args.source_file),
            "provide exactly one of --checkout or --source-file")
    if args.checkout:
        checkout = args.checkout.resolve()
        require(git(checkout, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA revision")
        require(git(checkout, "rev-parse", "HEAD:" + SOURCE) == SOURCE_BLOB,
                "pinned SaveConverter tree blob changed")
        require(git(checkout, "hash-object", SOURCE) == SOURCE_BLOB,
                "pinned SaveConverter worktree blob changed")
        source_path = checkout / SOURCE
    else:
        source_path = args.source_file.resolve()
        require(subprocess.check_output(
            ["git", "hash-object", str(source_path)], text=True
        ).strip() == SOURCE_BLOB, "pinned SaveConverter source blob changed")
    source_bytes = source_path.read_bytes()
    require(hashlib.sha256(source_bytes).hexdigest() == SOURCE_SHA256,
            "pinned SaveConverter SHA-256 changed")
    source = source_bytes.decode("utf-8")
    body = extract_body(source)
    require(hashlib.sha256(body.encode()).hexdigest() == CONVERT_BODY_SHA256,
            "pinned convert() body SHA-256 changed")
    rejected = reject_source_mutations(source)
    harness = args.harness.read_text(encoding="utf-8")
    require(FIXTURE_SHA256 is None or
            hashlib.sha256(harness.encode()).hexdigest() == FIXTURE_SHA256,
            "native QFile fixture SHA-256 changed")
    marker = "PHASE1_INSERT_PINNED_CONVERT_BODY"
    require(harness.count(marker) == 1, "harness extraction marker drift")
    expanded = harness.replace(marker, body)

    flags = subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "Qt6Core"], text=True
    ).split()
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-qfile-") as directory:
        directory = Path(directory)
        cpp = directory / "qfile.cpp"
        binary = directory / "qfile"
        cpp.write_text(expanded, encoding="utf-8")
        compile_result = subprocess.run(
            ["g++", "-std=c++17", "-fPIC", "-O0", "-g", "-Wall",
             "-Wextra", "-Werror", str(cpp), "-o", str(binary), *flags],
            text=True,
            capture_output=True,
            timeout=60,
        )
        require(compile_result.returncode == 0,
                "native Qt6 QFile harness compile failed: " +
                compile_result.stderr[-8000:])
        run = subprocess.run(
            [str(binary)], text=True, capture_output=True, timeout=20
        )
        require(run.returncode == 0,
                "native Qt6 QFile harness failed: " +
                run.stdout + run.stderr)
        output = run.stdout + run.stderr

    cases = parse_output(output)
    evidence = {
        "class": "PINNED_MGBA_SAVECONVERTER_NATIVE_QT6_QFILE",
        "mgba_commit": PIN,
        "saveconverter_cpp_git_blob": SOURCE_BLOB,
        "saveconverter_cpp_sha256": SOURCE_SHA256,
        "convert_body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "fixture_sha256": hashlib.sha256(harness.encode()).hexdigest(),
        "original_convert_body_executed": True,
        "native_qfile": True,
        "qiodevice_fault_injection": False,
        "uses_real_linux_dev_full": True,
        "source_mutations_rejected": rejected,
        "qt6_core_version": subprocess.check_output(
            ["pkg-config", "--modversion", "Qt6Core"], text=True
        ).strip(),
        "cases": cases,
        "stock_gameplay": False,
        "sav_file_interoperability": False,
        "physical_flash": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
