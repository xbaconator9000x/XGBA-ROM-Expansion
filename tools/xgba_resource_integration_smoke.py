#!/usr/bin/env python3
"""R6: build and *execute* a pinned FireRed ROM using real mGBA and an >32MiB sidecar.

This is a bounded executable integration harness, not a Python emulation or
a claim that every game / unmodified mGBA supports XGBA. A temporary FireRed
checkout gets a 64-byte experimental source-level opt-in probe; the resulting
real ARM/Thumb .gba runs in a real compiled mGBA core. An external host test
adapter supplies validated resource bytes over the existing emulated GBA bus.
No copyrighted game image is stored or distributed by XGBA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MGBA = ROOT / "upstream" / "mgba"
FIRERED = ROOT / "upstream" / "pokefirered"
FIRERED_PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MGBA_PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
ROM_WINDOW = 32 * 1024 * 1024
RESOURCE_ID = "graphic.smoke"
RESOURCE_OFFSET = ROM_WINDOW + 8192
MAGIC = 0x58474241
PAYLOAD = bytes(((i * 7 + 47) % 256 for i in range(64)))


def invoke(args, **kw):
    return subprocess.run([str(x) for x in args], check=True, text=True, **kw)


def verify_pins():
    for directory, pin in ((FIRERED, FIRERED_PIN), (MGBA, MGBA_PIN)):
        if not (directory / ".git").is_dir():
            raise RuntimeError("BLOCKED: pinned source checkout absent: " + str(directory))
        actual = subprocess.check_output(
            ["git", "-C", str(directory), "rev-parse", "HEAD"], text=True).strip()
        if actual != pin:
            raise RuntimeError("BLOCKED: source revision mismatch: " + str(directory))
    for executable in ("arm-none-eabi-gcc", "arm-none-eabi-nm", "make", "cmake", "cc"):
        if not shutil.which(executable):
            raise RuntimeError("BLOCKED: native/ARM build tool missing: " + executable)


GAME_PROBE = r"""
/* XGBA R6: original game source compiles this *opt-in test fixture*.
 * The real mGBA host test stages validated bytes into allocated EWRAM.
 * No synthetic CPU interpreter or guessed GBA address is used.
 */
