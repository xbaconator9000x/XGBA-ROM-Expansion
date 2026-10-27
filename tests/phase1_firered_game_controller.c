/* Phase 1 only: input-driven real-ROM observation, never a host Flash write.
 * Save mutations alone do not certify TrySavingData entry or player-state roundtrip.
 */
#include <mgba/core/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/savedata.h>
#include <mgba/internal/arm/arm.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct InputEvent { unsigned frame, keys; };
static void die(const char *s) { fprintf(stderr, "ERROR: %s\n", s); exit(2); }
static uint64_t digest(const void *data, size_t size) {
    const unsigned char *p = data;
    uint64_t h = UINT64_C(14695981039346656037);
    for (size_t i = 0; i < size; ++i) { h ^= p[i]; h *= UINT64_C(1099511628211); }
    return h;
}
int main(int argc, char **argv) {
    if (argc != 8 && argc != 11) die("usage: controller ROM SAV EVENTS FRAMES STATUS_ADDR COUNTER_ADDR SB2_PTR_ADDR [START_MENU_SAVE DO_SAVE TRY_SAVING_DATA]");
    char *end;
    unsigned limit = (unsigned)strtoul(argv[4], &end, 10);
    if (*end || limit < 180 || limit > 5000) die("invalid frame budget");
    const int tracing = argc == 11;
    uint32_t targets[3] = {0, 0, 0};
    unsigned hits[3] = {0, 0, 0}, first_hit_frame[3] = {0, 0, 0};
    unsigned first_try_save_arg = 0xFFFFFFFFU;
    unsigned long long trace_steps = 0;
    if (tracing) {
        for (unsigned i = 0; i < 3; ++i) {
            char *tail;
            unsigned long value = strtoul(argv[8 + i], &tail, 0);
            if (*tail || value < 0x08000000UL || value >= 0x0A000000UL)
                die("invalid compiled ELF save-callsite address");
            targets[i] = (uint32_t)value & ~1U;
        }
    }
    struct InputEvent events[1024];
    unsigned count = 0, prev = 0;
    FILE *script = fopen(argv[3], "r");
    if (!script) die("cannot open input schedule");
    char line[100];
    while (fgets(line, sizeof(line), script)) {
        unsigned frame, keys;
        if (sscanf(line, "%u %x", &frame, &keys) != 2 || keys > 0x3FF ||
            frame >= limit || (count && frame <= prev) || count == 1024)
            die("malformed, unsorted or excessive input schedule");
        events[count++] = (struct InputEvent){frame, keys};
        prev = frame;
    }
    fclose(script);
    struct mCore *core = mCoreFind(argv[1]);
    if (!core || !core->init(core)) die("mGBA core init failed");
    mCoreInitConfig(core, "xgba-phase1-game-controller");
    uint32_t *video = calloc(256 * 256, sizeof(*video));
    if (!video) die("video allocation failed");
    core->setVideoBuffer(core, video, 256);
    if (!mCoreLoadFile(core, argv[1]) || !mCoreLoadSaveFile(core, argv[2], false))
        die("ROM/save open failed");
    if (!core->setKeys) die("mGBA input API unavailable");
    core->reset(core);
    struct GBA *gba = core->board;
    uint8_t *baseline = NULL;
    size_t baseline_size = 0;
    unsigned baseline_frame = 0, first_change = 0, first_dirty = 0;
    unsigned event_index = 0, keys = 0, frames_with_changed_data = 0;
    uint64_t screen_first = 0, screen_last = 0;
    for (unsigned frame = 0; frame < limit; ++frame) {
        if (event_index < count && events[event_index].frame == frame) {
            keys = events[event_index].keys;
            ++event_index;
        }
        core->setKeys(core, keys);
        if (tracing && frame >= 180) {
            /* Step real ARM/Thumb instructions to witness exact ELF entry PCs.
             * A frame-only PC sample would miss almost every short save callback.
             * Never synthesize a call or write Flash from the host. */
            while (core->frameCounter(core) <= frame) {
                if (++trace_steps > 400000000ULL)
                    die("instruction-trace budget exhausted; no negative claim allowed");
                struct ARMCore *cpu = gba->cpu;
                uint32_t executing = (uint32_t)cpu->gprs[ARM_PC]
                    - (cpu->executionMode == MODE_THUMB ? 4U : 8U);
                for (unsigned j = 0; j < 3; ++j) {
                    if (executing == targets[j]) {
                        ++hits[j];
                        if (!first_hit_frame[j]) first_hit_frame[j] = frame + 1;
                        if (j == 2 && first_try_save_arg == 0xFFFFFFFFU)
                            first_try_save_arg = (unsigned)cpu->gprs[0] & 0xFFU;
                    }
                }
                core->step(core);
            }
        } else {
            core->runFrame(core);
        }
        if (frame == 179) screen_first = digest(video, 256 * 160 * sizeof(*video));
        struct GBASavedata *save = &gba->memory.savedata;
        size_t size = GBASavedataSize(save);
        if (!baseline && save->data && size == 131072) {
            baseline = malloc(size);
            if (!baseline) die("save snapshot allocation failed");
            memcpy(baseline, save->data, size);
            baseline_size = size;
            baseline_frame = frame + 1;
        } else if (baseline && save->data && GBASavedataSize(save) == baseline_size &&
                   memcmp(baseline, save->data, baseline_size)) {
            ++frames_with_changed_data;
            if (!first_change) first_change = frame + 1;
        }
        if (save->dirty && !first_dirty) first_dirty = frame + 1;
    }
    screen_last = digest(video, 256 * 160 * sizeof(*video));
    unsigned changed_bytes = 0;
    if (baseline && gba->memory.savedata.data &&
        GBASavedataSize(&gba->memory.savedata) == baseline_size) {
        for (size_t i = 0; i < baseline_size; ++i)
            if (baseline[i] != gba->memory.savedata.data[i]) ++changed_bytes;
    }
    uint32_t sb2 = core->busRead32(core, (uint32_t)strtoul(argv[7], NULL, 0));
    unsigned marker = (sb2 >= 0x02000000U && sb2 < 0x0203F000U)
        ? core->busRead8(core, sb2 + 0xB80U) : 0xFFFFFFFFU;
    printf("{\"mode\":\"controller\",\"frames\":%u,\"input_events\":%u,"
           "\"save_type\":%u,\"baseline_frame\":%u,\"flash_changed_bytes\":%u,"
           "\"frames_with_changed_flash\":%u,\"first_flash_change_frame\":%u,"
           "\"first_dirty_frame\":%u,\"save_status\":%u,\"save_counter\":%u,"
           "\"saveblock2_marker\":%u,\"screen_hash_frame180\":\"%016llx\","
           "\"screen_hash_final\":\"%016llx\",\"host_flash_writes\":0,"
           "\"trace_mode\":%s,\"trace_start_frame\":%u,\"trace_steps\":%llu,"
           "\"start_menu_save_hits\":%u,\"save_dialog_do_save_hits\":%u,"
           "\"try_saving_data_entry_hits\":%u,\"first_start_menu_save_frame\":%u,"
           "\"first_save_dialog_frame\":%u,\"first_try_saving_data_frame\":%u,"
           "\"first_try_save_arg\":%u,\"game_save_callsite_verified\":false}\n",
           core->frameCounter(core), count, gba->memory.savedata.type,
           baseline_frame, changed_bytes, frames_with_changed_data,
           first_change, first_dirty,
           core->busRead16(core, (uint32_t)strtoul(argv[5], NULL, 0)),
           core->busRead32(core, (uint32_t)strtoul(argv[6], NULL, 0)),
           marker, (unsigned long long)screen_first, (unsigned long long)screen_last,
           tracing ? "true" : "false", tracing ? 181U : 0U, trace_steps,
           hits[0], hits[1], hits[2], first_hit_frame[0], first_hit_frame[1],
           first_hit_frame[2], first_try_save_arg);
    core->setKeys(core, 0);
    core->deinit(core);
    free(baseline);
    free(video);
    return 0;
}
