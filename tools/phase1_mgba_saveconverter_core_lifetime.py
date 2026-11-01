#!/usr/bin/env python3
"""Run the pinned SaveConverter getStatePlatform body under host sanitizers."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
SOURCE = "src/platform/qt/SaveConverter.cpp"
BLOB = "4c32280c9c5288e806ffd237119186e2a633c4a7"
SOURCE_SHA256 = "3a6498a4fa69064d9b3723b49398cfe9d8e827ada3d8be26215db3a5ead2184f"
BODY_SHA256 = "9b7ebec69806b91569e19422c4269b20d24d6ff2691333d783a1f17c2e00d83b"
BODY_START = 10913
BODY_END = 11841
MARKER = "PHASE1_INSERT_PINNED_GET_STATE_PLATFORM"
SANITIZER = "AddressSanitizer: heap-use-after-free"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def extract_body(source):
    needle = "mPlatform SaveConverter::getStatePlatform(VFile* vf) {"
    require(source.count(needle) == 1, "missing or ambiguous pinned getStatePlatform()")
    start = source.index(needle)
    depth = 0
    for offset in range(source.index("{", start), len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return start, offset + 1, source[start:offset + 1]
    raise ValueError("unbalanced pinned getStatePlatform() body")


def check_body(source):
    start, end, body = extract_body(source)
    require(start == BODY_START and end == BODY_END,
            "pinned getStatePlatform() byte anchors drifted")
    require(hashlib.sha256(body.encode()).hexdigest() == BODY_SHA256,
            "pinned getStatePlatform() function digest mismatch")
    anchors = {
        "#ifdef M_CORE_GBA\n": 1,
        "state = mCoreExtractState(core, vf, nullptr);": 2,
        "core->deinit(core);": 2,
        "mappedMemoryFree(state, core->stateSize(core));": 2,
        "#ifdef M_CORE_GB\n": 1,
        "core = GBACoreCreate();": 1,
        "core = GBCoreCreate();": 1,
    }
    for anchor, count in anchors.items():
        require(body.count(anchor) == count, "function source anchor drift: " + anchor)
    gba_deinit = body.index("core->deinit(core);")
    gba_release = body.index("mappedMemoryFree(state, core->stateSize(core));")
    gb_branch = body.index("#ifdef M_CORE_GB")
    gb_deinit = body.index("core->deinit(core);", gb_branch)
    gb_release = body.index("mappedMemoryFree(state, core->stateSize(core));", gb_branch)
    require(gba_deinit < gba_release and gb_deinit < gb_release,
            "original deinit-before-stateSize ordering absent")
    return body


def check_source_mutations(source):
    mutations = (
        ("core->deinit(core);\n\t\tif (state) {",
         "size_t cachedSize = core->stateSize(core);\n\t\tcore->deinit(core);\n\t\tif (state) {"),
        ("mappedMemoryFree(state, core->stateSize(core));",
         "mappedMemoryFree(state, 16);"),
        ("core->deinit(core);", "/* core deinit removed */"),
    )
    rejected = 0
    for old, new in mutations:
        require(source.count(old) >= 1, "mutation anchor missing: " + old)
        mutated = source.replace(old, new, 1)
        try:
            check_body(mutated)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + old)
    require(rejected == len(mutations), "not all source mutations were rejected")
    return rejected


def run_case(binary, name, sanitizer_env):
    result = subprocess.run(
        [str(binary), name],
        text=True,
        capture_output=True,
        env=sanitizer_env,
        timeout=10,
    )
    combined = result.stdout + result.stderr
    require(result.returncode != 0, name + " did not terminate with sanitizer failure")
    require(SANITIZER in combined, name + " lacked heap-use-after-free diagnostic")
    require("mock_deinit" in combined,
            name + " diagnostic did not identify the freeing callback")
    diagnostic_excerpt = [
        line.strip()
        for line in result.stderr.splitlines()
        if "ERROR: AddressSanitizer:" in line
        or "READ of size" in line
        or "getStatePlatform" in line
        or "mock_deinit" in line
    ]
    require(any("getStatePlatform" in line for line in diagnostic_excerpt),
            name + " diagnostic did not identify the original body frame")
    return {
        "exit_code": result.returncode,
        "diagnostic": SANITIZER,
        "free_callback_seen": True,
        "diagnostic_excerpt": diagnostic_excerpt[:8],
    }


def validate(evidence):
    require(evidence["pinned_source_body_executed"] is True,
            "pinned source body provenance missing")
    require(evidence["compiler_sanitizers"] == ["address", "undefined"],
            "ASan/UBSan evidence missing")
    require(set(evidence["cases"]) == {"gba_nonnull", "gb_nonnull", "null_control"},
            "required core-lifetime cases missing")
    require(evidence["cases"]["gba_nonnull"]["diagnostic"] == SANITIZER and
            evidence["cases"]["gb_nonnull"]["diagnostic"] == SANITIZER,
            "non-null cases lack expected ASan finding")
    require(evidence["cases"]["null_control"]["exit_code"] == 0,
            "null-state control failed")
    require(evidence["source_mutations_rejected"] == 3,
            "source mutation controls missing")
    require(evidence["real_mgba_core"] is False and
            evidence["full_qt_application"] is False and
            evidence["sav_interoperability"] is False and
            evidence["stock_gameplay"] is False and
            evidence["physical_flash"] is False,
            "controlled native harness evidence was overclaimed")
    require(evidence["independent_approvals"] == 0 and
            evidence["gate"] == "FAIL_INCOMPLETE",
            "approval or gate status changed")


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
    raw_source = (args.checkout / SOURCE).read_bytes()
    require(hashlib.sha256(raw_source).hexdigest() == SOURCE_SHA256,
            "pinned SaveConverter SHA-256 mismatch")
    source = raw_source.decode("utf-8")
    body = check_body(source)
    source_mutation_count = check_source_mutations(source)
    require(body.count("core->deinit(core);") == 2,
            "both optional-core source branches must be present")
    harness = args.harness.read_text(encoding="utf-8")
    require(harness.count(MARKER) == 1, "harness extraction marker drift")
    flags = [
        "g++", "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
        "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
        "-fno-sanitize-recover=all",
    ]
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-core-lifetime-") as directory:
        directory = Path(directory)
        source_path = directory / "core_lifetime.cpp"
        binary_path = directory / "core_lifetime"
        source_path.write_text(harness.replace(MARKER, body), encoding="utf-8")
        compile_result = subprocess.run(
            [*flags, str(source_path), "-o", str(binary_path)],
            text=True,
            capture_output=True,
            timeout=30,
        )
        require(compile_result.returncode == 0,
                "sanitizer compile failed: " + compile_result.stderr[-4000:])
        sanitizer_env = os.environ.copy()
        sanitizer_env["ASAN_OPTIONS"] = "detect_leaks=0:halt_on_error=1:abort_on_error=0"
        sanitizer_env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        cases = {
            "gba_nonnull": run_case(binary_path, "gba", sanitizer_env),
            "gb_nonnull": run_case(binary_path, "gb", sanitizer_env),
        }
        null_result = subprocess.run(
            [str(binary_path), "null"],
            text=True,
            capture_output=True,
            env=sanitizer_env,
            timeout=10,
        )
        require(null_result.returncode == 0,
                "null-state control failed: " + null_result.stdout + null_result.stderr)
        require("PHASE1_CORE_LIFETIME_NULL_CONTROL platform=0" in null_result.stdout,
                "null-state control produced unexpected platform result")
        cases["null_control"] = {
            "exit_code": null_result.returncode,
            "platform": 0,
        }
        compiler_version = subprocess.check_output(
            ["g++", "--version"], text=True
        ).splitlines()[0]

    evidence = {
        "class": "PINNED_MGBA_SAVECONVERTER_GET_STATE_PLATFORM_ASAN",
        "mgba_commit": PIN,
        "saveconverter_cpp_git_blob": BLOB,
        "saveconverter_cpp_sha256": SOURCE_SHA256,
        "function_byte_range": [BODY_START, BODY_END],
        "function_sha256": BODY_SHA256,
        "fixture_sha256": hashlib.sha256(harness.encode()).hexdigest(),
        "compiler": compiler_version,
        "compile_flags": flags[1:],
        "compiler_sanitizers": ["address", "undefined"],
        "pinned_source_body_executed": True,
        "cases": cases,
        "source_mutations_rejected": source_mutation_count,
        "real_mgba_core": False,
        "full_qt_application": False,
        "sav_interoperability": False,
        "stock_gameplay": False,
        "physical_flash": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    validate(evidence)
    for change in (
        {"pinned_source_body_executed": False},
        {"compiler_sanitizers": []},
        {"source_mutations_rejected": 2},
        {"real_mgba_core": True},
        {"sav_interoperability": True},
        {"stock_gameplay": True},
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
