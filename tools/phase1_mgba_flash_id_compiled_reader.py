#!/usr/bin/env python3
"""Compile exact pinned mGBA Flash ID reader with instrumented timing/bank stubs.
This is a source-function witness, not an emulator or FireRed execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
BLOB = "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb"
PATH = "src/gba/savedata.c"
URL = f"https://raw.githubusercontent.com/mgba-emu/mgba/{PIN}/{PATH}"

PREFIX = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
enum { FLASH_COMMAND_NONE = 0, FLASH_COMMAND_ID = 0x90 };
enum { GBA_SAVEDATA_AUTODETECT = 0, GBA_SAVEDATA_FLASH512 = 1, GBA_SAVEDATA_FLASH1M = 2 };
enum { FLASH_PANASONIC_MN63F805MNP = 0x1B32, FLASH_SANYO_LE26FV10N1TS = 0x1362 };
struct GBA { int timing; };
struct GBASavedata {
    struct GBA* p;
    int command, type;
    uint8_t* currentBank;
    unsigned settling;
    int dust;
};
static bool scheduled;
static bool mTimingIsScheduled(int* timing, int* event) {
    (void)timing; (void)event;
    return scheduled;
}
"""
SUFFIX = r"""
static int cases;
static void check(const char* name, int type, int command, unsigned address,
                  unsigned settling, bool isScheduled, uint8_t stored, uint8_t expected) {
    uint8_t bank[65536] = {0};
    struct GBA gba = {0};
    struct GBASavedata save = {0};
    bank[address] = stored;
    save.p = &gba;
    save.type = type;
    save.command = command;
    save.currentBank = bank;
    save.settling = settling;
    scheduled = isScheduled;
    uint8_t actual = GBASavedataReadFlash(&save, address);
    if (actual != expected) {
        fprintf(stderr, "FAIL %s: expected 0x%02X, got 0x%02X\n", name, expected, actual);
        assert(0 && "pinned Flash ID read mismatch");
    }
    ++cases;
}
int main(void) {
    check("flash1m-manufacturer", 2, 0x90, 0, 0, false, 0, 0x62);
    check("flash1m-device", 2, 0x90, 1, 0, false, 0, 0x13);
    check("flash512-manufacturer", 1, 0x90, 0, 0, false, 0, 0x32);
    check("flash512-device", 1, 0x90, 1, 0, false, 0, 0x1B);
    check("id-address2-falls-through", 2, 0x90, 2, 0, false, 0xA5, 0xA5);
    check("autodetect-id-falls-through", 0, 0x90, 0, 0, false, 0x5A, 0x5A);
    check("ordinary-bank-read", 2, 0, 0, 0, false, 0x5A, 0x5A);
    check("settling-q7-set", 2, 0, 0x1000, 1, true, 0x00, 0x80);
    check("settling-q7-clear", 2, 0, 0x1000, 1, true, 0x80, 0x00);
    check("settling-other-sector", 2, 0, 0x2000, 1, true, 0x55, 0x55);
    check("id-preempts-settling", 2, 0x90, 0, 0, true, 0x80, 0x62);
    printf("PASS %d compiled Flash ID reader cases\n", cases);
    return 0;
}
"""

def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def extract(source):
    start = source.index("uint8_t GBASavedataReadFlash(")
    opening = source.index("{", start)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise ValueError("Unclosed pinned function")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = args.source.read_bytes() if args.source else urllib.request.urlopen(URL, timeout=45).read()
    if blob_sha(raw) != BLOB:
        raise RuntimeError("Pinned savedata.c Git blob mismatch")
    function = extract(raw.decode("utf-8"))
    if "FLASH_SANYO_LE26FV10N1TS" not in function or "mTimingIsScheduled" not in function:
        raise RuntimeError("Pinned reader dependencies changed")
    with tempfile.TemporaryDirectory(prefix="xgba-flash-id-") as td:
        root = Path(td)
        c = root / "flash_id_probe.c"
        exe = root / "flash_id_probe"
        c.write_text(PREFIX + "\n" + function + "\n" + SUFFIX)
        subprocess.run(["cc", "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        str(c), "-o", str(exe)], check=True)
        result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    assert result.stdout.strip() == "PASS 11 compiled Flash ID reader cases", result.stdout
    evidence = {
        "scope": "exact pinned mGBA Flash ID reader compiled with timing and bank stubs; not runtime",
        "upstream": f"mgba-emu/mgba@{PIN}",
        "path": PATH,
        "git_blob_sha1": BLOB,
        "compiled_function_sha256": hashlib.sha256(function.encode()).hexdigest(),
        "cases_passed": 11,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()
