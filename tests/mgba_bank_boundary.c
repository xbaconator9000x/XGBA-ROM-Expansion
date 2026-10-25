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

#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/memory.h>
#include <mgba/internal/arm/isa-inlines.h>
#include <mgba-util/vfs.h>

#define ADDRESS (GBA_BASE_ROM0 + 0x1200)
#define THUMB_ADDRESS (GBA_BASE_ROM0 + 0x1400)
#define ROM_BYTES_SMALL (16u * 1024u * 1024u)
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
static void run_one(bool matrix) {
    const size_t size = matrix ? ROM_BYTES_MATRIX : ROM_BYTES_SMALL;
    uint8_t *bytes = calloc(size, 1);
    if (!bytes) { fprintf(stderr, "Out of memory\n"); ++failures; return; }
    bytes[0xAC] = matrix ? 'M' : 'X';
    put32(bytes, 0x1200, OPCODE_A);
    put16(bytes, 0x1400, THUMB_A);
    if (matrix) {
        put32(bytes, BANK_A, OPCODE_A);
        put32(bytes, BANK_B, OPCODE_B);
        put16(bytes, BANK_A+0x200, THUMB_A);
        put16(bytes, BANK_B+0x200, THUMB_B);
    }
    struct mCore *core = GBACoreCreate();
    if (!core || !core->init(core)) {
        fprintf(stderr, "Cannot initialize pinned GBA core\n");
        ++failures;
        free(bytes);
        return;
    }
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
    core->reset(core);
    struct GBA *gba = core->board;
    printf("CARTRIDGE %s backing_bytes=%zu visible_rom_bytes=%zu\n",
           matrix ? "matrix" : "vanilla", size, gba->memory.romSize);
    if (!matrix) {
        check("vanilla_non_M_does_not_select_matrix",
              gba->memory.romSize == ROM_BYTES_SMALL && gba->memory.matrix.cmd == 0);
        check_arm(core, ADDRESS, OPCODE_A, "vanilla_ARM_fetch_data_consistency");
        check_thumb(core, THUMB_ADDRESS, THUMB_A, "vanilla_Thumb_fetch_data_consistency");
    } else {
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
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    free(bytes);
}
int main(void) {
    run_one(false);
    run_one(true);
    printf("SUMMARY hard_failures=%d native_gap_observations=%d "
           "xgba_runtime_implemented=false phase1_mapping_complete=false\n",
           failures, observations);
    return failures ? 1 : 0;
}
