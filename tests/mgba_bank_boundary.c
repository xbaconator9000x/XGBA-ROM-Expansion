/* XGBA Phase 1: source-pinned native mGBA boundary characterization.
 * NO XGBA runtime is implemented by this file.
 * The synthetic cartridge is generated in memory, not a commercial ROM.
 * Native safety gaps are reported as obligations, not misreported as passes.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#if defined(ENABLE_VFS_FD) && !defined(_WIN32)
#include <fcntl.h>
#include <unistd.h>
#endif

#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/memory.h>
#include <mgba/internal/gba/savedata.h>
#include <mgba/internal/gba/serialize.h>
#include <mgba/internal/gba/io.h>
#include <mgba/internal/arm/isa-inlines.h>
#include <mgba-util/vfs.h>

#define ADDRESS (GBA_BASE_ROM0 + 0x1200)
#define THUMB_ADDRESS (GBA_BASE_ROM0 + 0x1400)
#define ROM_BYTES_SMALL (32u * 1024u * 1024u)
#define ROM_BYTES_MATRIX (64u * 1024u * 1024u)
#define BANK_A (0x00020000u)
#define BANK_B (0x00040000u)
#define OPCODE_A (0xE1A00000u)  /* mov r0,r0 */
#define OPCODE_B (0xE1A01001u)  /* mov r1,r1 */
#define THUMB_A (0x46C0u)       /* nop / mov r8,r8 */
#define THUMB_B (0x46C9u)       /* mov r9,r9 */

static int failures;
static int observations;
static void check(const char *label, bool condition) {
    printf("%s %s\n", condition ? "PASS" : "FAIL", label);
    if (!condition) ++failures;
}
static void observation(const char *label, bool condition) {
    printf("OBSERVATION %s=%s\n", label, condition ? "true" : "false");
    ++observations;
}
static void put32(uint8_t *bytes, size_t offset, uint32_t data) {
    bytes[offset] = (uint8_t) data;
    bytes[offset+1] = (uint8_t) (data >> 8);
    bytes[offset+2] = (uint8_t) (data >> 16);
    bytes[offset+3] = (uint8_t) (data >> 24);
}
static void put16(uint8_t *bytes, size_t offset, uint16_t data) {
    bytes[offset] = (uint8_t) data;
    bytes[offset+1] = (uint8_t) (data >> 8);
}
static void map512(struct GBA *gba, uint32_t physical, uint32_t virt) {
    GBAMatrixWrite(gba, 4, physical);
    GBAMatrixWrite(gba, 8, virt);
    GBAMatrixWrite(gba, 12, 1); /* unit = 512 bytes, not bytes */
    GBAMatrixWrite(gba, 0, 1);  /* native Matrix mapping command */
}
static void check_arm(struct mCore *core, uint32_t addr, uint32_t expected, const char *label) {
    struct ARMCore *cpu = core->cpu;
    cpu->executionMode = MODE_ARM;
    cpu->cpsr.t = 0;
    cpu->gprs[ARM_PC] = addr;
    ARMWritePC(cpu);            /* explicitly synchronizes active instruction region */
    uint32_t data = GBALoad32(cpu, addr, NULL);
    printf("TRACE %s data=%08x fetch=%08x expected=%08x\n",
           label, data, cpu->prefetch[0], expected);
    check(label, data == expected && cpu->prefetch[0] == expected);
}
static void check_thumb(struct mCore *core, uint32_t addr, uint16_t expected, const char *label) {
    struct ARMCore *cpu = core->cpu;
    cpu->executionMode = MODE_THUMB;
    cpu->cpsr.t = 1;
    cpu->gprs[ARM_PC] = addr;
    ThumbWritePC(cpu);
    uint32_t data = GBALoad16(cpu, addr, NULL) & 0xFFFFu;
    printf("TRACE %s data=%04x fetch=%04x expected=%04x\n",
           label, data, cpu->prefetch[0] & 0xFFFFu, expected);
    check(label, data == expected && (cpu->prefetch[0] & 0xFFFFu) == expected);
}
#if defined(ENABLE_VFS_FD) && !defined(_WIN32)
static struct VFile *create_savedata_file(char path[64], size_t size, uint8_t fill) {
    memcpy(path, "/tmp/xgba-mgba-savedata-XXXXXX", sizeof("/tmp/xgba-mgba-savedata-XXXXXX"));
    int fd = mkstemp(path);
    if (fd < 0) return NULL;
    uint8_t bytes[4096];
    memset(bytes, fill, sizeof(bytes));
    size_t written = 0;
    while (written < size) {
        size_t chunk = size - written;
        if (chunk > sizeof(bytes)) chunk = sizeof(bytes);
        ssize_t result = write(fd, bytes, chunk);
        if (result <= 0) {
     close(fd);
     unlink(path);
     return NULL;
        }
        written += (size_t) result;
    }
    if (lseek(fd, 0, SEEK_SET) < 0) {
        close(fd);
        unlink(path);
        return NULL;
    }
    struct VFile *vf = VFileFromFD(fd);
    if (!vf) {
        close(fd);
        unlink(path);
    }
    return vf;
}