#include "sprite.h"
#include "__XGBA_R4_ABSOLUTE_PATH__"
#define XGBA_SMOKE_MAGIC 0x58474241u
struct XgbaSmokeControl {
    volatile u32 magic;
    volatile u32 state; /* 1 waiting, 2 host ready, 3 loaded, 4 host release */
    volatile u32 verified;
    volatile u32 used;
    volatile u32 tile;
};
EWRAM_DATA volatile struct XgbaSmokeControl gXgbaSmokeControl = {0};
EWRAM_DATA u8 gXgbaSmokeTiles[64] ALIGNED(4) = {0};
static const u8 sXgbaOriginalTiles[64] ALIGNED(4) = {
    0x11, 0x22, 0x33, 0x44
};
static void XgbaSmokeProbe(void)
{
    struct SpriteSheet original = {sXgbaOriginalTiles, 64, 0xA121};
    struct XgbaStagedSprite stage;
    bool8 used = FALSE;
    gXgbaSmokeControl.magic = XGBA_SMOKE_MAGIC;
    gXgbaSmokeControl.state = 1;
    /* Emulator core progresses cycles while this game code waits.
     * Host detects state, validates the sidecar, writes to game EWRAM.
     * Test-specific handshake; this is NOT a generic game patch. */
    while (gXgbaSmokeControl.state == 1)
        ;
    stage.abiVersion = 1;
    stage.resourceId = 0xA121;
    stage.ewramData = gXgbaSmokeTiles;
    stage.byteLength = sizeof(gXgbaSmokeTiles);
    stage.validatedByProvider = gXgbaSmokeControl.verified ? TRUE : FALSE;
    ResetSpriteData();
    gXgbaSmokeControl.tile = XgbaLoadStagedSpriteSheet(
        &original, 0xA121, &stage, &used);
    gXgbaSmokeControl.used = used;
    gXgbaSmokeControl.state = 3;
    while (gXgbaSmokeControl.state == 3)
        ;
    /* Resume the original main loop after the host verifies the VRAM copy. */
}
"""


def inject_game_probe():
    main = FIRERED / "src" / "main.c"
    original = main.read_text(encoding="utf-8")
    if "gXgbaSmokeControl" in original:
        raise RuntimeError("Refusing to overwrite an existing XGBA game probe")
    declaration = "void AgbMain()\n{"
    hook = "    gLinkTransferringData = FALSE;\n\n    for (;;)"
    if original.count(declaration) != 1 or original.count(hook) != 1:
        raise RuntimeError("Pinned FireRed main.c declaration/loop drifted")
    adapter = (ROOT / "tools" / "xgba_resource_firered_adapter.c").as_posix()
    snippet = GAME_PROBE.replace("__XGBA_R4_ABSOLUTE_PATH__", adapter)
    altered = original.replace(declaration, snippet + "\n" + declaration)
    altered = altered.replace(hook,
                              "    gLinkTransferringData = FALSE;\n"
                              "    XgbaSmokeProbe();\n\n    for (;;)")
    main.write_text(altered, encoding="utf-8")
    return main, original


def build_game():
    # Never mutate the persistent source pin; restore the temporary checkout.
    main, original = inject_game_probe()
    try:
        invoke(["make", "-C", FIRERED, "-j2", "MODERN=1", "GAME_VERSION=FIRERED"],
               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=2100)
        rom = FIRERED / "pokefirered_modern.gba"
        elf = FIRERED / "pokefirered_modern.elf"
        if not rom.is_file() or not elf.is_file():
            raise RuntimeError("BLOCKED: real modern FireRed ELF/GBA missing")
        symbols = subprocess.check_output(
            ["arm-none-eabi-nm", "-g", str(elf)], text=True)
        addresses = {}
        for symbol in ("gXgbaSmokeControl", "gXgbaSmokeTiles"):
            hits = re.findall(r"^([0-9a-fA-F]{8})\s+[A-Za-z]\s+" +
                              re.escape(symbol) + r"$", symbols, re.M)
            if len(hits) != 1:
                raise RuntimeError("BLOCKED: real ELF symbol absent/ambiguous: " + symbol)
            addresses[symbol] = int(hits[0], 16)
            if not 0x02000000 <= addresses[symbol] < 0x02040000:
                raise RuntimeError("BLOCKED: game test symbol not in EWRAM: " + symbol)
        if addresses["gXgbaSmokeTiles"] + len(PAYLOAD) > 0x02040000:
            raise RuntimeError("BLOCKED: stage outside 256KiB EWRAM")
        return rom, elf, addresses
    finally:
        main.write_text(original, encoding="utf-8")


NATIVE_HARNESS = r"""
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/memory.h>
#include <mgba-util/vfs.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include "__XGBA_R5_ABSOLUTE_PATH__"

