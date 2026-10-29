/* Phase 1: real unchanged pinned mGBA core and Flash command bus.
 * Synthetic in-memory cartridge, host-driven commands, NO FireRed ARM calls.
 * Sector IDs 30/31 originate in the pinned FireRed save interface.
 * This characterizes emulator transaction visibility, NOT power-loss atomicity.
 */
#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/savedata.h>
#include <mgba-util/vfs.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { FLASH_SECTOR_SIZE = 0x1000, SECTOR_30_OFFSET = 0x1E000,
       SECTOR_31_OFFSET = 0x1F000, SECTOR_29_OFFSET = 0x1D000,
       BANK0_SECTOR_30_OFFSET = 0xE000, SAMPLE_SIZE = 16 };
static int checks = 0;
static void require(bool ok, const char *name) {
    ++checks;
    printf("%s %s\n", ok ? "PASS" : "FAIL", name);
    if (!ok) exit(3);
}
static void flash(struct mCore *core, unsigned address, uint8_t value) {
    core->busWrite8(core, 0x0E000000U + address, value);
}
static void unlock(struct mCore *core) {
    flash(core, 0x5555, 0xAA);
    flash(core, 0x2AAA, 0x55);
}
static void bank(struct mCore *core, uint8_t number) {
    unlock(core);
    flash(core, 0x5555, 0xB0);
    flash(core, 0x0000, number);
}
static void erase(struct mCore *core, unsigned address) {
    unlock(core);
    flash(core, 0x5555, 0x80);
    unlock(core);
    flash(core, address, 0x30);
}
static void program(struct mCore *core, unsigned address, uint8_t value) {
    unlock(core);
    flash(core, 0x5555, 0xA0);
    flash(core, address, value);
}
static uint8_t value_for(unsigned generation, unsigned i) {
    static const uint8_t sentinel[4] = { 0x9D, 0xB3, 0x00, 0x00 };
    return i < 4 ? sentinel[i] : (uint8_t)(generation + 3U * i);
}
static void write_sector(struct mCore *core, unsigned address, unsigned generation) {
    erase(core, address);
    for (unsigned i = 0; i < SAMPLE_SIZE; ++i)
        program(core, address + i, value_for(generation, i));
}
static bool matches(const uint8_t *data, unsigned offset, unsigned generation) {
    for (unsigned i = 0; i < SAMPLE_SIZE; ++i)
        if (data[offset + i] != value_for(generation, i)) return false;
    return true;
}
int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    const size_t rom_size = 2U * 1024U * 1024U;
    uint8_t *rom = calloc(rom_size, 1);
    require(rom != NULL, "synthetic_rom_allocated");
    rom[0xAC] = 'X';
    struct mCore *core = GBACoreCreate();
    require(core != NULL && core->init(core), "native_mgba_core_initialized");
    mCoreInitConfig(core, NULL);
    struct VFile *vf = VFileFromConstMemory(rom, rom_size);
    require(vf != NULL && core->loadROM(core, vf), "synthetic_rom_loaded");
    core->reset(core);
    struct GBA *gba = core->board;
    GBASavedataForceType(&gba->memory.savedata, GBA_SAVEDATA_FLASH1M);
    struct GBASavedata *save = &gba->memory.savedata;
    require(save->type == GBA_SAVEDATA_FLASH1M && save->data != NULL,
            "native_flash1m_initialized");
    uint8_t *physical = save->data;
    require(physical[SECTOR_30_OFFSET] == 0xFF &&
            physical[SECTOR_31_OFFSET] == 0xFF,
            "fresh_special_sectors_erased");
    bank(core, 1);
    require(save->currentBank == physical + 0x10000,
            "physical_bank1_selected");
    write_sector(core, 0xE000, 0x20);
    write_sector(core, 0xF000, 0x20);
    require(matches(physical, SECTOR_30_OFFSET, 0x20) &&
            matches(physical, SECTOR_31_OFFSET, 0x20),
            "old_generation_both_sectors");
    require(physical[BANK0_SECTOR_30_OFFSET] == 0xFF &&
            physical[SECTOR_29_OFFSET] == 0xFF,
            "adjacent_and_bank0_isolation");
    /* Simulated interruption after first sector, not an actual power cut. */
    write_sector(core, 0xE000, 0x60);
    require(matches(physical, SECTOR_30_OFFSET, 0x60) &&
            matches(physical, SECTOR_31_OFFSET, 0x20),
            "interrupted_two_sector_mixed_generation_visible");
    write_sector(core, 0xF000, 0x60);
    require(matches(physical, SECTOR_30_OFFSET, 0x60) &&
            matches(physical, SECTOR_31_OFFSET, 0x60),
            "retry_restores_matching_generation");
    /* No unlocked direct writes; command state must be respected. */
    flash(core, 0xE007, 0x00);
    require(matches(physical, SECTOR_30_OFFSET, 0x60),
            "unlocked_bus_write_does_not_program");
    bank(core, 2);
    require(save->currentBank == physical + 0x10000,
            "invalid_bank_rejected");
    bank(core, 0);
    require(save->currentBank == physical,
            "bank0_reselected");
    require(physical[BANK0_SECTOR_30_OFFSET] == 0xFF &&
            matches(physical, SECTOR_30_OFFSET, 0x60),
            "bank_switch_does_not_alias_special_sector");
    printf("SUMMARY native_mgba=true original_firered_arm_executed=false "
           "synthetic_rom=true physical_hardware=false persistent_sav=false "
           "phase1_gate=FAIL_INCOMPLETE approvals=0 checks=%d\n", checks);
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    free(rom);
    return 0;
}