static int read_savedata_file_byte(const char *path, off_t offset) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return -1;
    uint8_t value;
    bool ok = lseek(fd, offset, SEEK_SET) == offset && read(fd, &value, 1) == 1;
    close(fd);
    return ok ? value : -1;
}

static void reset_savedata_file(struct GBA *gba, const char *path) {
    mTimingDeschedule(&gba->timing, &gba->memory.savedata.dust);
    GBASavedataReset(&gba->memory.savedata);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_AUTODETECT);
    GBALoadSave(gba, NULL);
    if (path) unlink(path);
}

static void test_native_savedata_file_backend(struct GBA *gba) {
    char path[64];
    struct VFile *vf = create_savedata_file(path, GBA_SIZE_FLASH512, 0xA5);
    if (!vf) {
        check("native_savedata_flash_fixture_created", false);
        return;
    }
    GBALoadSave(gba, vf);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_FLASH1M);
    check("native_savedata_flash_direct_growth_zero_fills_new_bank",
          gba->memory.savedata.data &&
          gba->memory.savedata.data[0] == 0xA5 &&
          gba->memory.savedata.data[GBA_SIZE_FLASH512] == 0 &&
          read_savedata_file_byte(path, GBA_SIZE_FLASH512) == 0);
    reset_savedata_file(gba, path);

    GBALoadSave(gba, NULL);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_FLASH512);
    gba->memory.savedata.command = FLASH_COMMAND_SWITCH_BANK;
    GBASavedataWriteFlash(&gba->memory.savedata, 0, 1);
    check("native_savedata_flash_anonymous_promotion_leaves_new_bank_zero",
          gba->memory.savedata.type == GBA_SAVEDATA_FLASH1M &&
          gba->memory.savedata.data[GBA_SIZE_FLASH512 - 1] == 0xFF &&
          gba->memory.savedata.data[GBA_SIZE_FLASH512] == 0);
    reset_savedata_file(gba, NULL);

    vf = create_savedata_file(path, GBA_SIZE_FLASH512, 0xA5);
    if (!vf) {
        check("native_savedata_flash_promotion_fixture_created", false);
        return;
    }
    GBALoadSave(gba, vf);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_FLASH512);
    gba->memory.savedata.command = FLASH_COMMAND_SWITCH_BANK;
    GBASavedataWriteFlash(&gba->memory.savedata, 0, 1);
    check("native_savedata_flash_bank_promotion_erases_new_bank",
          gba->memory.savedata.type == GBA_SAVEDATA_FLASH1M &&
          gba->memory.savedata.data[GBA_SIZE_FLASH512] == 0xFF &&
          read_savedata_file_byte(path, GBA_SIZE_FLASH512) == 0xFF);
    reset_savedata_file(gba, path);

    vf = create_savedata_file(path, GBA_SIZE_EEPROM512, 0xA5);
    if (!vf) {
        check("native_savedata_eeprom_fixture_created", false);
        return;
    }
    GBALoadSave(gba, vf);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_EEPROM);
    check("native_savedata_eeprom_direct_growth_zero_fills_upper_range",
          gba->memory.savedata.data &&
          gba->memory.savedata.data[0] == 0xA5 &&
          gba->memory.savedata.data[GBA_SIZE_EEPROM512] == 0 &&
          read_savedata_file_byte(path, GBA_SIZE_EEPROM512) == 0);
    reset_savedata_file(gba, path);

    vf = create_savedata_file(path, GBA_SIZE_EEPROM512, 0xA5);
    if (!vf) {
        check("native_savedata_eeprom_promotion_fixture_created", false);
        return;
    }
    GBALoadSave(gba, vf);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_EEPROM512);
    gba->memory.savedata.command = EEPROM_COMMAND_WRITE;
    gba->memory.savedata.writeAddress = GBA_SIZE_EEPROM512 * 8;
    GBASavedataWriteEEPROM(&gba->memory.savedata, 1, 2);
    check("native_savedata_eeprom_promotion_erases_upper_range",
          gba->memory.savedata.type == GBA_SAVEDATA_EEPROM &&
          gba->memory.savedata.data[GBA_SIZE_EEPROM512] == 0xFF &&
          read_savedata_file_byte(path, GBA_SIZE_EEPROM512) == 0xFF);
    reset_savedata_file(gba, path);

    GBALoadSave(gba, NULL);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_EEPROM512);
    gba->memory.savedata.command = EEPROM_COMMAND_WRITE;
    gba->memory.savedata.writeAddress = GBA_SIZE_EEPROM512 * 8;
    GBASavedataWriteEEPROM(&gba->memory.savedata, 1, 2);
    check("native_savedata_eeprom_anonymous_promotion_leaves_unwritten_bytes_zero",
          gba->memory.savedata.type == GBA_SAVEDATA_EEPROM &&
          gba->memory.savedata.data[0] == 0xFF &&
          gba->memory.savedata.data[GBA_SIZE_EEPROM512] == 0x80 &&
          gba->memory.savedata.data[GBA_SIZE_EEPROM512 + 1] == 0 &&
          gba->memory.savedata.data[GBA_SIZE_EEPROM - 1] == 0);
    reset_savedata_file(gba, NULL);

    vf = create_savedata_file(path, 0, 0);
    if (!vf) {
        check("native_savedata_eeprom_empty_fixture_created", false);
        return;
    }
    GBALoadSave(gba, vf);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_EEPROM);
    check("native_savedata_eeprom_8k_empty_erases_only_first_512_bytes",
          gba->memory.savedata.data &&
          gba->memory.savedata.data[0] == 0xFF &&
          gba->memory.savedata.data[GBA_SIZE_EEPROM512 - 1] == 0xFF &&
          gba->memory.savedata.data[GBA_SIZE_EEPROM512] == 0 &&
          read_savedata_file_byte(path, GBA_SIZE_EEPROM512) == 0);
    reset_savedata_file(gba, path);

    vf = create_savedata_file(path, 0, 0);
    if (!vf) {
        check("native_savedata_eeprom_512_control_fixture_created", false);
        return;
    }
    GBALoadSave(gba, vf);
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_EEPROM512);
    check("native_savedata_eeprom_512_empty_file_erases_entire_save",
          gba->memory.savedata.data &&
          gba->memory.savedata.data[0] == 0xFF &&
          gba->memory.savedata.data[GBA_SIZE_EEPROM512 - 1] == 0xFF);
    reset_savedata_file(gba, path);

    vf = create_savedata_file(path, 4096, 0xA5);
    if (!vf) {
        check("native_savedata_clone_write_error_fixture_created", false);
        return;
    }
    GBALoadSave(gba, vf);
    uint8_t readOnlyOutput[1] = {0};
    struct VFile *out = VFileFromConstMemory(readOnlyOutput, sizeof(readOnlyOutput));
    bool cloneReportedSuccess = out && GBASavedataClone(&gba->memory.savedata, out);
    check("native_savedata_clone_reports_success_after_readonly_output_error",
          cloneReportedSuccess);
    if (out) out->close(out);
    reset_savedata_file(gba, path);
}
#else
static void test_native_savedata_file_backend(struct GBA *gba) {
    (void) gba;
    puts("SKIP native_savedata_file_backend_requires_posix_vfs_fd");
}
#endif

