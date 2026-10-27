/* Phase 1 only. Real pinned mGBA core + source-built FireRed ROM.
 * This is an emulator runtime probe, not a proof of correct in-game saving.
 */
#include <mgba/core/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/savedata.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static void fail(const char *message) { fprintf(stderr, "ERROR: %s\n", message); exit(2); }
static void flash_write(struct mCore *core, unsigned offset, uint8_t value) {
    core->busWrite8(core, 0x0E000000U + offset, value);
}
int main(int argc, char **argv) {
    if (argc != 6) fail("usage: probe ROM SAV MODE STATUS_ADDR COUNTER_ADDR");
    const char *mode = argv[3];
    struct mCore *core = mCoreFind(argv[1]);
    if (!core) fail("mCoreFind did not recognize ROM");
    if (!core->init(core)) fail("mGBA core initialization failed");
    mCoreInitConfig(core, "xgba-phase1-real-rom");
    if (!mCoreLoadFile(core, argv[1])) fail("source-built ROM could not be loaded");
    if (!mCoreLoadSaveFile(core, argv[2], false)) fail("save file could not be opened");
    core->reset(core);
    for (int i = 0; i < 180; ++i) core->runFrame(core);
    struct GBA *gba = (struct GBA *)core->board;
    unsigned type = gba->memory.savedata.type;
    uint32_t statusAddr = (uint32_t)strtoul(argv[4], NULL, 0);
    uint32_t counterAddr = (uint32_t)strtoul(argv[5], NULL, 0);
    unsigned status = core->busRead16(core, statusAddr);
    unsigned counter = core->busRead32(core, counterAddr);
    unsigned before = core->busRead8(core, 0x0E000040U);
    if (!strcmp(mode, "program")) {
        if (type != GBA_SAVEDATA_FLASH1M) fail("expected Flash1M before program");
        flash_write(core, 0x5555, 0xAA);
        flash_write(core, 0x2AAA, 0x55);
        flash_write(core, 0x5555, 0xA0);
        flash_write(core, 0x0040, 0x5A);
        for (int i = 0; i < 3; ++i) core->runFrame(core);
        if (core->busRead8(core, 0x0E000040U) != 0x5A) fail("flash programming did not persist in mapped memory");
    }
    if (!strcmp(mode, "verify") && before != 0x5A) fail("Flash1M byte not restored from physical save file");
    printf("{\"mode\":\"%s\",\"frames\":%u,\"save_type\":%u,\"save_status\":%u,\"save_counter\":%u,\"flash_byte_40\":%u}\n",
        mode, core->frameCounter(core), type, status, counter, before);
    core->deinit(core);
    return 0;
}
