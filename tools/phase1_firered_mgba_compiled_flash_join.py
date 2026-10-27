#!/usr/bin/env python3
"""Compile three exact pinned source functions across FireRed/mGBA with a
stubbed save-bus boundary. No ROM execution or real emulator is claimed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request

SOURCES = {
    "fire_id": ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
                "src/agb_flash_1m.c", "e249fab9a350f3263e7df5f20ff301a6d008e3db",
                "u16 IdentifyFlash("),
    "fire_check": ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
                   "src/load_save.c", "8b723dd044c6024b3671bb890b25b56a53f99ec5",
                   "void CheckForFlashMemory("),
    "mgba_read": ("mgba-emu/mgba", "fd9dc5c2cbf234365068855851107e762fc6211b",
                  "src/gba/savedata.c", "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
                  "uint8_t GBASavedataReadFlash("),
}

BUS_SOURCE = ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
              "src/agb_flash.c", "08aeed1638e214a3cad8b28d103964ab24342fba")

PREFIX = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
enum { WAITCNT_SRAM_MASK = 3, WAITCNT_SRAM_8 = 3 };
static volatile u16 REG_WAITCNT;
typedef void (*FlashOp)(void);
struct FlashType {
    union { u16 joined; struct { u8 makerId, deviceId; } separate; } ids;
};
struct FlashSetupInfo {
    FlashOp programFlashByte, programFlashSector, eraseFlashChip, eraseFlashSector, WaitForFlashWrite;
    const u16* maxTime;
    struct FlashType type;
};
static void dummyOp(void) {}
static const u16 mxTimes[] = {1}, leTimes[] = {2}, fallbackTimes[] = {3};
static const struct FlashSetupInfo MX29L010 = {
    .programFlashByte=dummyOp, .programFlashSector=dummyOp,
    .eraseFlashChip=dummyOp, .eraseFlashSector=dummyOp, .WaitForFlashWrite=dummyOp,
    .maxTime=mxTimes, .type={.ids={.joined=0x09C2}}
};
static const struct FlashSetupInfo LE26FV10N1TS = {
    .programFlashByte=dummyOp, .programFlashSector=dummyOp,
    .eraseFlashChip=dummyOp, .eraseFlashSector=dummyOp, .WaitForFlashWrite=dummyOp,
    .maxTime=leTimes, .type={.ids={.joined=0x1362}}
};
static const struct FlashSetupInfo DefaultFlash = {
    .programFlashByte=dummyOp, .programFlashSector=dummyOp,
    .eraseFlashChip=dummyOp, .eraseFlashSector=dummyOp, .WaitForFlashWrite=dummyOp,
    .maxTime=fallbackTimes, .type={.ids={.joined=0}}
};
static const struct FlashSetupInfo* const sSetupInfos[] = {
    &MX29L010, &LE26FV10N1TS, &DefaultFlash
};
static FlashOp ProgramFlashByte, ProgramFlashSector, EraseFlashChip, EraseFlashSector, WaitForFlashWrite;
static const u16* gFlashMaxTime;
static const struct FlashType* gFlash;
static u32 gFlashMemoryPresent;
static int flashTimerCalls;
static void InitFlashTimer(void) { ++flashTimerCalls; }

enum { FLASH_COMMAND_NONE = 0, FLASH_COMMAND_ID = 0x90 };
enum { GBA_SAVEDATA_AUTODETECT = 0, GBA_SAVEDATA_FLASH512 = 1, GBA_SAVEDATA_FLASH1M = 2 };
enum { FLASH_PANASONIC_MN63F805MNP = 0x1B32, FLASH_SANYO_LE26FV10N1TS = 0x1362 };
struct GBA { int timing; };
struct GBASavedata {
    struct GBA* p;
    int command, type;
    u8* currentBank;
    unsigned settling;
    int dust;
};
static bool mTimingIsScheduled(int* timing, int* event) {
    (void)timing; (void)event;
    return false;
}
static struct GBA emulator;
static struct GBASavedata save;
static u8 bank[65536];
static bool directId;
static u16 forcedId;
static u8 GBASavedataReadFlash(struct GBASavedata* savedata, u16 address);
static u16 ReadFlashId(void) {
    if (directId) return forcedId;
    return (u16)GBASavedataReadFlash(&save, 0) |
           (u16)((u16)GBASavedataReadFlash(&save, 1) << 8);
}
"""
SUFFIX = r"""
static int cases;
static void check(const char* label, int type, int command, bool useDirect,
                  u16 directValue, bool expectedPresent, const struct FlashSetupInfo* expectedSetup) {
    memset(bank, 0xFF, sizeof(bank));
    save.p = &emulator;
    save.currentBank = bank;
    save.type = type;
    save.command = command;
    save.settling = 0;
    directId = useDirect;
    forcedId = directValue;
    flashTimerCalls = 0;
    gFlashMemoryPresent = 9;
    REG_WAITCNT = 0xFFFF;
    CheckForFlashMemory();
    bool present = gFlashMemoryPresent == TRUE;
    if (present != expectedPresent ||
        flashTimerCalls != (expectedPresent ? 1 : 0) ||
        gFlash != &expectedSetup->type ||
        gFlashMaxTime != expectedSetup->maxTime ||
        ProgramFlashByte != expectedSetup->programFlashByte ||
        ProgramFlashSector != expectedSetup->programFlashSector ||
        EraseFlashChip != expectedSetup->eraseFlashChip ||
        EraseFlashSector != expectedSetup->eraseFlashSector ||
        WaitForFlashWrite != expectedSetup->WaitForFlashWrite ||
        (REG_WAITCNT & WAITCNT_SRAM_MASK) != WAITCNT_SRAM_8) {
        fprintf(stderr, "FAIL %s: present=%d timer=%d selected=0x%04X waitcnt=0x%04X\n",
                label, present, flashTimerCalls, gFlash->ids.joined, REG_WAITCNT);
        assert(0 && "pinned compiled cross-boundary contract failed");
    }
    ++cases;
}
int main(void) {
    check("mGBA-flash1m-sanyo", 2, 0x90, false, 0, true, &LE26FV10N1TS);
    check("mGBA-flash512-panasonic", 1, 0x90, false, 0, false, &DefaultFlash);
    check("mGBA-autodetect-bank-FF", 0, 0x90, false, 0, false, &DefaultFlash);
    check("mGBA-flash1m-no-ID-command", 2, 0, false, 0, false, &DefaultFlash);
    check("manual-macronix-ID", 0, 0, true, 0x09C2, true, &MX29L010);
    check("manual-sanyo-ID", 0, 0, true, 0x1362, true, &LE26FV10N1TS);
    check("manual-unknown-ID", 0, 0, true, 0xFFFF, false, &DefaultFlash);
    check("manual-zero-ID", 0, 0, true, 0, false, &DefaultFlash);
    check("manual-near-miss-ID", 0, 0, true, 0x1363, false, &DefaultFlash);
    printf("PASS %d compiled cross-repo Flash identification cases\n", cases);
    return 0;
}
"""