/* The native 16-bit ROM2_EX cartridge address range has EEPROM and
 * e-Reader priority over normal ROM backing. This fixture tests the real
 * native decoder without altering memory.c.
 */
static void test_native_peripherals(struct mCore *core) {
    struct GBA *gba = core->board;
    struct ARMCore *cpu = core->cpu;
    enum GBASavedataType original_type = gba->memory.savedata.type;
    enum SavedataCommand original_command = gba->memory.savedata.command;
    const uint32_t devices = gba->memory.hw.devices;
    const uint16_t original_reader_register = gba->memory.ereader.registerUnk;
    const uint32_t plain_addr = GBA_BASE_ROM2_EX + 0x1200u;
    const uint32_t reader_addr = GBA_BASE_ROM2_EX + 0x00F80000u;
    gba->memory.hw.devices &= ~HW_EREADER;
    uint16_t ordinary = GBALoad16(cpu, plain_addr, NULL);
    check("native_ROM2_EX_without_EEPROM_reads_ROM",
          ordinary == GBALoad16(cpu, ADDRESS, NULL));

    gba->memory.savedata.type = GBA_SAVEDATA_EEPROM512;
    gba->memory.savedata.command = EEPROM_COMMAND_NULL;
    uint16_t serial = GBALoad16(cpu, plain_addr, NULL);
    check("native_ROM2_EX_16bit_EEPROM_overrides_ROM", serial == 1u);
    check("native_ROM2_EX_32bit_EEPROM_not_16bit_override",
          GBALoad32(cpu, plain_addr, NULL) == GBALoad32(cpu, ADDRESS, NULL));

    gba->memory.savedata.type = original_type;
    gba->memory.hw.devices |= HW_EREADER;
    gba->memory.ereader.registerUnk = 0x1234u;
    check("native_ROM2_EX_eReader_register_overrides_ROM",
          GBALoad16(cpu, reader_addr, NULL) == 0x1234u);

    gba->memory.savedata.type = GBA_SAVEDATA_EEPROM512;
    gba->memory.savedata.command = EEPROM_COMMAND_NULL;
    check("native_EEPROM_priority_over_eReader_on_16bit_ROM2_EX",
          GBALoad16(cpu, reader_addr, NULL) == 1u);
    /* Prove the native 16-bit DMA3 source path goes through EEPROM rather
     * than treating the ROM2_EX window as unconditionally banked ROM. */
    gba->memory.savedata.type = GBA_SAVEDATA_EEPROM512;
    gba->memory.savedata.command = EEPROM_COMMAND_NULL;
    gba->memory.hw.devices &= ~HW_EREADER;
    ((uint16_t*)gba->memory.wram)[0x100u >> 1] = 0xA5A5u;
    GBADMAWriteSAD(gba, 3, plain_addr);
    GBADMAWriteDAD(gba, 3, GBA_BASE_EWRAM + 0x100u);
    gba->memory.io[GBA_REG_DMA3CNT_LO >> 1] = 1u;
    GBADMAWriteCNT_HI(gba, 3, 0x8000u); /* enable, immediate, 16-bit, one unit */
    fprintf(stderr, "DMA DEBUG pre: now=%d event.when=%u scheduled=%d active=%d count=%d src=%08x dst=%08x cycles=%d nextEvent=%d\n",
       mTimingCurrentTime(&gba->timing), gba->memory.dmaEvent.when,
       mTimingIsScheduled(&gba->timing, &gba->memory.dmaEvent),
       gba->memory.activeDMA, gba->memory.dma[3].nextCount,
       gba->memory.dma[3].nextSource, gba->memory.dma[3].nextDest,
       gba->cpu->cycles, gba->cpu->nextEvent);
    /* mTimingSchedule may enqueue into reroot while the CPU is at an event
     * boundary. The first tick promotes reroot; subsequent ticks dispatch
     * the DMA service and completion callbacks. Drain a bounded number of
     * native scheduler turns, never manually call private DMA callbacks. */
    for (int turn = 0; turn < 8 &&
         GBADMARegisterIsEnable(gba->memory.dma[3].reg); ++turn) {
        mTimingTick(&gba->timing, 80);
        fprintf(stderr, "DMA DEBUG tick=%d now=%d scheduled=%d count=%d enabled=%d\n",
                turn + 1, mTimingCurrentTime(&gba->timing),
                mTimingIsScheduled(&gba->timing, &gba->memory.dmaEvent),
                gba->memory.dma[3].nextCount,
                GBADMARegisterIsEnable(gba->memory.dma[3].reg));
    }
    fprintf(stderr, "DMA DEBUG post: now=%d event.when=%u scheduled=%d active=%d count=%d dstword=%04x cycles=%d nextEvent=%d\n",
       mTimingCurrentTime(&gba->timing), gba->memory.dmaEvent.when,
       mTimingIsScheduled(&gba->timing, &gba->memory.dmaEvent),
       gba->memory.activeDMA, gba->memory.dma[3].nextCount,
       ((uint16_t*)gba->memory.wram)[0x100u >> 1],
       gba->cpu->cycles, gba->cpu->nextEvent);
    check("native_DMA3_16bit_ROM2_EX_reads_EEPROM",
          ((uint16_t*)gba->memory.wram)[0x100u >> 1] == 1u);
    check("native_DMA3_immediate_one_unit_completes",
          !GBADMARegisterIsEnable(gba->memory.dma[3].reg));

    gba->memory.savedata.type = original_type;
    gba->memory.savedata.command = original_command;
    gba->memory.ereader.registerUnk = original_reader_register;
    gba->memory.hw.devices = devices;
}

