"""Native R4 FireRed sprite-source ABI regression, NOT an emulator/game execution.

Checks the actual, pinned FireRed LoadSpriteSheet C body and real public headers.
The test compiles that original body (extracted unchanged at runtime) and the
opt-in XGBA adapter into one native executable. Only low-level GBA VRAM,
allocator and CpuSet hardware services are supplied by the Linux harness.
No Python-only engine mock is credited as native integration or as R6 proof.
"""
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIRERED = ROOT / "upstream" / "pokefirered"
PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"


def original_load_sprite_sheet():
    src = (FIRERED / "src" / "sprite.c").read_text(encoding="utf-8")
    key = "u16 LoadSpriteSheet(const struct SpriteSheet *sheet)"
    assert src.count(key) == 1, "Native FireRed LoadSpriteSheet ABI missing/changed"
    pos = src.index(key)
    begin = src.index("{", pos)
    depth = 0
    end = None
    for i in range(begin, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    assert end is not None
    actual = src[pos:end]
    for token in ("AllocSpriteTiles(sheet->size / TILE_SIZE_4BPP)",
                  "AllocSpriteTileRange(sheet->tag,", "CpuCopy16(sheet->data,",
                  "(u8 *)OBJ_VRAM0", "return (u16)tileStart;"):
        assert token in actual, f"Native FireRed sprite loading changed: {token}"
    return actual


C_TEST_DRIVER = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include "global.h"
#include "sprite.h"

static int gAllocationFailure;
static int gCopies;
static u16 gAllocatedTag, gAllocatedStart, gAllocatedCount;

s16 AllocSpriteTiles(u16 count) {
    assert(count > 0);
    return gAllocationFailure ? -1 : 5;
}
static void AllocSpriteTileRange(u16 tag, u16 start, u16 count) {
    gAllocatedTag = tag;
    gAllocatedStart = start;
    gAllocatedCount = count;
}
void CpuSet(const void *src, void *dst, u32 control) {
    u32 count = (control & 0x1FFFFFu) * ((control & CPU_SET_32BIT) ? 4u : 2u);
    assert(!(control & CPU_SET_SRC_FIXED));
    memcpy(dst, src, count);
    ++gCopies;
}

/* Exact native LoadSpriteSheet extracted from the pinned FireRed source: */
__FIRERED_SPRITE_FUNCTION__

/* The R4 adapter itself is compiled as real C using FireRed's public ABI. */
#include "tools/xgba_resource_firered_adapter.c"

static void map_gba_memory(void) {
    void *p = mmap((void *)(uintptr_t)EWRAM_START, 0x40000,
                  PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE,
                  -1, 0);
    assert(p == (void *)(uintptr_t)EWRAM_START);
    p = mmap((void *)(uintptr_t)OBJ_VRAM0, 0x8000,
             PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE,
             -1, 0);
    assert(p == (void *)(uintptr_t)OBJ_VRAM0);
}
static void check_copy(const u8 *expected) {
    assert(gCopies == 1);
    assert(gAllocatedTag == 77);
    assert(gAllocatedStart == 5);
    assert(gAllocatedCount == 2);
    assert(memcmp((u8 *)(uintptr_t)OBJ_VRAM0 + 5 * TILE_SIZE_4BPP, expected, 64) == 0);
}
int main(void) {
    static const u8 original[64] __attribute__((aligned(2))) = {0x11, 0x22, 0x33};
    struct SpriteSheet vanilla = {original, 64, 77};
    u8 *stageBytes = (u8 *)(uintptr_t)EWRAM_START + 0x200;
    struct XgbaStagedSprite staged = {1u, 0xA121u, stageBytes, 64u, TRUE};
    bool8 usingExternal = FALSE;
    map_gba_memory();
    memset(stageBytes, 0x5a, 64);
    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xA121u, &staged, &usingExternal) == 5);
    assert(usingExternal == TRUE);
    check_copy(stageBytes);
    puts("PASS native SpriteSheet + staged EWRAM -> original FireRed OBJ_VRAM0 copy");

    usingExternal = TRUE;
    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xBADu, &staged, &usingExternal) == 5);
    assert(usingExternal == FALSE);
    check_copy(original);
    puts("PASS wrong resource ID falls back to original sprite");

    staged.abiVersion = 2;
    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xA121u, &staged, &usingExternal) == 5);
    check_copy(original);
    puts("PASS unknown ABI version falls back");
    staged.abiVersion = 1;

    staged.validatedByProvider = FALSE;
    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xA121u, &staged, &usingExternal) == 5);
    check_copy(original);
    puts("PASS unverified resource rejected");
    staged.validatedByProvider = TRUE;

    staged.ewramData = (void *)(uintptr_t)OBJ_VRAM0;
    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xA121u, &staged, &usingExternal) == 5);
    check_copy(original);
    puts("PASS non-EWRAM pointer rejected");
    staged.ewramData = stageBytes;

    staged.ewramData = (void *)(uintptr_t)(EWRAM_END - 32);
    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xA121u, &staged, &usingExternal) == 5);
    check_copy(original);
    puts("PASS EWRAM boundary overrun rejected");
    staged.ewramData = stageBytes;

    staged.byteLength = 32;
    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xA121u, &staged, &usingExternal) == 5);
    check_copy(original);
    puts("PASS partial asset never replaces the native sprite");
    staged.byteLength = 64;

    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xA121u, NULL, &usingExternal) == 5);
    check_copy(original);
    puts("PASS no extension preserves native original sprite");

    gCopies = 0;
    gAllocationFailure = 1;
    assert(XgbaLoadStagedSpriteSheet(&vanilla, 0xA121u, &staged, &usingExternal) == 0);
    assert(gCopies == 0);
    puts("PASS native sprite allocation failure does not copy tiles");

    gCopies = 0;
    assert(XgbaLoadStagedSpriteSheet(NULL, 0, NULL, &usingExternal) == 0);
    assert(gCopies == 0);
    puts("PASS invalid original source never dereferenced");
    return 0;
}
'''


class NativeFireRedR4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiler = shutil.which("cc")
        if cls.compiler is None:
            raise AssertionError("Native C compiler required; cannot silently skip R4")
        cls.pin = subprocess.check_output(
            ["git", "-C", str(FIRERED), "rev-parse", "HEAD"], text=True
        ).strip()
        if cls.pin != PIN:
            raise AssertionError("Incorrect pinned original FireRed source: " + cls.pin)

    def test_real_native_source_contract(self):
        actual = original_load_sprite_sheet()
        self.assertIn("u16 LoadSpriteSheet", actual)
        sprite_header = (FIRERED / "include" / "sprite.h").read_text(encoding="utf-8")
        self.assertRegex(sprite_header, r"struct SpriteSheet\s*\{\s*const void \*data")
        self.assertRegex(sprite_header, r"u16 LoadSpriteSheet\(const struct SpriteSheet \*sheet\)")
        self.assertIn("#define EWRAM_START 0x02000000", (
            FIRERED / "include" / "gba" / "defines.h").read_text(encoding="utf-8"))

    def test_actual_firered_sprite_callsite_and_r4_adapter_execute_in_native_c(self):
        actual = original_load_sprite_sheet()
        with tempfile.TemporaryDirectory() as tmp:
            d = pathlib.Path(tmp)
            main = d / "firered_r4_native.c"
            main.write_text(C_TEST_DRIVER.replace("__FIRERED_SPRITE_FUNCTION__", actual), encoding="utf-8")
            exe = d / "firered_r4_native"
            compile_result = subprocess.run([
                self.compiler, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-O0",
                "-DMODERN=1", "-I", str(FIRERED / "include"), "-I", str(ROOT),
                str(main), "-o", str(exe),
            ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout)
            result = subprocess.run([str(exe)], text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(result.stdout.count("PASS "), 10, result.stdout)


if __name__ == "__main__":
    unittest.main()