#define MAGIC 0x58474241u
#define EXPECTED_RESOURCE_BYTES 64u
struct HostFile {
    const char *path;
    uint64_t offset;
    uint8_t digest[32];
    int truncate;
    int unknown;
};
static int lookup(void *context, const char *id, uint64_t *length, uint8_t hash[32])
{
    struct HostFile *h = context;
    if (h->unknown || strcmp(id, "graphic.smoke") != 0)
        return 1;
    *length = EXPECTED_RESOURCE_BYTES;
    memcpy(hash, h->digest, 32);
    return 0;
}
static int read_file(void *context, const char *id, uint8_t *destination,
                     size_t capacity, size_t *bytes_read)
{
    struct HostFile *h = context;
    if (strcmp(id, "graphic.smoke") != 0 || capacity < EXPECTED_RESOURCE_BYTES)
        return 1;
    FILE *file = fopen(h->path, "rb");
    if (!file)
        return 1;
    if (fseeko(file, (off_t)h->offset, SEEK_SET) != 0) {
        fclose(file);
        return 1;
    }
    *bytes_read = fread(destination, 1, h->truncate ? 63 : 64, file);
    int bad = ferror(file);
    fclose(file);
    return bad ? 1 : 0;
}
static void fatal(const char *why)
{
    fprintf(stderr, "BLOCKED_R6_RUNTIME: %s\n", why);
    exit(2);
}
static uint32_t read_word(struct mCore *core, uint32_t addr)
{
    return core->busRead32(core, addr);
}
static void write_word(struct mCore *core, uint32_t addr, uint32_t word)
{
    core->busWrite32(core, addr, word);
}
static uint8_t hexval(char c)
{
    if (c >= '0' && c <= '9') return (uint8_t)(c - '0');
    if (c >= 'a' && c <= 'f') return (uint8_t)(c - 'a' + 10);
    if (c >= 'A' && c <= 'F') return (uint8_t)(c - 'A' + 10);
    fatal("invalid hex digest");
    return 0;
}
static void parse_sha(const char *str, uint8_t digest[32])
{
    if (strlen(str) != 64) fatal("digest length");
    for (size_t i = 0; i < 32; ++i)
        digest[i] = (hexval(str[i*2]) << 4) | hexval(str[i*2+1]);
}
int main(int argc, char **argv)
{
    if (argc != 8) fatal("arguments: ROM, sidecar, offset, sha, ctrl, tiles, case");
    const char *rom_file = argv[1];
    const char *data_file = argv[2];
    uint64_t offset = strtoull(argv[3], NULL, 10);
    const char *case_name = argv[7];
    uint32_t control_addr = (uint32_t)strtoul(argv[5], NULL, 16);
    uint32_t sprite_addr = (uint32_t)strtoul(argv[6], NULL, 16);
    if (offset <= 32u * 1024u * 1024u)
        fatal("sidecar resource not above 32MiB");
    FILE *fp = fopen(rom_file, "rb");
    if (!fp) fatal("FireRed ROM not compiled");
    if (fseeko(fp, 0, SEEK_END)) fatal("ROM length seek");
    off_t rom_size = ftello(fp);
    if (rom_size <= 0 || rom_size > 32u * 1024u * 1024u)
        fatal("invalid original FireRed ROM size");
    rewind(fp);
    uint8_t *rom = malloc((size_t)rom_size);
    if (!rom || fread(rom, 1, (size_t)rom_size, fp) != (size_t)rom_size)
        fatal("ROM bytes");
    fclose(fp);
    uint8_t game_sha[32];
    xgba_sha256(rom, (size_t)rom_size, game_sha);
    struct HostFile fixture = {.path=data_file, .offset=offset};
    parse_sha(argv[4], fixture.digest);
    if (strcmp(case_name, "truncate") == 0) fixture.truncate = 1;
    if (strcmp(case_name, "missing") == 0) fixture.unknown = 1;
    if (strcmp(case_name, "corrupt") == 0) fixture.digest[0] ^= 0x80;
    struct XgbaMgbaProviderV1 api = {
        .abi_version=XGBA_MGBA_PROVIDER_ABI_VERSION,
        .struct_size=sizeof(api),
        .context=&fixture,
        .lookup=lookup,
        .read=read_file,
    };
    strcpy(api.source_id, "firered-smoke");
    memcpy(api.source_sha256, game_sha, sizeof(game_sha));
    uint8_t requested_sha[32];
    memcpy(requested_sha, game_sha, sizeof(requested_sha));
    if (strcmp(case_name, "wrong-rom") == 0)
        requested_sha[0] ^= 0x40;
    struct XgbaMgbaProvider provider = {0};
    int opt_in = strcmp(case_name, "disabled") != 0;
    enum XgbaMgbaProviderStatus init = xgba_mgba_provider_open(
        &provider, &api, opt_in, "firered-smoke", requested_sha);
    if (strcmp(case_name, "wrong-rom") == 0) {
        if (init != XGBA_MGBA_IDENTITY_MISMATCH)
            fatal("wrong ROM accepted");
    } else if (init != XGBA_MGBA_OK)
        fatal("valid provider open failed");

    struct mCore *core = GBACoreCreate();
    if (!core || !core->init(core)) fatal("mGBA native init");
    mCoreInitConfig(core, NULL);
    struct VFile *vf = VFileFromConstMemory(rom, (size_t)rom_size);
    if (!vf || !core->loadROM(core, vf))
        fatal("mGBA cannot load built FireRed image");
    core->reset(core);
    int ready = 0;
    for (int frame = 0; frame < 1800; ++frame) {
        core->runFrame(core);
        if (read_word(core, control_addr) == MAGIC &&
            read_word(core, control_addr + 4) == 1u) {
            ready = 1;
            break;
        }
    }
    if (!ready) fatal("actual FireRed game never reached native opt-in request");

    uint8_t bytes[EXPECTED_RESOURCE_BYTES] = {0};
    size_t n = 0;
    int obtained = init == XGBA_MGBA_OK &&
        xgba_mgba_provider_read(&provider, "graphic.smoke", bytes,
                                sizeof(bytes), &n) == XGBA_MGBA_OK && n == 64u;
    if (strcmp(case_name, "positive") == 0 && !obtained)
        fatal("positive resource validation failed");
    if (strcmp(case_name, "positive") != 0 && obtained)
        fatal("negative resource unexpectedly accepted");
    if (obtained) {
        for (unsigned i = 0; i < EXPECTED_RESOURCE_BYTES; ++i)
            core->busWrite8(core, sprite_addr + i, bytes[i]);
    }
    write_word(core, control_addr + 8, obtained ? 1 : 0);
    write_word(core, control_addr + 4, 2u);
    int delivered = 0;
    for (int frame = 0; frame < 300; ++frame) {
        core->runFrame(core);
        if (read_word(core, control_addr + 4) == 3u) {
            delivered = 1;
            break;
        }
    }
    if (!delivered) fatal("actual FireRed native SpriteSheet adapter never returned");
    unsigned used = read_word(core, control_addr + 12);
    unsigned tile = read_word(core, control_addr + 16);
    if (!!used != !!obtained) fatal("game did not select correct sprite backing");
    if (tile > 1022) fatal("invalid OBJ tile index");
    const uint32_t vram = 0x06010000u + tile * 32u;
    for (size_t i = 0; i < EXPECTED_RESOURCE_BYTES; ++i) {
        uint8_t value = (uint8_t)core->busRead8(core, vram + (uint32_t)i);
        uint8_t expected = obtained ? bytes[i] : (i < 4 ? (uint8_t)(0x11u + i*0x11u) : 0u);
        if (value != expected) fatal("actual game OBJ VRAM not equal to chosen asset");
    }
    write_word(core, control_addr + 4, 4);
    core->runFrame(core); /* Original game AgbMain loop resumes. */
    printf("PASS_R6_FIRE_RED_EXECUTED mode=%s copied=%d obj_tile=%u asset_above_32MiB=1\n",
           case_name, obtained, tile);
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    free(rom);
    return 0;
}
"""


def build_native_mgba(root):
    cmake = root / "CMakeLists.txt"
    source = root / "xgba_integration_native.c"
    adapter = (ROOT / "tools" / "xgba_resource_mgba_adapter.c").as_posix()
    source.write_text(NATIVE_HARNESS.replace("__XGBA_R5_ABSOLUTE_PATH__", adapter),
                      encoding="utf-8")
    cmake.write_text(
        "cmake_minimum_required(VERSION 3.16)\n"
        "project(XgbaRealFireRedExecution C)\n"
        "set(CMAKE_C_STANDARD 11)\n"
        "set(BUILD_QT OFF CACHE BOOL \"\" FORCE)\n"
        "set(BUILD_SDL OFF CACHE BOOL \"\" FORCE)\n"
        "set(BUILD_LIBRETRO OFF CACHE BOOL \"\" FORCE)\n"
        "set(BUILD_TEST OFF CACHE BOOL \"\" FORCE)\n"
        "set(BUILD_STATIC ON CACHE BOOL \"\" FORCE)\n"
        "set(BUILD_SHARED OFF CACHE BOOL \"\" FORCE)\n"
        "set(BUILD_HEADLESS OFF CACHE BOOL \"\" FORCE)\n"
        "set(ENABLE_SCRIPTING OFF CACHE BOOL \"\" FORCE)\n"
        "set(BUILD_PYTHON OFF CACHE BOOL \"\" FORCE)\n"
        "set(USE_PNG OFF CACHE BOOL \"\" FORCE)\n"
        "set(USE_ZLIB OFF CACHE BOOL \"\" FORCE)\n"
        "set(ENABLE_GDB_STUB OFF CACHE BOOL \"\" FORCE)\n"
        f'add_subdirectory("{MGBA.as_posix()}" pinned-mgba)\n'
        "add_executable(xgba_firered_execution xgba_integration_native.c)\n"
        "target_link_libraries(xgba_firered_execution PRIVATE mgba)\n"
        "get_target_property(_mgba_defs mgba COMPILE_DEFINITIONS)\n"
        "if(NOT _mgba_defs)\n"
        "  message(FATAL_ERROR \"mGBA native compile definitions unavailable\")\n"
        "endif()\n"
        "target_compile_definitions(xgba_firered_execution PRIVATE " +
        chr(36) + "{_mgba_defs})\n"
        "target_include_directories(xgba_firered_execution PRIVATE\n"
        f'  "{MGBA.as_posix()}/include" ' +
        '"' + chr(36) + '{CMAKE_BINARY_DIR}/pinned-mgba/include")\n',
        encoding="utf-8")
    build = root / "build"
    invoke(["cmake", "-S", root, "-B", build, "-DCMAKE_BUILD_TYPE=Release"],
           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    invoke(["cmake", "--build", build, "--target", "xgba_firered_execution",
            "--parallel", "2"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
           timeout=900)
    path = build / "xgba_firered_execution"
    if not path.is_file():
        raise RuntimeError("BLOCKED: compiled native mGBA execution harness absent")
    return path


def run_demonstration():
    verify_pins()
    rom, elf, symbols = build_game()
    identity = {"id":"firered-smoke","sha256":hashlib.sha256(rom.read_bytes()).hexdigest()}
    sys.path.insert(0, str(ROOT / "tools"))
    import xgba_resource_sidecar as sidecar
    with tempfile.TemporaryDirectory(prefix="xgba-r6-real-mgba-") as tmp:
        root = Path(tmp)
        data = root / "external.bin"
        with data.open("wb") as fp:
            fp.truncate(RESOURCE_OFFSET + len(PAYLOAD))
            fp.seek(RESOURCE_OFFSET)
            fp.write(PAYLOAD)
        manifest_path = root / "resource.json"
        manifest_path.write_text(json.dumps({
            "format":sidecar.FORMAT,"version":sidecar.VERSION,
            "source_identity":identity, "data_file":data.name,
            "resources":[{
                "id":RESOURCE_ID,"offset":RESOURCE_OFFSET,"length":len(PAYLOAD),
                "sha256":hashlib.sha256(PAYLOAD).hexdigest(),
            }],
        }), encoding="utf-8")
        package = sidecar.load_manifest(
            manifest_path, expected_source_identity=identity)
        item = package.get_resource(RESOURCE_ID)
        if item.offset <= ROM_WINDOW:
            raise RuntimeError("BLOCKED: sidecar asset not after 32MiB")
        executable = build_native_mgba(root)
        results = {}
        for mode in ("positive", "disabled", "wrong-rom",
                     "truncate", "corrupt", "missing"):
            result = invoke([
                executable, rom, package.data_path, item.offset, item.sha256,
                format(symbols["gXgbaSmokeControl"], "08x"),
                format(symbols["gXgbaSmokeTiles"], "08x"), mode,
            ], capture_output=True, timeout=300)
            if "PASS_R6_FIRE_RED_EXECUTED mode=" + mode not in result.stdout:
                raise RuntimeError("BLOCKED: native FireRed/mGBA proof missing: " + mode)
            results[mode] = result.stdout.strip()
        return {
            "status":"REAL_NATIVE_EXECUTED","upstream_mgba":MGBA_PIN,
            "upstream_firered":FIRERED_PIN,
            "real_elf_sha256":hashlib.sha256(elf.read_bytes()).hexdigest(),
            "real_rom_sha256":identity["sha256"],
            "asset_sha256":item.sha256,"asset_offset":item.offset,
            "cases":results,"scope":"temporary source-instrumented FireRed ROM + linked mGBA host harness; not a generic distribution-ready emulator",
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", help="Write proof metadata JSON to file")
    args = parser.parse_args()
    result = run_demonstration()
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