static void test_native_matrix_state(struct mCore *core, uint8_t *backing) {
    struct GBA *gba = core->board;
    struct GBASerializedState *state = calloc(1, sizeof(*state));
    if (!state) { check("matrix_state_allocation", false); return; }
    const uint32_t mapping_before = gba->memory.matrix.mappings[0x1200u >> 9];
    const uint32_t thumb_before = gba->memory.matrix.mappings[0x1400u >> 9];
    GBAMatrixSerialize(gba, state);
    GBAMatrixReset(gba);
    check("matrix_reset_does_not_preserve_alternate_bank",
          gba->memory.matrix.mappings[0x1200u >> 9] != mapping_before);
    GBAMatrixDeserialize(gba, state);
    check("matrix_savestate_16slot_metadata_roundtrip",
          gba->memory.matrix.mappings[0x1200u >> 9] == mapping_before &&
          gba->memory.matrix.mappings[0x1400u >> 9] == thumb_before);
    check_arm(core, ADDRESS, OPCODE_B, "matrix_savestate_reloads_ARM_physical_bank");
    check_thumb(core, THUMB_ADDRESS, THUMB_B, "matrix_savestate_reloads_Thumb_physical_bank");

    /* Distinct from Matrix-only metadata: the complete GBA serializer
     * must restore the selected external bank and CPU-visible bytes. */
    GBASerialize(gba, state);
    map512(gba, BANK_A, 0x1200u);
    check_arm(core, ADDRESS, OPCODE_A, "matrix_pre_full_state_mutation_bank_A");
    bool restored = GBADeserialize(gba, state);
    check("matrix_full_emulator_state_deserialize_success", restored);
    if (restored) {
        check_arm(core, ADDRESS, OPCODE_B, "matrix_full_state_restores_ARM_bank_B");
        check_thumb(core, THUMB_ADDRESS, THUMB_B, "matrix_full_state_restores_Thumb_bank_B");
    }

    /* Native GBADeserialize checks header identity, but ROM CRC mismatch
     * merely emits a warning. Confirm positive guards and capture the
     * missing exact-backing identity as an observation, NOT a safety pass.
     */
    const uint32_t valid_crc = state->romCrc32;
    state->romCrc32 ^= 1u;
    observation("native_savestate_CRC_mismatch_only_warns",
                GBADeserialize(gba, state));
    state->romCrc32 = valid_crc;

    state->id ^= 1u;
    check("native_savestate_rejects_changed_game_code",
          !GBADeserialize(gba, state));
    state->id ^= 1u;

    state->title[0] ^= 1u;
    check("native_savestate_rejects_changed_game_title",
          !GBADeserialize(gba, state));
    state->title[0] ^= 1u;

    const uint8_t original_backing = backing[BANK_B];
    backing[BANK_B] ^= 2u;
    bool accepted_altered_backing = GBADeserialize(gba, state);
    uint32_t altered_data = GBALoad32(gba->cpu, ADDRESS, NULL);
    observation("native_savestate_external_bank_payload_change_unverified",
                accepted_altered_backing && altered_data != OPCODE_B);
    backing[BANK_B] = original_backing;
    check("native_savestate_restores_original_backing_after_fixture_mutation",
          GBADeserialize(gba, state) &&
          GBALoad32(gba->cpu, ADDRESS, NULL) == OPCODE_B);

    free(state);
}