def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()

def extract(raw, needle):
    source = raw.decode("utf-8")
    start = source.index(needle)
    opening = source.index("{", start)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise ValueError("Unclosed source function: " + needle)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-dir", type=Path, help="Optional root with repo subdirs pret-pokefirered, mgba-emu-mgba")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    functions = {}
    for key, (repo, pin, path, expected, needle) in SOURCES.items():
        if args.upstream_dir:
            raw = (args.upstream_dir / repo.replace("/", "-") / path).read_bytes()
        else:
            url = f"https://raw.githubusercontent.com/{repo}/{pin}/{path}"
            raw = urllib.request.urlopen(url, timeout=45).read()
        if blob_sha(raw) != expected:
            raise RuntimeError(f"Refusing non-pinned {repo}/{path}")
        functions[key] = extract(raw, needle)
    repo, pin, path, expected = BUS_SOURCE
    if args.upstream_dir:
        bus_raw = (args.upstream_dir / repo.replace("/", "-") / path).read_bytes()
    else:
        bus_raw = urllib.request.urlopen(f"https://raw.githubusercontent.com/{repo}/{pin}/{path}", timeout=45).read()
    if blob_sha(bus_raw) != expected:
        raise RuntimeError("Refusing non-pinned FireRed Flash bus reader")
    bus = extract(bus_raw, "u16 ReadFlashId(")
    anchors = ["SetReadFlash1(readFlash1Buffer);",
               "FLASH_WRITE(0x5555, 0xAA);",
               "FLASH_WRITE(0x2AAA, 0x55);",
               "FLASH_WRITE(0x5555, 0x90);",
               "flashId = readFlash1(FLASH_BASE + 1) << 8;",
               "flashId |= readFlash1(FLASH_BASE);",
               "FLASH_WRITE(0x5555, 0xF0);"]
    cursor = 0
    for anchor in anchors:
        index = bus.find(anchor, cursor)
        if index < 0:
            raise RuntimeError("FireRed Flash ID bus ordering drift: " + anchor)
        cursor = index + len(anchor)
    if "ReadFlashId()" not in functions["fire_id"]:
        raise RuntimeError("FireRed Flash ID bus boundary changed")
    if "GBASavedataReadFlash" not in functions["mgba_read"]:
        raise RuntimeError("mGBA Flash ID reader changed")
    with tempfile.TemporaryDirectory(prefix="xgba-cross-flash-") as td:
        root = Path(td)
        c = root / "cross_flash.c"
        exe = root / "cross_flash"
        c.write_text(PREFIX + "\n" + functions["mgba_read"] + "\n" +
                     functions["fire_id"] + "\n" + functions["fire_check"] + "\n" + SUFFIX)
        subprocess.run(["cc", "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=undefined", "-fno-sanitize-recover=all",
                        str(c), "-o", str(exe)], check=True)
        result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    assert result.stdout.strip() == "PASS 9 compiled cross-repo Flash identification cases", result.stdout
    evidence = {
        "scope": "3 exact pinned functions compiled with stubbed save bus, flash descriptors, timer and scheduler",
        "sources": {key: {"repository": val[0], "commit": val[1], "path": val[2], "blob": val[3],
                          "function_sha256": hashlib.sha256(functions[key].encode()).hexdigest()}
                    for key, val in SOURCES.items()},
        "source_only_bus_reader": {"repository": repo, "commit": pin, "path": path,
                                   "git_blob_sha1": expected,
                                   "function_sha256": hashlib.sha256(bus.encode()).hexdigest(),
                                   "compiled": False},
        "cases_passed": 9,
        "real_emulator_execution": False,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()
