/* Test-only fake Flash backend. Two unchanged pinned src/save.c function bodies
 * are injected below; this is HOST C, not mGBA/ARM/physical Flash.
 */
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
#define SECTOR_DATA_SIZE 3968
#define SECTOR_FOOTER_SIZE 128
#define SECTOR_SIZE (SECTOR_DATA_SIZE + SECTOR_FOOTER_SIZE)
#define SPECIAL_SECTOR_SENTINEL 0xB39D
#define SECTOR_ID_TRAINER_TOWER_1 30
#define SECTOR_ID_TRAINER_TOWER_2 31
#define SAVE_STATUS_OK 1
#define SAVE_STATUS_ERROR 0xFF
struct SaveSector {
    u8 data[SECTOR_DATA_SIZE];
    u8 unused[SECTOR_FOOTER_SIZE - 12];
    u16 id;
    u16 checksum;
    u32 signature;
    u32 counter;
};
#define SECTOR_COUNTER_OFFSET offsetof(struct SaveSector, counter)
_Static_assert(sizeof(struct SaveSector) == 4096, "pinned save sector ABI");
_Static_assert(SECTOR_COUNTER_OFFSET == 4092, "pinned counter field offset");
static struct SaveSector gSaveDataBuffer;
static u8 physical[2][SECTOR_SIZE];
static int write_failure[2];
static unsigned read_calls, write_calls;
static void check(int yes, const char *message) {
    if (!yes) { fprintf(stderr, "PHASE1_FATAL %s\n", message); exit(2); }
}
static void ReadFlash(u16 sector, u32 offset, void *dest, u32 size) {
    check(sector == 30 || sector == 31, "unexpected physical read sector");
    check(offset == 0 && size == 4096, "unexpected read extent");
    read_calls++;
    memcpy(dest, physical[sector - 30], size);
}
static u32 ProgramFlashSectorAndVerify(u16 sector, u8 *source) {
    check(sector == 30 || sector == 31, "unexpected physical write sector");
    write_calls++;
    if (write_failure[sector - 30]) return 1;
    memcpy(physical[sector - 30], source, SECTOR_SIZE);
    return 0;
}
PHASE1_PINNED_SPECIAL_SECTOR_FUNCTIONS
static void fill(u8 *dst, unsigned seed) {
    for (size_t i = 0; i < 4092; ++i) dst[i] = (u8)((i * 7 + seed) % 251);
}
int main(void) {
    u8 input[4092], output[4092], old_second[4096], newer[4092];
    u32 sentinel = 0;
    fill(input, 17);
    check(TryWriteSpecialSaveSector(30, input) == SAVE_STATUS_OK, "sector30 write");
    memcpy(&sentinel, physical[0], 4);
    check(sentinel == SPECIAL_SECTOR_SENTINEL, "physical sentinel");
    check(memcmp(physical[0] + 4, input, 4092) == 0, "all 4092 payload bytes copied");
    memset(output, 0, sizeof output);
    check(TryReadSpecialSaveSector(30, output) == SAVE_STATUS_OK, "sector30 read");
    check(memcmp(output, input, 4092) == 0, "read full 4092 payload");
    check(memcmp(physical[0] + 4092, input + 4088, 4) == 0,
          "last four bytes occupy nominal counter field");
    puts("SPECIAL_WRITE_READ sector=30 payload_bytes=4092 counter_tail_preserved=4");

    physical[0][0] ^= 1;
    memset(output, 0xCC, sizeof output);
    check(TryReadSpecialSaveSector(30, output) == SAVE_STATUS_ERROR, "bad sentinel rejected");
    for (size_t i = 0; i < sizeof output; ++i)
        check(output[i] == 0xCC, "bad sentinel mutated destination");
    puts("SPECIAL_SENTINEL_BAD rejected=1 destination_unchanged=4092");
    physical[0][0] ^= 1;
    physical[0][4095] ^= 0x80;
    check(TryReadSpecialSaveSector(30, output) == SAVE_STATUS_OK,
          "valid sentinel with changed last byte rejected");
    check(output[4091] == physical[0][4095], "last physical byte not read");
    puts("SPECIAL_LAST_BYTE_MODIFIED accepted=1");

    unsigned before_reads = read_calls, before_writes = write_calls;
    check(TryReadSpecialSaveSector(29, output) == SAVE_STATUS_ERROR, "invalid read ID");
    check(TryWriteSpecialSaveSector(29, input) == SAVE_STATUS_ERROR, "invalid write ID");
    check(read_calls == before_reads && write_calls == before_writes, "invalid ID did I/O");
    puts("SPECIAL_INVALID_SECTOR read_rejected=1 write_rejected=1");

    write_failure[1] = 1;
    check(TryWriteSpecialSaveSector(31, input) == SAVE_STATUS_ERROR, "failed write not propagated");
    write_failure[1] = 0;
    puts("SPECIAL_WRITE_FAIL sector=31 returned_error=1");

    check(TryWriteSpecialSaveSector(31, input) == SAVE_STATUS_OK, "baseline sector31");
    memcpy(old_second, physical[1], sizeof old_second);
    fill(newer, 83);
    check(TryWriteSpecialSaveSector(30, newer) == SAVE_STATUS_OK, "new sector30");
    write_failure[1] = 1;
    check(TryWriteSpecialSaveSector(31, newer) == SAVE_STATUS_ERROR, "new sector31 failed");
    check(memcmp(physical[0] + 4, newer, 4092) == 0, "first sector not updated");
    check(memcmp(physical[1], old_second, 4096) == 0, "old second not preserved");
    puts("SPECIAL_TORN_WRITE first_updated=1 second_old=1");
    puts("SPECIAL_DONE gate=FAIL_INCOMPLETE approvals=0");
    return 0;
}