/* Native >32MiB loading is not an XGBA opt-in handshake.
 * mGBA's loader inspects byte 0xAC and takes different code paths:
 * verify that a non-M oversized native file retains the ordinary 32MiB
 * address aperture and never activates the Matrix controller.
 */
static void test_nonmatrix_oversize_loader(void) {
    const size_t size = (size_t) GBA_SIZE_ROM0 + 0x1000u;
    uint8_t *bytes = calloc(size, 1);
    if (!bytes) { check("oversize_nonM_fixture_allocation", false); return; }
    bytes[0xAC] = 'X';
    put32(bytes, 0x1200u, OPCODE_A);
    put32(bytes, GBA_SIZE_ROM0 - 0x10u, 0xA5B6C7D8u);
    /* Bytes above the visible aperture must not alias into the image. */
    put32(bytes, GBA_SIZE_ROM0 + 0x120u, OPCODE_B);
    struct mCore *core = GBACoreCreate();
    if (!core || !core->init(core)) {
        check("oversize_nonM_core_init", false);
        if (core) core->deinit(core);
        free(bytes);
        return;
    }
    mCoreInitConfig(core, NULL);
    struct VFile *vf = VFileFromConstMemory(bytes, size);
    if (!vf || !core->loadROM(core, vf)) {
        check("oversize_nonM_native_load", false);
        if (vf) vf->close(vf);
        mCoreConfigDeinit(&core->config);
        core->deinit(core);
        free(bytes);
        return;
    }
    core->reset(core);
    struct GBA *gba = core->board;
    check("native_oversize_nonM_keeps_32MiB_visible_aperture",
          gba->memory.romSize == GBA_SIZE_ROM0);
    check("native_oversize_nonM_keeps_full_VFile_backing_length",
          gba->romVf && gba->romVf->size(gba->romVf) == (off_t)size);
    check("native_oversize_nonM_does_not_activate_Matrix",
          gba->memory.matrix.size == 0);
    check_arm(core, ADDRESS, OPCODE_A, "native_oversize_nonM_ARM_visible_bytes");
    check("native_oversize_nonM_ROM_end_access",
          GBALoad32(core->cpu, GBA_BASE_ROM0 + GBA_SIZE_ROM0 - 0x10u, NULL)
          == 0xA5B6C7D8u);
    check("native_oversize_nonM_has_no_extra_CPU_address_window",
          GBALoad32(core->cpu, GBA_BASE_ROM1 + 0x120u, NULL)
          != OPCODE_B);
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    free(bytes);
}

