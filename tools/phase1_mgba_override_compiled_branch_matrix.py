#!/usr/bin/env python3
"""Compile the exact pinned mGBA default-override function against a small
instrumented dependency boundary. Not a full emulator or a ROM execution test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
BLOB = "566968162b29c90167199ef43f3d7a99248798e8"
PATH = "src/gba/overrides.c"
URL = f"https://raw.githubusercontent.com/mgba-emu/mgba/{PIN}/{PATH}"

PREFIX = r"""
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum { GBA_IDLE_LOOP_NONE = 0, GBA_UNL_CART_MULTICART = 3 };
enum { GBA_SAVEDATA_AUTODETECT = 0, GBA_SAVEDATA_SRAM = 1, GBA_SAVEDATA_FLASH1M = 2 };
enum { HW_RTC = 4 };
struct GBACartridge { uint8_t beforeId[0xAC]; char id[4]; };
_Static_assert(offsetof(struct GBACartridge, id) == 0xAC, "game-code header offset");
struct Configuration { bool forceSram; };
struct GBACartridgeOverride {
    int idleLoop;
    int savetype;
    int hardware;
    bool vbaBugCompat;
    char id[4];
};
struct GBA {
    struct { uint8_t* rom; struct { int type; } unl; } memory;
    uint32_t romCrc32;
    int savedata, hardware;
    bool vbaBugCompat;
};
static int configCalls, defaultCalls, applyCalls;
static bool GBAOverrideFindConfig(const struct Configuration* config, struct GBACartridgeOverride* override) {
    ++configCalls;
    if (config && config->forceSram) {
        override->savetype = GBA_SAVEDATA_SRAM;
        return true;
    }
    return false;
}
static bool GBAOverrideFind(const struct Configuration* config, struct GBACartridgeOverride* override) {
    (void) config;
    ++defaultCalls;
    if (!memcmp(override->id, "BPRE", 4)) {
        override->savetype = GBA_SAVEDATA_FLASH1M;
        return true;
    }
    return false;
}
static void GBAOverrideApply(struct GBA* gba, const struct GBACartridgeOverride* override) {
    ++applyCalls;
    gba->savedata = override->savetype;
    gba->hardware = override->hardware;
    gba->vbaBugCompat = override->vbaBugCompat;
}
"""

SUFFIX = r"""
static int cases;
static void check(const char* label, const char* id, const char* marker,
                  uint32_t crc, bool forceSram, bool multicart,
                  int expectedSave, int expectedHardware, bool expectedVba,
                  int expectedApply, int expectedConfig, int expectedDefault) {
    uint8_t rom[0x200] = {0};
    memcpy(rom + 0xAC, id, 4);
    if (marker) {
        memcpy(rom + 0x108, marker, strlen(marker));
    }
    struct GBA gba = {0};
    gba.memory.rom = rom;
    gba.memory.unl.type = multicart ? GBA_UNL_CART_MULTICART : 0;
    gba.romCrc32 = crc;
    gba.savedata = GBA_SAVEDATA_AUTODETECT;
    struct Configuration config = {.forceSram = forceSram};
    configCalls = defaultCalls = applyCalls = 0;
    GBAOverrideApplyDefaults(&gba, &config);
    if (gba.savedata != expectedSave || gba.hardware != expectedHardware ||
        gba.vbaBugCompat != expectedVba || applyCalls != expectedApply ||
        configCalls != expectedConfig || defaultCalls != expectedDefault) {
        fprintf(stderr, "FAIL %s: save=%d hw=%d vba=%d calls=%d/%d/%d\n",
                label, gba.savedata, gba.hardware, gba.vbaBugCompat,
                applyCalls, configCalls, defaultCalls);
        assert(0 && "compiled pinned default override branch mismatch");
    }
    ++cases;
}
int main(void) {
    const uint32_t unknown = 0x12345678;
    const uint32_t known = 0xDD88761C; /* pinned BPRE CRC */
    check("unknown-id-no-marker", "ZZZZ", NULL, unknown, false, false, 0, 0, false, 0, 0, 1);
    check("known-id-no-marker", "BPRE", NULL, unknown, false, false, 2, 0, false, 1, 0, 1);
    check("unknown-id-red-marker", "ZZZZ", "pokemon red version", unknown, false, false, 2, 4, true, 1, 1, 0);
    check("unknown-id-emerald-marker", "ZZZZ", "pokemon emerald version", unknown, false, false, 2, 4, true, 1, 1, 0);
    check("AXVE-code-marker", "AXVE", NULL, unknown, false, false, 2, 4, true, 1, 1, 0);
    check("unknown-id-known-crc", "ZZZZ", "pokemon red version", known, false, false, 0, 0, false, 0, 0, 1);
    check("known-id-known-crc", "BPRE", "pokemon red version", known, false, false, 2, 0, false, 1, 0, 1);
    check("known-id-unknown-crc", "BPRE", "pokemon red version", unknown, false, false, 2, 4, true, 1, 1, 0);
    check("marker-case-sensitive", "ZZZZ", "Pokemon red version", unknown, false, false, 0, 0, false, 0, 0, 1);
    check("config-override-sram", "ZZZZ", "pokemon red version", unknown, true, false, 1, 4, true, 1, 1, 0);
    check("multicart-preempts-heuristic", "ZZZZ", "pokemon red version", unknown, false, true, 1, 0, false, 1, 0, 0);
    struct GBA gba = {0};
    struct Configuration config = {0};
    configCalls = defaultCalls = applyCalls = 0;
    GBAOverrideApplyDefaults(&gba, &config);
    assert(configCalls == 0 && defaultCalls == 0 && applyCalls == 0);
    ++cases;
    printf("PASS %d compiled branch cases\n", cases);
    return 0;
}
"""

def git_blob_sha(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def extract_function(source):
    start = source.index("void GBAOverrideApplyDefaults(")
    opening = source.index("{", start)
    depth = 0
    for i in range(opening, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise ValueError("Unclosed upstream function")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Local exact pinned upstream source")
    parser.add_argument("--output", type=Path, help="Optional JSON evidence")
    args = parser.parse_args()
    raw = args.source.read_bytes() if args.source else urllib.request.urlopen(URL, timeout=45).read()
    if git_blob_sha(raw) != BLOB:
        raise RuntimeError("Pinned upstream Git blob changed: refuse to compile")
    source = raw.decode("utf-8")
    func = extract_function(source)
    if "GBAOverrideFindConfig(overrides, &override);" not in func:
        raise RuntimeError("Expected configuration boundary absent")
    if "GBAOverrideFind(overrides, &override)" not in func:
        raise RuntimeError("Expected default boundary absent")
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-override-") as td:
        root = Path(td)
        c = root / "override_probe.c"
        exe = root / "override_probe"
        c.write_text(PREFIX + "\n" + func + "\n" + SUFFIX)
        cmd = ["cc", "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror", "-fsanitize=undefined",
               "-fno-sanitize-recover=all", str(c), "-o", str(exe)]
        subprocess.run(cmd, check=True)
        result = subprocess.run([str(exe)], check=True, text=True, capture_output=True)
    assert result.stdout.strip() == "PASS 12 compiled branch cases", result.stdout
    evidence = {
        "scope": "actual pinned GBAOverrideApplyDefaults C function, dependency stubs, not mGBA runtime",
        "upstream": f"mgba-emu/mgba@{PIN}",
        "path": PATH,
        "git_blob_sha1": BLOB,
        "compiled_function_sha256": hashlib.sha256(func.encode()).hexdigest(),
        "compiler": "cc -std=c11 -O1 -Wall -Wextra -Werror -fsanitize=undefined",
        "cases_passed": 12,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps(evidence, sort_keys=True))

if __name__ == "__main__":
    main()
