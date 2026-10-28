/* Phase 1 only. Real pinned mGBA core + source-built FireRed ROM.
 * This is an emulator runtime probe, not a proof of correct in-game saving.
 */
#include <mgba/core/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/savedata.h>
#include <mgba/internal/arm/arm.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

static void fail(const char *message) { fprintf(stderr, "ERROR: %s\n", message); exit(2); }
static void flash_write(struct mCore *core, unsigned offset, uint8_t value) {
    core->busWrite8(core, 0x0E000000U + offset, value);
}
int main(int argc, char **argv) {
    if (argc != 6 && argc != 9 && argc != 10 && argc != 12) fail("usage: probe ROM SAV MODE STATUS_ADDR COUNTER_ADDR [LOAD_ADDR VALID_ADDR COPY_ADDR [SAVEBLOCK2_PTR_ADDR]]");
    if (!strcmp(argv[3], "trace") && argc != 10 && argc != 12) fail("trace mode needs three ELF function addresses");
    const char *mode = argv[3];
    struct mCore *core = mCoreFind(argv[1]);
    if (!core) fail("mCoreFind did not recognize ROM");
    fprintf(stderr, "stage: core identified\n");
    if (!core->init(core)) fail("mGBA core initialization failed");
    mCoreInitConfig(core, "xgba-phase1-real-rom");
    fprintf(stderr, "stage: core initialized\n");
    void *video = calloc(256U * 256U, 4);
    if (!video) fail("video buffer allocation failed");
    core->setVideoBuffer(core, video, 256);
    if (!mCoreLoadFile(core, argv[1])) fail("source-built ROM could not be loaded");
    fprintf(stderr, "stage: ROM loaded\n");
    if (!mCoreLoadSaveFile(core, argv[2], false)) fail("save file could not be opened");
    fprintf(stderr, "stage: save loaded\n");
    core->reset(core);
    fprintf(stderr, "stage: reset complete\n");
    struct GBA *gba = (struct GBA *)core->board;
    unsigned hits[3] = {0, 0, 0};
    unsigned long long steps = 0;
    uint32_t traceEndPc = 0, loadReturnPc = 0;
    unsigned loadSaveArg = 0xFFFFFFFFU, loadReturnValue = 0xFFFFFFFFU, loadReturnHits = 0;
    unsigned traceFrameLimit = 0;
    if (!strcmp(mode, "trace")) {
        uint32_t target[3];
        for (int j = 0; j < 3; ++j)
            target[j] = (uint32_t)strtoul(argv[6 + j], NULL, 0) & ~1U;
        /* Prefetched ARM PC is +8 in ARM mode and +4 in Thumb mode. */
        traceFrameLimit = 720; /* observe save-loader return, not just boot */
        while (core->frameCounter(core) < traceFrameLimit && steps < 100000000ULL) {
            struct ARMCore *cpu = gba->cpu;
            uint32_t pc = (uint32_t)cpu->gprs[ARM_PC];
            uint32_t executing = pc - (cpu->executionMode == MODE_THUMB ? 4U : 8U);
            traceEndPc = executing;
            if (loadReturnPc && executing == loadReturnPc) {
                ++loadReturnHits;
                loadReturnValue = (unsigned)cpu->gprs[0] & 0xFFU;
                loadReturnPc = 0;
            }
            for (int j = 0; j < 3; ++j) {
                if (executing == target[j]) {
                    ++hits[j];
                    if (j == 0) {
                        loadSaveArg = (unsigned)cpu->gprs[0] & 0xFFU;
                        loadReturnPc = (uint32_t)cpu->gprs[ARM_LR] & ~1U;
                    }
                }
            }
            core->step(core);
            ++steps;
            if (core->frameCounter(core) >= 180 && loadReturnHits > 0) break;
        }
        if (core->frameCounter(core) < 180)
            fail("trace budget exhausted before frame 180");
    } else {
        for (int i = 0; i < 180; ++i) {
            core->runFrame(core);
            if (i == 0) fprintf(stderr, "stage: first frame complete\n");
        }
    }
    fprintf(stderr, "stage: runtime observation window complete\n");
    unsigned type = gba->memory.savedata.type;
    uint32_t statusAddr = (uint32_t)strtoul(argv[4], NULL, 0);
    uint32_t counterAddr = (uint32_t)strtoul(argv[5], NULL, 0);
    unsigned status = core->busRead16(core, statusAddr);
    unsigned counter = core->busRead32(core, counterAddr);
    unsigned before = gba->memory.savedata.data ? gba->memory.savedata.data[0x40] : 0xFF;
    uint32_t saveBlock2 = argc >= 10 ? core->busRead32(core, (uint32_t)strtoul(argv[9], NULL, 0)) : 0;
    unsigned fillerMarker = (saveBlock2 >= 0x02000000U && saveBlock2 < 0x02040000U)
        ? core->busRead8(core, saveBlock2 + 0xB80U) : 0xFFFFFFFFU;
    uint32_t saveBlock1 = argc == 12 ? core->busRead32(core, (uint32_t)strtoul(argv[10], NULL, 0)) : 0;
    uint32_t storage = argc == 12 ? core->busRead32(core, (uint32_t)strtoul(argv[11], NULL, 0)) : 0;
    unsigned sectorMarkers[14] = {0};
    if (argc == 12) {
        if (saveBlock2 < 0x02000000U || saveBlock2 >= 0x02040000U ||
            saveBlock1 < 0x02000000U || saveBlock1 >= 0x02040000U ||
            storage < 0x02000000U || storage >= 0x02040000U)
            fail("source-linked saveblock/storage pointers outside EWRAM");
        sectorMarkers[0] = fillerMarker;
        for (unsigned i = 1; i < 14; ++i) {
            uint32_t base = i <= 4 ? saveBlock1 : storage;
            uint32_t chunk = i <= 4 ? i - 1 : i - 5;
            sectorMarkers[i] = core->busRead8(core, base + chunk * 0xF80U + 0x100U);
        }
    }
    if (!strcmp(mode, "program")) {
        if (type != GBA_SAVEDATA_FLASH1M) fail("expected Flash1M before program");
        /* Host-driven probe: finish any interrupted game-side Flash command,
         * select physical bank zero, then send real bus programming commands.
         * This does NOT represent an in-game SaveGame call. */
        GBASavedataReset(&gba->memory.savedata);
        flash_write(core, 0x5555, 0xAA);
        flash_write(core, 0x2AAA, 0x55);
        flash_write(core, 0x5555, 0xB0);
        flash_write(core, 0x0000, 0);
        if (gba->memory.savedata.currentBank != gba->memory.savedata.data)
            fail("could not select physical Flash bank zero");
        flash_write(core, 0x5555, 0xAA);
        flash_write(core, 0x2AAA, 0x55);
        flash_write(core, 0x5555, 0xA0);
        flash_write(core, 0x0040, 0x5A);
        if (gba->memory.savedata.data[0x40] != 0x5A)
            fail("host bus Flash programming did not change bank zero data");
        for (int i = 0; i < 3; ++i) core->runFrame(core);
    }
    if (!strcmp(mode, "verify") && before != 0x5A) fail("Flash1M byte not restored from physical save file");
    printf("{\"mode\":\"%s\",\"frames\":%u,\"save_type\":%u,\"save_status\":%u,\"save_counter\":%u,\"flash_byte_40\":%u,\"trace_steps\":%llu,\"load_game_save_entry_hits\":%u,\"get_save_valid_status_entry_hits\":%u,\"copy_save_slot_data_entry_hits\":%u,\"load_game_save_arg\":%u,\"load_game_save_return_hits\":%u,\"load_game_save_return_value\":%u,\"trace_end_pc\":%u,\"trace_frame_limit\":%u,\"saveblock2_ptr\":%u,\"saveblock2_filler_marker\":%u",
        mode, core->frameCounter(core), type, status, counter, before, steps, hits[0], hits[1], hits[2],
        loadSaveArg, loadReturnHits, loadReturnValue, traceEndPc, traceFrameLimit, saveBlock2, fillerMarker);
    if (argc == 12) {
        printf(",\"saveblock1_ptr\":%u,\"pokemon_storage_ptr\":%u,\"saveblock_sector_markers\":[",
               saveBlock1, storage);
        for (unsigned i = 0; i < 14; ++i)
            printf("%s%u", i ? "," : "", sectorMarkers[i]);
        printf("]");
    }
    printf("}\n");
    core->deinit(core);
    free(video);
    return 0;
}