static void run_one(bool matrix) {
    fprintf(stderr,"STEP begin %s\n", matrix ? "matrix" : "vanilla");
    const size_t size = matrix ? ROM_BYTES_MATRIX : ROM_BYTES_SMALL;
    uint8_t *bytes = calloc(size, 1);
    if (!bytes) { fprintf(stderr, "Out of memory\n"); ++failures; return; }
    bytes[0xAC] = matrix ? 'M' : 'X';
    put32(bytes, 0x1200, OPCODE_A);
    /* Native ROM2_EX begins at the second 16 MiB of a 32 MiB aperture. */
    if (!matrix) put32(bytes, 0x01001200u, OPCODE_A);
    put16(bytes, 0x1400, THUMB_A);
    if (matrix) {
        put32(bytes, BANK_A, OPCODE_A);
        put32(bytes, BANK_B, OPCODE_B);
        put16(bytes, BANK_A+0x200, THUMB_A);
        put16(bytes, BANK_B+0x200, THUMB_B);
    }
    fprintf(stderr,"STEP fixture allocated %s\n", matrix ? "matrix" : "vanilla");
    struct mCore *core = GBACoreCreate();
    if (!core || !core->init(core)) {
        fprintf(stderr, "Cannot initialize pinned GBA core\n");
        ++failures;
        free(bytes);
        return;
    }
    fprintf(stderr,"STEP core created/initialized\n");
    mCoreInitConfig(core, NULL);
    struct VFile *vf = VFileFromConstMemory(bytes, size);
    if (!vf || !core->loadROM(core, vf)) {
        fprintf(stderr, "Cannot load synthetic %s cartridge\n", matrix ? "Matrix" : "vanilla");
        ++failures;
        if (vf) vf->close(vf);
        mCoreConfigDeinit(&core->config);
        core->deinit(core);
        free(bytes);
        return;
    }
    fprintf(stderr,"STEP ROM loaded, resetting\n");
    core->reset(core);
    fprintf(stderr,"STEP core reset successful\n");
    struct GBA *gba = core->board;
    printf("CARTRIDGE %s backing_bytes=%zu visible_rom_bytes=%zu\n",
           matrix ? "matrix" : "vanilla", size, gba->memory.romSize);
    if (!matrix) {
        fprintf(stderr,"STEP vanilla pre-check\n");
        check("vanilla_non_M_does_not_select_matrix",
              gba->memory.romSize == ROM_BYTES_SMALL && gba->memory.matrix.cmd == 0);
        check_arm(core, ADDRESS, OPCODE_A, "vanilla_ARM_fetch_data_consistency");
        check_thumb(core, THUMB_ADDRESS, THUMB_A, "vanilla_Thumb_fetch_data_consistency");
        test_native_savedata_file_backend(gba);
        test_native_peripherals(core);
    } else {
        fprintf(stderr,"STEP matrix pre-check\n");
        check("matrix_M_signature_and_16MiB_aperture",
              gba->memory.romSize == 0x01000000u);
        map512(gba, BANK_A, 0x1200u);
        check_arm(core, ADDRESS, OPCODE_A, "matrix_bank_A_ARM_fetch_data");
        /* Replacing bytes in ROM does NOT itself rewrite the existing CPU prefetch. */
        struct ARMCore *cpu = core->cpu;
        const uint32_t old_prefetch = cpu->prefetch[0];
        map512(gba, BANK_B, 0x1200u);
        const uint32_t new_data = GBALoad32(cpu, ADDRESS, NULL);
        observation("native_remap_leaves_prefetch_stale_until_refetch",
                    cpu->prefetch[0] == old_prefetch && new_data == OPCODE_B);
        check_arm(core, ADDRESS, OPCODE_B, "matrix_bank_B_ARM_fetch_data_after_refetch");
        map512(gba, BANK_A+0x200u, 0x1400u);
        check_thumb(core, THUMB_ADDRESS, THUMB_A, "matrix_bank_A_Thumb_fetch_data");
        map512(gba, BANK_B+0x200u, 0x1400u);
        check_thumb(core, THUMB_ADDRESS, THUMB_B, "matrix_bank_B_Thumb_fetch_data");
        test_native_matrix_state(core, bytes);
        /* Invalid virtual windows and zero size are rejected by native Matrix. */
        uint32_t previous = GBALoad32(cpu, ADDRESS, NULL);
        uint32_t slot = gba->memory.matrix.mappings[0x1200u >> 9];
        map512(gba, BANK_A, 0x2000u); /* disallowed virtual address */
        check("native_matrix_rejects_outside_8KiB_window",
              GBALoad32(cpu, ADDRESS, NULL) == previous &&
              gba->memory.matrix.mappings[0x1200u >> 9] == slot);
        uint32_t size_before = gba->memory.matrix.size;
        GBAMatrixWrite(gba, 12, 0);
        check("native_matrix_rejects_zero_size",
              gba->memory.matrix.size == size_before);
        /* The physical-bank bound is NOT checked by upstream Matrix:
           mapping metadata changes even if only part of requested data is in VFile.
           This is a safety obligation for future XGBA, not a passing safety test. */
        GBAMatrixWrite(gba, 4, (uint32_t)(size - 0x100u));
        GBAMatrixWrite(gba, 8, 0x1600u);
        GBAMatrixWrite(gba, 12, 1);
        GBAMatrixWrite(gba, 0, 1);
        observation("native_matrix_accepts_physical_range_past_end",
                    gba->memory.matrix.mappings[0x1600u >> 9] ==
                    (uint32_t)(size - 0x100u));
    }
    fprintf(stderr,"STEP deinit\n");
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    free(bytes);
    fprintf(stderr,"STEP complete\n");
}
int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    run_one(false);
    run_one(true);
    test_nonmatrix_oversize_loader();
    printf("SUMMARY hard_failures=%d native_gap_observations=%d "
           "xgba_runtime_implemented=false phase1_mapping_complete=false\n",
           failures, observations);
    return failures ? 1 : 0;
}
