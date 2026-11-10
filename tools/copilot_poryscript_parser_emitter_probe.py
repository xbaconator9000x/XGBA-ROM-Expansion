#!/usr/bin/env python3
"""Probe numeric and sentinel behavior in the pinned Poryscript CLI."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


PORYSCRIPT_PIN = "c32481161c767b25a3425fa9f1f8729927ff3d55"
SOURCE_BLOBS = {
    "parser/parser.go": "3957939076696de0a3e701c223c53afffe8d1b0e",
    "parser/parser_test.go": "fdab86ecadc1ed1c01b2dcd639d70fc62ef2c980",
    "emitter/emitter.go": "d35843ef29929ead47351646d7a33dd5c692b850",
    "lexer/lexer.go": "34ef7b989e38a7f9f0f893809a55a72e995f1bb8",
}
NUMERIC_LITERALS = ("0", "0x", "0x10000", "-1", "65536")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def call(argv, cwd):
    return subprocess.run(
        argv, cwd=cwd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False
    )


def git_blob_sha1(data):
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data
    ).hexdigest()


def verify_sources(root, source_files_only):
    if (root / ".git").exists():
        revision = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        require(revision == PORYSCRIPT_PIN, "Poryscript revision mismatch")
        for path, expected in SOURCE_BLOBS.items():
            actual = subprocess.check_output(
                ["git", "-C", str(root), "hash-object", path], text=True
            ).strip()
            require(actual == expected, "Poryscript source blob mismatch: " + path)
        mode = "EXACT_PINNED_COMMIT_AND_BLOBS"
    else:
        require(source_files_only, "Poryscript checkout lacks .git metadata")
        for path, expected in SOURCE_BLOBS.items():
            source = root / path
            require(source.is_file(), "Poryscript source file missing: " + path)
            actual = git_blob_sha1(source.read_bytes())
            require(actual == expected, "Poryscript source blob mismatch: " + path)
        mode = "EXACT_PINNED_FILE_BLOBS"
    return mode


def run_probe(root, source_files_only=False):
    root = root.resolve()
    identity_mode = verify_sources(root, source_files_only)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        executable = temp / "poryscript"
        build = call(["go", "build", "-o", str(executable), "."], root)
        require(build.returncode == 0, "pinned Poryscript CLI build failed: " +
                build.stderr)
        numeric_cases = {}
        for literal in NUMERIC_LITERALS:
            fixture = (
                "mapscripts Probe_MapScripts {\n"
                "MAP_SCRIPT_ON_FRAME_TABLE [\n"
                f"VAR_TEST, {literal}: Probe_Target\n"
                "]\n}\n"
                "raw `\nProbe_Target:\n.byte 1\n`\n"
            )
            input_path = temp / "numeric.pory"
            input_path.write_text(fixture, encoding="utf-8")
            result = call([
                str(executable), "-cc", "", "-fc", "", "-lm=false",
                "-optimize=false", "-i", str(input_path),
            ], root)
            require(result.returncode == 0,
                    f"pinned CLI rejected conditional literal {literal!r}: "
                    f"{result.stderr}")
            anchor = f"map_script_2 VAR_TEST, {literal}, Probe_Target"
            require(anchor in result.stdout,
                    f"pinned CLI output did not preserve {literal!r}")
            require(result.stdout.count("\t.2byte 0") == 1,
                    "pinned CLI output lacks the separate conditional-table sentinel")
            numeric_cases[literal] = {
                "accepted": True,
                "emitted_anchor": anchor,
                "emitted_assembly_sha256":
                    hashlib.sha256(result.stdout.encode()).hexdigest(),
            }

        empty_fixture = (
            "mapscripts Probe_MapScripts {\n"
            "MAP_SCRIPT_ON_FRAME_TABLE []\n"
            "}\n"
        )
        empty_path = temp / "empty-table.pory"
        empty_path.write_text(empty_fixture, encoding="utf-8")
        empty_result = call([
            str(executable), "-cc", "", "-fc", "", "-lm=false",
            "-optimize=false", "-i", str(empty_path),
        ], root)
        require(empty_result.returncode == 0,
                "pinned CLI rejected an empty conditional table")
        require(empty_result.stdout.count("\t.2byte 0") == 1 and
                "map_script_2 " not in empty_result.stdout,
                "empty table did not emit exactly its separate zero sentinel")
        mutated_empty_output = empty_result.stdout.replace("\t.2byte 0\n", "", 1)
        sentinel_mutation_rejected = False
        try:
            require(mutated_empty_output.count("\t.2byte 0") == 1,
                    "conditional-table sentinel missing")
        except ValueError:
            sentinel_mutation_rejected = True
        require(sentinel_mutation_rejected,
                "missing-sentinel negative control escaped")

        malformed_cases = {
            "empty-condition": (
                "mapscripts Probe_MapScripts {\n"
                "MAP_SCRIPT_ON_FRAME_TABLE [ , 1: Probe_Target ]\n}\n",
                "expected condition for map script table entry, but it was empty",
            ),
            "missing-comma": (
                "mapscripts Probe_MapScripts {\n"
                "MAP_SCRIPT_ON_FRAME_TABLE [ VAR_TEST ]\n}\n",
                "missing ',' to specify map script table entry comparison value",
            ),
        }
        rejected_cases = {}
        for name, (fixture, expected_error) in malformed_cases.items():
            input_path = temp / (name + ".pory")
            input_path.write_text(fixture, encoding="utf-8")
            result = call([
                str(executable), "-cc", "", "-fc", "", "-lm=false",
                "-optimize=false", "-i", str(input_path),
            ], root)
            require(result.returncode != 0 and expected_error in result.stderr,
                    f"malformed table control was not rejected: {name}")
            rejected_cases[name] = "REJECTED_AS_EXPECTED"

        return {
            "status": "PASS_PINNED_PORYSCRIPT_CLI_PARSER_EMITTER_PROBE",
            "poryscript_commit": PORYSCRIPT_PIN,
            "identity_verification": identity_mode,
            "numeric_cases": numeric_cases,
            "empty_table": {
                "accepted": True,
                "conditional_records": 0,
                "separate_zero_sentinel_emitted": True,
                "emitted_assembly_sha256":
                    hashlib.sha256(empty_result.stdout.encode()).hexdigest(),
            },
            "negative_controls": {
                **rejected_cases,
                "mutated_away_empty_table_sentinel": (
                    "PASS_REJECTED_BY_SENTINEL_ASSERTION"
                ),
            },
            "execution_scope": (
                "Pinned Poryscript CLI output from small synthetic map-script "
                "fixtures; no assembler, ROM, interpreter, emulator, or gameplay."
            ),
            "phase1_gate": "FAIL_INCOMPLETE",
            "approval_count_changed": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poryscript-root", required=True, type=Path)
    parser.add_argument("--source-files-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_probe(args.poryscript_root, args.source_files_only)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
