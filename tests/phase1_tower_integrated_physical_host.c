/* Test-only physical Flash shim. Original pinned FireRed C functions are
 * injected unchanged. HOST execution only; not agbcc ARM or mGBA. */
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef u32 bool32;
#define TRUE 1
#define FALSE 0
#define MAX_TRAINER_TOWER_FLOORS 8
#define CHALLENGE_TYPE_KNOCKOUT 2
#define SECTOR_DATA_SIZE 3968
#define SECTOR_FOOTER_SIZE 128
#define SECTOR_SIZE 4096
#define SPECIAL_SECTOR_SENTINEL 0xB39D
#define SECTOR_ID_TRAINER_TOWER_1 30
#define SECTOR_ID_TRAINER_TOWER_2 31
#define SAVE_STATUS_OK 1
#define SAVE_STATUS_ERROR 0xFF
#define ABSPATH(x) x
#define AGB_ASSERT_EX(expr,file,line) ((void)0);
struct TrainerTowerTrainer { u8 bytes[328]; };
struct TrainerTowerFloor {
    u8 id, floorIdx, challengeType, prize;
    struct TrainerTowerTrainer trainers[3];
    u32 checksum;
};
struct EReaderTrainerTowerSet {
    u8 numFloors, id; u16 dummy; u32 checksum;
    struct TrainerTowerFloor floors[8];
};
struct HostSaveBlock1 { struct { u8 unk9; } trainerTower[1]; };
static struct HostSaveBlock1 saveBlock;
static struct HostSaveBlock1 *gSaveBlock1Ptr = &saveBlock;
struct SaveSector {
    u8 data[SECTOR_DATA_SIZE];
    u8 unused[SECTOR_FOOTER_SIZE - 12];
    u16 id, checksum; u32 signature, counter;
};
#define SECTOR_COUNTER_OFFSET offsetof(struct SaveSector, counter)
#define SEC30_SIZE offsetof(struct EReaderTrainerTowerSet, floors[4])
#define SEC31_SIZE (sizeof(struct EReaderTrainerTowerSet) - SEC30_SIZE)
_Static_assert(sizeof(struct TrainerTowerTrainer)==328, "trainer ABI");
_Static_assert(sizeof(struct TrainerTowerFloor)==992, "floor ABI");
_Static_assert(sizeof(struct EReaderTrainerTowerSet)==7944, "set ABI");
_Static_assert(sizeof(struct SaveSector)==4096, "sector ABI");
_Static_assert(SECTOR_COUNTER_OFFSET==4092, "counter ABI");
_Static_assert(SEC30_SIZE==3976 && SEC31_SIZE==3968, "split ABI");
static struct SaveSector gSaveDataBuffer;
static u8 physical[2][SECTOR_SIZE];
static bool fail_write[2];
static unsigned writes[2], reads[2];
static void check(bool cond, const char *msg) {
    if (!cond) { fprintf(stderr, "FAIL %s\n", msg); exit(3); }
}
static void ReadFlash(u16 sector, u32 offset, void *dst, u32 size) {
    check(sector==30 || sector==31, "unexpected read ID");
    check(offset==0 && size==SECTOR_SIZE, "unexpected read extent");
    reads[sector-30]++;
    memcpy(dst, physical[sector-30], size);
}
static u32 ProgramFlashSectorAndVerify(u16 sector, u8 *src) {
    check(sector==30 || sector==31, "unexpected write ID");
    writes[sector-30]++;
    if (fail_write[sector-30]) return 1;
    memcpy(physical[sector-30], src, SECTOR_SIZE);
    return 0;
}
static void *AllocZeroed(size_t n) {
    void *p=calloc(1,n); check(p!=NULL,"allocation"); return p;
}
static void Free(void *p) { free(p); }
PHASE1_PINNED_ORIGINAL_BYTE_SUM_FUNCTION
PHASE1_PINNED_SPECIAL_SECTOR_FUNCTIONS
PHASE1_PINNED_CEREADER_FUNCTIONS
static void reset_io(void) {
    memset(physical,0,sizeof physical);
    memset(&gSaveDataBuffer,0,sizeof gSaveDataBuffer);
    memset(writes,0,sizeof writes); memset(reads,0,sizeof reads);
    fail_write[0]=fail_write[1]=false;
}
static void valid(struct EReaderTrainerTowerSet *s, u8 seed) {
    memset(s,0,sizeof *s); s->numFloors=8;
    for(unsigned i=0;i<8;i++) {
        struct TrainerTowerFloor *f=&s->floors[i];
        f->floorIdx=i+1; f->challengeType=0;
        f->trainers[0].bytes[5]=seed+i;
        f->checksum=CalcByteArraySum((const u8*)f,offsetof(struct TrainerTowerFloor,checksum));
    }
    s->checksum=CalcByteArraySum((const u8*)s->floors,
                                 8*sizeof(s->floors[0]));
    check(ValidateTrainerTowerData(s)==TRUE,"valid input");
}
static void verify(void) {
    struct EReaderTrainerTowerSet old, newer, dest;
    u8 old_second[SECTOR_SIZE];
    reset_io(); valid(&old,11); valid(&newer,77);
    check(CEReaderTool_SaveTrainerTower(&old)==TRUE,"initial write");
    check(writes[0]==1 && writes[1]==1,"both writes");
    u32 sentinel=0;
    memcpy(&sentinel,physical[0],sizeof sentinel);
    check(sentinel==SPECIAL_SECTOR_SENTINEL,"sector30 sentinel");
    memcpy(&sentinel,physical[1],sizeof sentinel);
    check(sentinel==SPECIAL_SECTOR_SENTINEL,"sector31 sentinel");
    check(physical[0][5]==1,"producer counter byte");
    memset(&dest,0xCC,sizeof dest);
    check(CEReaderTool_LoadTrainerTower(&dest)==TRUE,"positive read");
    old.id=1;
    check(memcmp(&dest,&old,sizeof old)==0,"7944-byte roundtrip");
    puts("INTEGRATED_PHYSICAL_ROUNDTRIP bytes=7944 sectors=30,31 sentinel=1");
    memcpy(old_second,physical[1],sizeof old_second);
    fail_write[1]=true;
    check(CEReaderTool_SaveTrainerTower(&newer)==FALSE,"failed second write");
    check(memcmp(physical[1],old_second,sizeof old_second)==0,"old sector31");
    memset(&dest,0xCC,sizeof dest);
    check(CEReaderTool_LoadTrainerTower(&dest)==FALSE,"mixed checksum rejection");
    check(memcmp(&dest,physical[0]+4,SEC30_SIZE)==0,"new first copied");
    check(memcmp((u8*)&dest+SEC30_SIZE,old_second+4,SEC31_SIZE)==0,
          "old second copied");
    puts("INTEGRATED_SECOND_WRITE_FAILURE first_updated=1 second_old=1 loader_rejects=1 destination_mutated=7944");
    fail_write[1]=false;
    check(CEReaderTool_SaveTrainerTower(&newer)==TRUE,"retry writer");
    memset(&dest,0xCC,sizeof dest);
    check(CEReaderTool_LoadTrainerTower(&dest)==TRUE,"retry reader");
    newer.id=1;
    check(memcmp(&dest,&newer,sizeof newer)==0,"retry exact");
    puts("INTEGRATED_RETRY bytes=7944");
    physical[0][0]^=1;
    memset(&dest,0xCC,sizeof dest);
    check(CEReaderTool_LoadTrainerTower(&dest)==FALSE,"bad first sentinel");
    for(size_t i=0;i<sizeof dest;i++)
        check(((u8*)&dest)[i]==0xCC,"first failure destination untouched");
    puts("INTEGRATED_FIRST_SENTINEL_FAILURE destination_unchanged=7944");
    physical[0][0]^=1;
    physical[1][0]^=1;
    memset(&dest,0xCC,sizeof dest);
    check(CEReaderTool_LoadTrainerTower(&dest)==FALSE,"bad second sentinel");
    check(memcmp(&dest,physical[0]+4,SEC30_SIZE)==0,"first copied on second fail");
    for(size_t i=SEC30_SIZE;i<sizeof dest;i++)
        check(((u8*)&dest)[i]==0xCC,"second unchanged");
    puts("INTEGRATED_SECOND_SENTINEL_FAILURE first_copied=3976 second_preserved=3968");
    check(ReadTrainerTowerAndValidate()==FALSE,"stock stub");
    puts("INTEGRATED_STOCK_STUB returns_false=1");
    puts("PHASE1_DONE gate=FAIL_INCOMPLETE approvals=0");
}
int main(void) { verify(); return 0; }
