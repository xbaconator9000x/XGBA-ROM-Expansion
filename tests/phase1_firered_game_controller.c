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
#include <unistd.h>

struct InputEvent { unsigned frame, keys; };
static void die(const char *s) { fprintf(stderr, "ERROR: %s\n", s); exit(2); }
static uint32_t optional_pinned_address(const char *name, int code) {
    const char *raw = getenv(name);
    if (!raw) return 0;
    char *tail;
    unsigned long v = strtoul(raw, &tail, 0);
    if (*tail || (code ? (v < 0x08000000UL || v >= 0x0A000000UL)
                       : !((v >= 0x02000000UL && v < 0x02040000UL) ||
                           (v >= 0x03000000UL && v < 0x03008000UL))))
        die("invalid pinned field-control diagnostic address");
    return (uint32_t)v & (code ? ~1U : ~0U);
}
#include "phase1_firered_interrupt.h"
static uint64_t digest(const void *data, size_t size) {
    const unsigned char *p = data;
    uint64_t h = UINT64_C(14695981039346656037);
    for (size_t i = 0; i < size; ++i) { h ^= p[i]; h *= UINT64_C(1099511628211); }
    return h;
}
int main(int argc, char **argv) {
    if (argc != 8 && argc != 23) die("usage: controller ROM SAV EVENTS FRAMES STATUS_ADDR COUNTER_ADDR SB2_PTR_ADDR [START_MENU_SAVE DO_SAVE TRY_SAVING_DATA TITLE_TASK INIT_MAIN EXEC_MAIN RETURN_FIELD CONTINUE_GAME RETURN_FIELD_LOCAL OVERWORLD CB1_OVERWORLD SHOW_START_MENU FIELD_GET_PLAYER_INPUT GMAIN SB1_PTR_ADDR]");
    unsigned cut_after = phase1_cut_selector(argc);
    char *end;
    unsigned limit = (unsigned)strtoul(argv[4], &end, 10);
    if (*end || limit < 180 || limit > 5000) die("invalid frame budget");
    const int tracing = argc == 23;
    uint32_t targets[13] = {0};
    unsigned hits[13] = {0}, first_hit_frame[13] = {0};
    unsigned first_try_save_arg = 0xFFFFFFFFU;
    uint32_t pending_try_save_return_pc = 0;
    unsigned try_save_return_hits = 0, first_try_save_return_frame = 0;
    unsigned first_try_save_return_value = 0xFFFFFFFFU;
    unsigned long long trace_steps = 0;
    uint32_t gmain_addr = 0, sb1_ptr_addr = 0;
    uint32_t lock_addr = optional_pinned_address("XGBA_PHASE1_LOCK_ADDR", 0);
    uint32_t avatar_addr = optional_pinned_address("XGBA_PHASE1_AVATAR_ADDR", 0);
    uint32_t player_step_target = optional_pinned_address("XGBA_PHASE1_PLAYER_STEP_ADDR", 1);
    uint32_t object_events_addr = optional_pinned_address("XGBA_PHASE1_OBJECT_EVENTS_ADDR", 0);
    uint32_t camera_move_target = optional_pinned_address("XGBA_PHASE1_CAMERA_MOVE_ADDR", 1);
    uint32_t flash_present_addr = optional_pinned_address("XGBA_PHASE1_FLASH_PRESENT_ADDR", 0);
    const int inject_no_flash = getenv("XGBA_PHASE1_INJECT_NO_FLASH") != NULL;
    if (inject_no_flash && !flash_present_addr)
        die("no-Flash fault injection requires pinned gFlashMemoryPresent address");
    unsigned no_flash_fault_entries = 0, no_flash_original = 0;
    int no_flash_fault_active = 0;
    unsigned locked_overworld_frames = 0, player_step_hits = 0;
    unsigned player_step_direction_hits = 0, camera_move_hits = 0;
    unsigned player_object_changed_frames = 0, player_object_active_frames = 0;
    unsigned player_object_camera_tracked_frames = 0, player_object_is_player_frames = 0;
    int player_object_first_x = -32768, player_object_first_y = -32768;
    int player_object_last_x = -32768, player_object_last_y = -32768;
    unsigned player_object_last_action = 255, player_object_last_behavior = 255;
    unsigned avatar_first_flags = 255, avatar_last_flags = 255;
    unsigned avatar_last_running = 255, avatar_last_transition = 255;
    unsigned avatar_last_object_event_id = 255;
    unsigned callback2_return_local_frames = 0, return_local_state_hist[16] = {0};
    unsigned last_gmain_state = 0;
    uint32_t last_callback2 = 0;
    unsigned callback2_overworld_frames = 0, new_start_key_frames = 0;
    unsigned new_start_key_overworld_frames = 0, first_callback2_overworld_frame = 0;
    unsigned new_direction_key_overworld_frames = 0, held_direction_key_overworld_frames = 0;
    unsigned position_changed_frames = 0, first_position_change_frame = 0;
    int first_overworld_x = -32768, first_overworld_y = -32768;
    if (tracing) {
        for (unsigned i = 0; i < 13; ++i) {
            char *tail;
            unsigned long value = strtoul(argv[8 + i], &tail, 0);
            if (*tail || value < 0x08000000UL || value >= 0x0A000000UL)
                die("invalid compiled ELF save-callsite address");
            targets[i] = (uint32_t)value & ~1U;
        }
        char *tail;
        unsigned long main_value = strtoul(argv[21], &tail, 0);
        if (*tail || !((main_value >= 0x02000000UL && main_value < 0x02040000UL) ||
                        (main_value >= 0x03000000UL && main_value < 0x03008000UL)))
            die("invalid compiled gMain address");
        gmain_addr = (uint32_t)main_value;
        unsigned long sb1_value = strtoul(argv[22], &tail, 0);
        if (*tail || !((sb1_value >= 0x02000000UL && sb1_value < 0x02040000UL) ||
                        (sb1_value >= 0x03000000UL && sb1_value < 0x03008000UL)))
            die("invalid compiled gSaveBlock1Ptr address");
        sb1_ptr_addr = (uint32_t)sb1_value;
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
                /* Source-pinned TrySavingData is a normal Thumb subroutine.
                 * Capture the caller return PC from LR at actual entry.
                 * Observe execution of that return PC and R0 at the return,
                 * not a speculative frame-sampled return value. */
                if (pending_try_save_return_pc && executing == pending_try_save_return_pc) {
                    ++try_save_return_hits;
                    if (!first_try_save_return_frame) {
                        first_try_save_return_frame = frame + 1;
                        first_try_save_return_value = (unsigned)cpu->gprs[0] & 0xFFU;
                    }
                    pending_try_save_return_pc = 0;
                    if (no_flash_fault_active) {
                        core->busWrite32(core, flash_present_addr, no_flash_original);
                        no_flash_fault_active = 0;
                    }
                }
                if (camera_move_target && executing == camera_move_target)
                    ++camera_move_hits;
                if (player_step_target && executing == player_step_target) {
                    ++player_step_hits;
                    if (((unsigned)cpu->gprs[0] & 0xFFU) != 0)
                        ++player_step_direction_hits;
                }
                for (unsigned j = 0; j < 13; ++j) {
                    if (executing == targets[j]) {
                        ++hits[j];
                        if (!first_hit_frame[j]) first_hit_frame[j] = frame + 1;
                        if (j == 2 && inject_no_flash) {
                            /* Explicit host IWRAM fault before genuine TrySavingData.
                             * Never write Flash, never call game function from host. */
                            if (no_flash_fault_active) die("nested TrySavingData fault");
                            unsigned present = core->busRead32(core, flash_present_addr);
                            if (present != 1U) die("expected Flash present before fault");
                            no_flash_original = present;
                            core->busWrite32(core, flash_present_addr, 0U);
                            if (core->busRead32(core, flash_present_addr) != 0U)
                                die("gFlashMemoryPresent RAM fault did not apply");
                            no_flash_fault_active = 1;
                            ++no_flash_fault_entries;
                        }
                        if (j == 2 && first_try_save_arg == 0xFFFFFFFFU) {
                            first_try_save_arg = (unsigned)cpu->gprs[0] & 0xFFU;
                            uint32_t return_pc = (uint32_t)cpu->gprs[ARM_LR] & ~1U;
                            if (return_pc >= 0x08000000U && return_pc < 0x0A000000U)
                                pending_try_save_return_pc = return_pc;
                        }
                    }
                }
                core->step(core);
                if (cut_after && hits[2] && !try_save_return_hits &&
                    pending_try_save_return_pc && trace_steps % 2048ULL == 0)
                    phase1_maybe_interrupt(cut_after, hits[2], try_save_return_hits,
                        pending_try_save_return_pc, trace_steps, frame + 1, gba,
                        core->busRead32(core, (uint32_t)strtoul(argv[6], NULL, 0)));
            }
        } else {
            core->runFrame(core);
        }
        if (tracing) {
            /* Pinned include/main.h: callback2 +4, newKeys +0x2E.
             * Read after emulated frame; do not infer key handling from host pulses. */
            uint32_t callback2 = core->busRead32(core, gmain_addr + 4U) & ~1U;
            uint16_t new_keys = core->busRead16(core, gmain_addr + 0x2EU);
            last_callback2 = callback2;
            last_gmain_state = core->busRead8(core, gmain_addr + 0x438U);
            if (callback2 == targets[8]) {
                ++callback2_return_local_frames;
                if (last_gmain_state < 16) ++return_local_state_hist[last_gmain_state];
            }
            if (callback2 == targets[9]) {
                ++callback2_overworld_frames;
                if (!first_callback2_overworld_frame) first_callback2_overworld_frame = frame + 1;
                if (lock_addr && core->busRead8(core, lock_addr))
                    ++locked_overworld_frames;
                if (avatar_addr) {
                    unsigned flags = core->busRead8(core, avatar_addr);
                    if (avatar_first_flags == 255) avatar_first_flags = flags;
                    avatar_last_flags = flags;
                    avatar_last_running = core->busRead8(core, avatar_addr + 2U);
                    avatar_last_transition = core->busRead8(core, avatar_addr + 3U);
                    avatar_last_object_event_id = core->busRead8(core, avatar_addr + 5U);
                }
                /* Pinned global.fieldmap.h ObjectEvent size 0x24; coords +0x10,
                 * bitfields active at +0, trackedByCamera at +1, isPlayer at +2.
                 * Observe the real player object before blaming input or camera.
                 * These reads are diagnostic only; no emulated memory writes. */
                if (object_events_addr && avatar_addr) {
                    unsigned id = core->busRead8(core, avatar_addr + 5U);
                    if (id < 16U) {
                        uint32_t obj = object_events_addr + id * 0x24U;
                        int ox = (int16_t)core->busRead16(core, obj + 0x10U);
                        int oy = (int16_t)core->busRead16(core, obj + 0x12U);
                        if (player_object_first_x == -32768) {
                            player_object_first_x = ox;
                            player_object_first_y = oy;
                        } else if (ox != player_object_first_x || oy != player_object_first_y) {
                            ++player_object_changed_frames;
                        }
                        player_object_last_x = ox;
                        player_object_last_y = oy;
                        player_object_active_frames += !!(core->busRead8(core, obj) & 1U);
                        player_object_camera_tracked_frames += !!(core->busRead8(core, obj + 1U) & 0x80U);
                        player_object_is_player_frames += !!(core->busRead8(core, obj + 2U) & 1U);
                        player_object_last_action = core->busRead8(core, obj + 0x1CU);
                        player_object_last_behavior = core->busRead8(core, obj + 0x1EU);
                    }
                }
                uint16_t held_keys = core->busRead16(core, gmain_addr + 0x2CU);
                if (new_keys & (0x10U | 0x20U | 0x40U | 0x80U))
                    ++new_direction_key_overworld_frames;
                if (held_keys & (0x10U | 0x20U | 0x40U | 0x80U))
                    ++held_direction_key_overworld_frames;
                uint32_t current_sb1 = core->busRead32(core, sb1_ptr_addr);
                if (current_sb1 >= 0x02000000U && current_sb1 < 0x02040000U) {
                    int x = (int16_t)core->busRead16(core, current_sb1);
                    int y = (int16_t)core->busRead16(core, current_sb1 + 2U);
                    if (first_overworld_x == -32768) {
                        first_overworld_x = x;
                        first_overworld_y = y;
                    } else if (x != first_overworld_x || y != first_overworld_y) {
                        ++position_changed_frames;
                        if (!first_position_change_frame) first_position_change_frame = frame + 1;
                    }
                }
            }
            if (new_keys & 0x0008U) {
                ++new_start_key_frames;
                if (callback2 == targets[9]) ++new_start_key_overworld_frames;
            }
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
    if (no_flash_fault_active) die("faulted TrySavingData did not return");
    /* Fail closed: no Flash1M baseline means no valid zero-change observation.
     * The environment override is an explicit harness-only negative control;
     * it never writes emulator memory or the cartridge save device. */
    if (getenv("XGBA_PHASE1_FORCE_MISSING_BASELINE"))
        baseline_frame = 0;
    if (!baseline || baseline_frame == 0 || baseline_size != 131072 ||
        gba->memory.savedata.type != GBA_SAVEDATA_FLASH1M ||
        !gba->memory.savedata.data ||
        GBASavedataSize(&gba->memory.savedata) != baseline_size)
        die("Flash1M baseline/final mapping unavailable; observation invalid");
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
    uint32_t player_name_word = (sb2 >= 0x02000000U && sb2 < 0x0203F000U)
        ? core->busRead32(core, sb2) : 0xFFFFFFFFU;
    uint32_t saveblock1 = sb1_ptr_addr ? core->busRead32(core, sb1_ptr_addr) : 0;
    int saveblock1_valid = saveblock1 >= 0x02000000U && saveblock1 < 0x02040000U;
    printf("{\"mode\":\"controller\",\"frames\":%u,\"input_events\":%u,"
           "\"save_type\":%u,\"baseline_frame\":%u,\"flash_changed_bytes\":%u,"
           "\"frames_with_changed_flash\":%u,\"first_flash_change_frame\":%u,"
           "\"first_dirty_frame\":%u,\"save_status\":%u,\"save_counter\":%u,"
           "\"saveblock2_marker\":%u,\"saveblock2_player_name_u32\":%u,\"screen_hash_frame180\":\"%016llx\","
           "\"screen_hash_final\":\"%016llx\",\"host_flash_writes\":0,"
           "\"trace_mode\":%s,\"trace_start_frame\":%u,\"trace_steps\":%llu,"
           "\"start_menu_save_hits\":%u,\"save_dialog_do_save_hits\":%u,"
           "\"try_saving_data_entry_hits\":%u,\"first_start_menu_save_frame\":%u,"
           "\"first_save_dialog_frame\":%u,\"first_try_saving_data_frame\":%u,"
           "\"first_try_save_arg\":%u,\"try_saving_data_return_hits\":%u,"
           "\"first_try_saving_data_return_frame\":%u,\"first_try_saving_data_return_value\":%u,"
           "\"title_task_hits\":%u,"
           "\"init_main_menu_hits\":%u,\"execute_main_menu_hits\":%u,"
           "\"return_to_field_hits\":%u,\"continue_saved_game_hits\":%u,"
           "\"first_title_task_frame\":%u,\"first_init_main_menu_frame\":%u,"
           "\"first_execute_main_menu_frame\":%u,\"first_return_to_field_frame\":%u,"
           "\"first_continue_saved_game_frame\":%u,"
           "\"return_field_local_hits\":%u,\"overworld_hits\":%u,"
           "\"cb1_overworld_hits\":%u,\"show_start_menu_hits\":%u,"
           "\"field_get_player_input_hits\":%u,\"first_return_field_local_frame\":%u,"
           "\"first_overworld_frame\":%u,\"first_cb1_overworld_frame\":%u,"
           "\"first_show_start_menu_frame\":%u,\"first_field_get_player_input_frame\":%u,"
           "\"callback2_overworld_frames\":%u,\"first_callback2_overworld_frame\":%u,"
           "\"new_start_key_frames\":%u,\"new_start_key_overworld_frames\":%u,"
           "\"callback2_return_local_frames\":%u,\"return_local_state_hist\":[%u,%u,%u,%u,%u,%u,%u,%u],"
           "\"last_gmain_state\":%u,\"last_callback2\":%u,"
           "\"saveblock1_map_group\":%u,\"saveblock1_map_num\":%u,\"saveblock1_layout_id\":%u,"
           "\"saveblock1_pos_x\":%d,\"saveblock1_pos_y\":%d,"
           "\"first_overworld_pos_x\":%d,\"first_overworld_pos_y\":%d,"
           "\"position_changed_frames\":%u,\"first_position_change_frame\":%u,"
           "\"new_direction_key_overworld_frames\":%u,\"held_direction_key_overworld_frames\":%u,"
           "\"locked_overworld_frames\":%u,\"player_step_hits\":%u,"
           "\"player_step_nonzero_direction_hits\":%u,"
           "\"avatar_first_flags\":%u,\"avatar_last_flags\":%u,"
           "\"avatar_last_running\":%u,\"avatar_last_transition\":%u,"
           "\"avatar_last_object_event_id\":%u,"
           "\"camera_move_hits\":%u,\"player_object_changed_frames\":%u,"
           "\"player_object_active_frames\":%u,\"player_object_camera_tracked_frames\":%u,"
           "\"player_object_is_player_frames\":%u,"
           "\"player_object_first_x\":%d,\"player_object_first_y\":%d,"
           "\"player_object_last_x\":%d,\"player_object_last_y\":%d,"
           "\"player_object_last_action\":%u,\"player_object_last_behavior\":%u,"
           "\"host_ram_fault_injection\":%s,\"no_flash_fault_entries\":%u,"
           "\"no_flash_original\":%u,"
           "\"game_save_callsite_verified\":false}\n",
           core->frameCounter(core), count, gba->memory.savedata.type,
           baseline_frame, changed_bytes, frames_with_changed_data,
           first_change, first_dirty,
           core->busRead16(core, (uint32_t)strtoul(argv[5], NULL, 0)),
           core->busRead32(core, (uint32_t)strtoul(argv[6], NULL, 0)),
           marker, player_name_word, (unsigned long long)screen_first, (unsigned long long)screen_last,
           tracing ? "true" : "false", tracing ? 181U : 0U, trace_steps,
           hits[0], hits[1], hits[2], first_hit_frame[0], first_hit_frame[1],
           first_hit_frame[2], first_try_save_arg,
           try_save_return_hits, first_try_save_return_frame, first_try_save_return_value,
           hits[3], hits[4], hits[5], hits[6], hits[7],
           first_hit_frame[3], first_hit_frame[4], first_hit_frame[5],
           first_hit_frame[6], first_hit_frame[7],
           hits[8], hits[9], hits[10], hits[11], hits[12],
           first_hit_frame[8], first_hit_frame[9], first_hit_frame[10],
           first_hit_frame[11], first_hit_frame[12],
           callback2_overworld_frames, first_callback2_overworld_frame,
           new_start_key_frames, new_start_key_overworld_frames,
           callback2_return_local_frames,
           return_local_state_hist[0], return_local_state_hist[1], return_local_state_hist[2],
           return_local_state_hist[3], return_local_state_hist[4], return_local_state_hist[5],
           return_local_state_hist[6], return_local_state_hist[7],
           last_gmain_state, last_callback2,
           saveblock1_valid ? core->busRead8(core, saveblock1 + 4U) : 255U,
           saveblock1_valid ? core->busRead8(core, saveblock1 + 5U) : 255U,
           saveblock1_valid ? core->busRead16(core, saveblock1 + 0x32U) : 0xFFFFU,
           saveblock1_valid ? (int16_t)core->busRead16(core, saveblock1) : -32768,
           saveblock1_valid ? (int16_t)core->busRead16(core, saveblock1 + 2U) : -32768,
           first_overworld_x, first_overworld_y, position_changed_frames,
           first_position_change_frame, new_direction_key_overworld_frames,
           held_direction_key_overworld_frames, locked_overworld_frames,
           player_step_hits, player_step_direction_hits,
           avatar_first_flags, avatar_last_flags, avatar_last_running,
           avatar_last_transition, avatar_last_object_event_id,
           camera_move_hits, player_object_changed_frames,
           player_object_active_frames, player_object_camera_tracked_frames,
           player_object_is_player_frames,
           player_object_first_x, player_object_first_y,
           player_object_last_x, player_object_last_y,
           player_object_last_action, player_object_last_behavior,
           inject_no_flash ? "true" : "false", no_flash_fault_entries, no_flash_original);
    core->setKeys(core, 0);
    core->deinit(core);
    free(baseline);
    free(video);
    return 0;
}
