#!/usr/bin/env python3
"""Phase 1: host-execute unchanged pinned FireRed map-script dispatch bodies.

Lookup and script execution are host stubs. Not mGBA or malformed-table safety.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/script.c": "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
    "include/constants/map_scripts.h": "1353de360cf1e00b6efbb26ec59c4822c99b59bf",
    "include/constants/quest_log.h": "fe284ba133ccc28053515c501979741b3960212f",
}
WRAPPERS = {
    "RunOnLoadMapScript": "MAP_SCRIPT_ON_LOAD",
    "RunOnTransitionMapScript": "MAP_SCRIPT_ON_TRANSITION",
    "RunOnResumeMapScript": "MAP_SCRIPT_ON_RESUME",
    "RunOnReturnToFieldMapScript": "MAP_SCRIPT_ON_RETURN_TO_FIELD",
    "RunOnDiveWarpMapScript": "MAP_SCRIPT_ON_DIVE_WARP",
}
NAMES = ("MapHeaderRunScriptType", *WRAPPERS,
         "TryRunOnFrameMapScript", "TryRunOnWarpIntoMapScript")
EXPECTED = "HOST_EXTRACTED_FIRERED_MAP_SCRIPT_DISPATCH PASS cases=16 gate=FAIL_INCOMPLETE approvals=0"

def require(ok, why):
    if not ok:
        raise ValueError(why)

def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def extract_one(source, name):
    pattern = (r"(?m)^(?:static\s+)?(?:void|bool8)\s+"
               + re.escape(name) + r"\s*\([^;{}]*\)\s*\{")
    hits = list(re.finditer(pattern, source))
    require(len(hits) == 1, "missing/duplicate function body: " + name)
    match = hits[0]
    depth = 0
    for pos in range(match.end()-1, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():pos+1]
    raise ValueError("unterminated function body: " + name)

def contract(source, map_header, quest_header):
    functions = {name: extract_one(source, name) for name in NAMES}
    run = functions["MapHeaderRunScriptType"]
    for token in ("MapHeaderGetScriptTable(tag);",
                  "if (ptr != NULL)", "RunScriptImmediately(ptr);"):
        require(token in run, "direct-dispatch contract drift: " + token)
    for name, tag in WRAPPERS.items():
        require("MapHeaderRunScriptType(" + tag + ");" in functions[name],
                "wrapper tag/dispatch drift: " + name)
    frame = functions["TryRunOnFrameMapScript"]
    for token in ("if (gQuestLogState == QL_STATE_PLAYBACK_LAST)",
                  "MapHeaderCheckScriptTable(MAP_SCRIPT_ON_FRAME_TABLE);",
                  "if (!ptr)", "ScriptContext_SetupScript(ptr);", "return TRUE;"):
        require(token in frame, "frame-table dispatch drift: " + token)
    warp = functions["TryRunOnWarpIntoMapScript"]
    for token in ("MapHeaderCheckScriptTable(MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE);",
                  "if (ptr)", "RunScriptImmediately(ptr);"):
        require(token in warp, "warp-table dispatch drift: " + token)
    expected = {
        "MAP_SCRIPT_ON_LOAD": 1, "MAP_SCRIPT_ON_FRAME_TABLE": 2,
        "MAP_SCRIPT_ON_TRANSITION": 3, "MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE": 4,
        "MAP_SCRIPT_ON_RESUME": 5, "MAP_SCRIPT_ON_DIVE_WARP": 6,
        "MAP_SCRIPT_ON_RETURN_TO_FIELD": 7, "QL_STATE_PLAYBACK": 2,
        "QL_STATE_PLAYBACK_LAST": 3,
    }
    for name, value in expected.items():
        header = quest_header if name.startswith("QL_") else map_header
        hits = re.findall(r"(?m)^#define\s+" + re.escape(name)
                          + r"\s+([0-9]+)(?:\s|$)", header)
        require(len(hits) == 1 and int(hits[0]) == value,
                "pinned map/quest-log tag changed: " + name)
    return functions, expected

def negative_controls(source, maps, quest):
    variants = []
    def change(label, key, old, new):
        original = {"source": source, "maps": maps, "quest": quest}[key]
        require(old in original, "mutation anchor missing: " + label)
        edited = original.replace(old, new, 1)
        variants.append((label, edited if key == "source" else source,
                         edited if key == "maps" else maps,
                         edited if key == "quest" else quest))
    change("dispatch-guard", "source", "if (ptr != NULL)", "if (ptr == NULL)")
    for name, tag in WRAPPERS.items():
        change("wrong-tag-" + name, "source",
               "MapHeaderRunScriptType(" + tag + ");",
               "MapHeaderRunScriptType(99);")
    change("frame-playback-gate", "source",
           "if (gQuestLogState == QL_STATE_PLAYBACK_LAST)",
           "if (gQuestLogState != QL_STATE_PLAYBACK_LAST)")
    change("frame-setup", "source",
           "ScriptContext_SetupScript(ptr);", "RunScriptImmediately(ptr);")
    change("warp-tag", "source",
           "MapHeaderCheckScriptTable(MAP_SCRIPT_ON_WARP_INTO_MAP_TABLE);",
           "MapHeaderCheckScriptTable(MAP_SCRIPT_ON_FRAME_TABLE);")
    change("map-constant", "maps",
           "#define MAP_SCRIPT_ON_FRAME_TABLE          2",
           "#define MAP_SCRIPT_ON_FRAME_TABLE          8")
    change("quest-constant", "quest",
           "#define QL_STATE_PLAYBACK_LAST 3",
           "#define QL_STATE_PLAYBACK_LAST 9")
    rejected = []
    for label, s, m, q in variants:
        try:
            contract(s, m, q)
        except ValueError:
            rejected.append(label)
        else:
            raise AssertionError("source mutation escaped: " + label)
    return rejected

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firered", type=Path, required=True)
    ap.add_argument("--test", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    revision = subprocess.check_output(
        ["git", "-C", str(args.firered), "rev-parse", "HEAD"],
        text=True).strip()
    require(revision == PIN, "pinned FireRed revision drift")
    sources = {}
    for path, expected in BLOBS.items():
        raw = (args.firered / path).read_bytes()
        require(blob(raw) == expected, "pinned source blob drift: " + path)
        sources[path] = raw.decode()
    source, maps, quest = (sources[k] for k in BLOBS)
    functions, constants = contract(source, maps, quest)
    rejected = negative_controls(source, maps, quest)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        extracted = "\n\n".join(functions[name] for name in NAMES) + "\n"
        (root / "phase1_dispatch_functions.inc").write_text(extracted)
        header = "".join(f"#define {name} {value}\n"
                         for name, value in constants.items())
        (root / "phase1_dispatch_constants.inc").write_text(header)
        binary = root / "host-dispatch"
        subprocess.run(["cc", "-std=gnu11", "-O0", "-Wall", "-Wextra",
                        "-Werror", "-I", str(root), str(args.test),
                        "-o", str(binary)], check=True)
        stdout = subprocess.check_output([str(binary)], text=True).strip()
    require(stdout == EXPECTED, "host dispatch execution drift")
    mutants = (
        stdout.replace("cases=16", "cases=15"),
        stdout.replace("PASS", "FAIL"),
        stdout.replace("FAIL_INCOMPLETE", "PASS"),
        stdout.replace("approvals=0", "approvals=1"),
    )
    require(all(x != EXPECTED for x in mutants), "output mutation escaped")
    result = {
        "class": "PINNED_SOURCE_EXTRACTED_MAP_SCRIPT_DISPATCH_HOST_C",
        "firered_revision": PIN, "source_blobs": BLOBS,
        "functions_extracted": list(NAMES),
        "extracted_c_sha256": hashlib.sha256(extracted.encode()).hexdigest(),
        "constants": constants, "host_cases_passed": 16,
        "source_mutations_rejected": rejected,
        "output_mutations_rejected": len(mutants),
        "limitations": [
            "Pinned C dispatch bodies executed on host with lookup and script stubs",
            "No mGBA instruction execution or arbitrary malformed-table native safety",
            "DIVE_WARP wrapper existence does not prove gameplay reachability",
            "No independent complete-file semantic disposition",
        ],
        "phase1_gate": "FAIL_INCOMPLETE", "independent_approvals": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
