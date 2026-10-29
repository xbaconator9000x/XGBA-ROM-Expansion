/* Phase 1 experiment: unchanged FireRed agbcc ARM special-sector functions
 * in unchanged pinned mGBA. Test-only direct entry; not stock gameplay or hardware.
 * Unlike the earlier host bus experiment, ALL Flash commands must originate
 * from the original ARM routines after original CheckForFlashMemory executes.
 */
#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/savedata.h>
#include <mgba/internal/arm/arm.h>
#include <mgba/internal/arm/isa-inlines.h>
#include <mgba-util/vfs.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

enum { DATA_SIZE = 4092, MAX_STEPS = 12000000, INPUT = 0x02010000,
       OUTPUT = 0x02012000, BANK1_30 = 0x1E000, BANK1_31 = 0x1F000 };
static void need(bool yes, const char *why) {
    if (!yes) { fprintf(stderr, "FAIL %s\n", why); exit(3); }
}
static uint8_t *load_rom(const char *name, size_t *length) {
    FILE *f = fopen(name, "rb"); need(f != NULL, "rom_open");
    need(fseek(f, 0, SEEK_END) == 0, "rom_seek");
    long n = ftell(f); need(n > 0 && n < 0x2000000, "rom_size");
    need(fseek(f, 0, SEEK_SET) == 0, "rom_rewind");
    uint8_t *data = malloc((size_t)n);
    need(data && fread(data, 1, (size_t)n, f) == (size_t)n, "rom_read");
    fclose(f); *length = (size_t)n; return data;
}
static uint32_t arg_address(const char *text) {
    char *end = NULL; unsigned long value = strtoul(text, &end, 0);
    need(end && *end == 0 && value >= 0x08000000UL && value < 0x0A000000UL,
         "linked_function_address");
    return (uint32_t)value & ~1U;
}
static uint32_t ram_address(const char *text) {
    char *end = NULL; unsigned long value = strtoul(text, &end, 0);
    need(end && *end == 0 && value >= 0x02000000UL && value < 0x04000000UL,
         "linked_ram_address");
    return (uint32_t)value;
}
static uint32_t original_entry(struct mCore *core, uint32_t address,
                               uint32_t a0, uint32_t a1, const char *label) {
    struct ARMCore *cpu = ((struct GBA *)core->board)->cpu;
    need(cpu != NULL, "original_cpu_present");
    cpu->gprs[0] = a0; cpu->gprs[1] = a1;
    cpu->gprs[ARM_SP] = 0x03007F00U;
    cpu->gprs[ARM_LR] = 0x03000001U;
    cpu->executionMode = MODE_THUMB;
    cpu->cpsr.t = 1;
    cpu->gprs[ARM_PC] = address;
    ThumbWritePC(cpu);
    unsigned i;
    for (i = 0; i < MAX_STEPS; ++i) {
        core->step(core);
        uint32_t pc = (uint32_t)cpu->gprs[ARM_PC];
        if (pc >= 0x03000000U && pc <= 0x03000008U) break;
    }
    need(i < MAX_STEPS, "bounded_original_arm_return");
    printf("ARM %s steps=%u result=0x%08x\n", label, i + 1, (uint32_t)cpu->gprs[0]);
    return (uint32_t)cpu->gprs[0];
}
static uint8_t pattern(unsigned sector, unsigned i) {
    return (uint8_t)((sector * 13U + i * 7U) & 0xFFU);
}
static void fill(struct mCore *core, unsigned sector) {
    for (unsigned i = 0; i < DATA_SIZE; ++i)
        core->busWrite8(core, INPUT + i, pattern(sector, i));
}
static bool sector_matches(const uint8_t *data, unsigned base, unsigned sector) {
    if (data[base] != 0x9d || data[base + 1] != 0xb3 ||
        data[base + 2] != 0 || data[base + 3] != 0) return false;
    for (unsigned i = 0; i < DATA_SIZE; ++i)
        if (data[base + 4 + i] != pattern(sector, i)) return false;
    return true;
}
static void check_readback(struct mCore *core, unsigned sector) {
    for (unsigned i = 0; i < DATA_SIZE; ++i)
        need(core->busRead8(core, OUTPUT + i) == pattern(sector, i),
             "original_arm_readback_payload");
}
int main(int argc, char **argv) {
    need(argc == 7, "usage_rom_checkflash_write_read_flashpresent_gflash");
    size_t rom_size = 0;
    uint8_t *rom = load_rom(argv[1], &rom_size);
    uint32_t checkflash = arg_address(argv[2]);
    uint32_t write = arg_address(argv[3]);
    uint32_t read = arg_address(argv[4]);
    uint32_t present = ram_address(argv[5]);
    uint32_t gflash = ram_address(argv[6]);
    struct mCore *core = GBACoreCreate();
    need(core && core->init(core), "native_mgba_init");
    mCoreInitConfig(core, NULL);
    struct VFile *vf = VFileFromConstMemory(rom, rom_size);
    need(vf && core->loadROM(core, vf), "pristine_rom_load");
    core->reset(core);
    struct GBA *gba = core->board;
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_FLASH1M);
    struct GBASavedata *save = &gba->memory.savedata;
    need(save->type == GBA_SAVEDATA_FLASH1M && save->data,
         "emulated_flash1m_configured");
    need(save->data[BANK1_30] == 0xff && save->data[BANK1_31] == 0xff,
         "special_sectors_initially_erased");
    original_entry(core, checkflash, 0, 0, "CheckForFlashMemory");
    need(core->busRead32(core, present) == 1, "original_flash_present");
    need(core->busRead32(core, gflash) != 0, "original_gflash_initialized");
    puts("PASS original_flash_detection_and_callbacks");
    for (unsigned sector = 30; sector <= 31; ++sector) {
        fill(core, sector);
        uint32_t result = original_entry(core, write, sector, INPUT,
                                          sector == 30 ? "WriteSector30" : "WriteSector31");
        need(result == 1, "original_arm_write_success");
        need(sector_matches(save->data, sector == 30 ? BANK1_30 : BANK1_31, sector),
             "original_arm_physical_sector_payload");
        if (sector == 30)
            need(save->data[BANK1_31] == 0xff, "sector31_not_yet_written");
        puts(sector == 30 ? "PASS original_arm_sector30_write" :
                            "PASS original_arm_sector31_write");
    }
    for (unsigned sector = 30; sector <= 31; ++sector) {
        for (unsigned i = 0; i < DATA_SIZE; ++i)
            core->busWrite8(core, OUTPUT + i, 0xCC);
        uint32_t result = original_entry(core, read, sector, OUTPUT,
                                          sector == 30 ? "ReadSector30" : "ReadSector31");
        need(result == 1, "original_arm_read_success");
        check_readback(core, sector);
        puts(sector == 30 ? "PASS original_arm_sector30_readback" :
                            "PASS original_arm_sector31_readback");
    }
    uint8_t before = save->data[0x1d000];
    uint32_t rejected = original_entry(core, write, 29, INPUT, "RejectSector29");
    need(rejected == 0xff && save->data[0x1d000] == before,
         "original_arm_invalid_sector_rejected");
    puts("PASS invalid_sector_no_flash_mutation");
    puts("SUMMARY native_mgba=true original_agbcc_arm=true original_flash_init=true host_flash_commands=false synthetic_direct_entry=true stock_gameplay=false physical_hardware=false persistent_sav=false phase1_gate=FAIL_INCOMPLETE approvals=0");
    mCoreConfigDeinit(&core->config);
    core->deinit(core); free(rom);
    return 0;
}
