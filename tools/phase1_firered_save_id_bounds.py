#!/usr/bin/env python3
"""Host-sanitizer witness for pinned FireRed save-sector ID bounds.

Uses unmodified extracted C functions and mocked flash. Not GBA/mGBA runtime.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {"src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
         "include/save.h": "87fb9b615b434b58823d15688056695acda9feab"}
NAMES = ("CopySaveSlotData", "GetSaveValidStatus")
ANCHORS = {
 "CopySaveSlotData": (r"id\s*=\s*gSaveDataBufferPtr->id\s*;",
                      r"CalculateChecksum\(gSaveDataBufferPtr->data,\s*locations\[id\]\.size\)",
                      r"if\s*\(gSaveDataBufferPtr->signature\s*==\s*SECTOR_SIGNATURE"),
 "GetSaveValidStatus": (r"locations\[gSaveDataBufferPtr->id\]\.size",
                        r"validSectors\s*\|=\s*1\s*<<\s*gSaveDataBufferPtr->id",
                        r"if\s*\(gSaveDataBufferPtr->signature\s*==\s*SECTOR_SIGNATURE\)")}

def extract(source, name):
    m = re.search(r"static u8\s+" + name + r"\s*\([^;{}]*\)\s*\{", source)
    if not m:
        raise ValueError("Missing function " + name)
    depth = 0
    for i in range(m.end() - 1, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[m.start():i+1]
    raise ValueError("Unclosed function " + name)

def check(source, header):
    for needle in ("#define NUM_SECTORS_PER_SLOT         14",
                   "#define NUM_SAVE_SLOTS 2",
                   "#define SECTOR_SIGNATURE 0x08012025"):
        if needle not in header:
            raise ValueError("Header contract missing: " + needle)
    for name, patterns in ANCHORS.items():
        function = extract(source, name)
        for pattern in patterns:
            if not re.search(pattern, function):
                raise ValueError("Source contract missing: " + name + " " + pattern)

PRE = r"""
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef u8 bool8;
#define TRUE 1
#define FALSE 0
#define NUM_SECTORS_PER_SLOT 14
#define NUM_SAVE_SLOTS 2
#define SECTOR_SIGNATURE 0x08012025
#define SAVE_STATUS_EMPTY 0
#define SAVE_STATUS_OK 1
#define SAVE_STATUS_INVALID 2
#define SAVE_STATUS_ERROR 0xFF
struct SaveSectorLocation { u8 *data; u16 size; };
struct SaveSector { u8 data[3968]; u8 unused[116]; u16 id; u16 checksum; u32 signature; u32 counter; };
static struct SaveSector fixture[28], current;
static struct SaveSector *gSaveDataBufferPtr = &current;
static u32 gSaveCounter;
static u16 gLastWrittenSector;
static u8 ReadFlashSector(u8 n, struct SaveSector *p) { *p = fixture[n]; return 1; }
static u16 CalculateChecksum(void *data, u16 size) { (void)data; (void)size; return 0; }
"""
POST = r"""
int main(int argc, char **argv) {
    struct SaveSectorLocation locations[NUM_SECTORS_PER_SLOT] = {{0}};
    if (argc != 2) return 91;
    for (unsigned i = 0; i < 28; ++i) {
        fixture[i].id = i % 14;
        fixture[i].signature = SECTOR_SIGNATURE;
        fixture[i].checksum = 0;
        fixture[i].counter = i < 14 ? 1 : 2;
    }
    if (!strcmp(argv[1], "valid-status")) {
        u8 s = GetSaveValidStatus(locations);
        if (s != SAVE_STATUS_OK || gSaveCounter != 2) return 92;
        puts("VALID_STATUS_OK"); return 0;
    }
    if (!strcmp(argv[1], "valid-copy")) {
        gSaveCounter = 2;
        if (CopySaveSlotData(0, locations) != SAVE_STATUS_OK) return 93;
        puts("VALID_COPY_OK"); return 0;
    }
    if (!strcmp(argv[1], "mixed-slot-last-new")) {
        /* 13 old counter values and one newer last physical sector. */
        fixture[13].counter = 10;
        u8 s = GetSaveValidStatus(locations);
        if (s != SAVE_STATUS_OK || gSaveCounter != 10) return 95;
        puts("VALID_MIXED_COUNTER_LAST_NEW"); return 0;
    }
    if (!strcmp(argv[1], "mixed-slot-last-old")) {
        /* 13 newer counter values and one older last physical sector. */
        for (unsigned i = 0; i < 13; ++i) fixture[i].counter = 11;
        u8 s = GetSaveValidStatus(locations);
        if (s != SAVE_STATUS_OK || gSaveCounter != 2) return 96;
        puts("VALID_MIXED_COUNTER_LAST_OLD"); return 0;
    }
    if (!strcmp(argv[1], "invalid-status")) {
        fixture[0].id = 14;
        (void)GetSaveValidStatus(locations);
        puts("UNEXPECTED_RETURN"); return 0;
    }
    if (!strcmp(argv[1], "invalid-copy")) {
        fixture[0].id = 14;
        fixture[0].signature = 0; /* Invalid signature does not prevent index. */
        (void)CopySaveSlotData(0, locations);
        puts("UNEXPECTED_RETURN"); return 0;
    }
    return 94;
}
"""

def run(args):
    root = Path(args.source_dir)
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != PIN:
        raise ValueError("Wrong pinned commit: " + head)
    data = {}
    for path, sha in BLOBS.items():
        raw = (root/path).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if actual != sha:
            raise ValueError("Wrong Git blob for " + path)
        data[path] = raw.decode("utf-8")
    source, header = data["src/save.c"], data["include/save.h"]
    check(source, header)
    negatives = 0
    for needle in ("locations[id].size", "locations[gSaveDataBufferPtr->id].size"):
        altered = source.replace(needle, "locations[0].size")
        if altered == source:
            raise ValueError("Missing mutation target")
        try:
            check(altered, header)
        except ValueError:
            negatives += 1
        else:
            raise ValueError("Mutation incorrectly accepted")
    compiler = args.cc or shutil.which("clang") or shutil.which("gcc")
    if not compiler:
        raise ValueError("Clang/GCC unavailable")
    code = PRE + "\n".join(extract(source, name) for name in NAMES) + POST
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/"test.c"
        exe = Path(tmp)/"test"
        path.write_text(code)
        build = subprocess.run([compiler, "-std=gnu11", "-O0", "-g", "-fno-omit-frame-pointer",
                                "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                                str(path), "-o", str(exe)], capture_output=True, text=True)
        if build.returncode:
            raise ValueError("Host compilation failed: " + build.stderr[:1500])
        for case in ("valid-status", "valid-copy", "mixed-slot-last-new", "mixed-slot-last-old", "invalid-status", "invalid-copy"):
            p = subprocess.run([str(exe), case], capture_output=True, text=True,
                               env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1"},
                               timeout=20)
            output = p.stdout + p.stderr
            diagnostic = bool(re.search(r"AddressSanitizer|runtime error:|UndefinedBehaviorSanitizer", output))
            if case.startswith(("valid", "mixed")):
                if p.returncode or "VALID_" not in output or diagnostic:
                    raise ValueError("Valid control failed: " + case + ": " + output[:500])
            elif p.returncode == 0 or not diagnostic:
                raise ValueError("Malformed control lacks sanitizer evidence: " + case + ": " + output[:500])
            results[case] = {"exit_code": p.returncode, "sanitizer_diagnostic": diagnostic}
    report = {"pinned_commit": PIN, "source_git_blobs": BLOBS, "functions_extracted_unchanged": NAMES,
              "source_anchors": sum(map(len, ANCHORS.values())),
              "negative_source_mutations": negatives, "host_compiler": compiler,
              "tests": results, "kind": "HOST_C_SANITIZER_MOCK_FLASH",
              "new_unique_machine_processed_files": 0,
              "analyst_prepared_whole_files_added": 0, "independent_approvals": 0,
              "phase1": "FAIL_INCOMPLETE",
              "limitations": ["Not an original agbcc/ARM build", "Not a real flash or mGBA runtime",
                              "Mock checksums are zero; no player-facing reachability established"]}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cc")
    try:
        run(parser.parse_args())
    except Exception as exc:
        parser.exit(2, "FAIL_CLOSED: " + str(exc) + "\n")
