/* Phase 1 host execution of exact pinned src/cereader_tool.c, not GBA/mGBA.
 * Fake sector reads/writes deliberately isolate C destination-mutation semantics.
 * The shim does NOT implement the real special-sector sentinel or Flash timing.
 */
#include "global.h"
static struct HostSaveBlock1 save_block;
struct HostSaveBlock1 *gSaveBlock1Ptr = &save_block;
static u8 sector[2][SECTOR_SIZE];
static bool present[2] = {true,true};
static bool write_ok[2] = {true,true};
static int reads[2], writes[2];
static void check(bool condition, const char *label) {
    if (!condition) { fprintf(stderr, "FAIL: %s\n",label); exit(1); }
}
void *AllocZeroed(size_t size) { void *p=calloc(1,size); check(p!=NULL,"allocation"); return p; }
void Free(void *p) { free(p); }
u32 CalcByteArraySum(const u8 *data,u32 n) { u32 sum=0; for(u32 i=0;i<n;i++) sum+=data[i]; return sum; }
static int index_for(u16 id) { check(id==30 || id==31,"special sector id"); return id-30; }
bool32 TryWriteSpecialSaveSector(u16 id,u8 *buf) { int i=index_for(id); writes[i]++; if(!write_ok[i])return FALSE; memcpy(sector[i],buf,SECTOR_SIZE); present[i]=true; return TRUE; }
bool32 TryReadSpecialSaveSector(u16 id,void *buf) { int i=index_for(id); reads[i]++; if(!present[i])return FALSE; memcpy(buf,sector[i],SECTOR_SIZE); return TRUE; }
static void reset_io(void) { memset(sector,0,sizeof sector); present[0]=present[1]=true; write_ok[0]=write_ok[1]=true; memset(reads,0,sizeof reads); memset(writes,0,sizeof writes); }
static void make_valid(struct EReaderTrainerTowerSet *set,int n,int seed) {
    memset(set,0,sizeof *set); set->numFloors=n;
    for(int i=0;i<8;i++) {
        struct TrainerTowerFloor *f=&set->floors[i]; f->floorIdx=i+1; f->challengeType=0; f->trainers[0].bytes[5]=seed+i;
        f->checksum=CalcByteArraySum((u8*)f,offsetof(struct TrainerTowerFloor,checksum));
    }
    set->checksum=CalcByteArraySum((u8*)set->floors,n*sizeof set->floors[0]);
    check(ValidateTrainerTowerData(set)==TRUE,"valid seed set");
}
static void verify_second_read_failure(void) {
    struct EReaderTrainerTowerSet a,d;
    reset_io(); make_valid(&a,8,11); check(CEReaderTool_SaveTrainerTower(&a)==TRUE,"write positive");
    check(writes[0]==1&&writes[1]==1,"write count");
    check(sector[0][1]==1,"producer header increment");
    memset(&d,0xCC,sizeof d); present[1]=false;
    check(CEReaderTool_LoadTrainerTower(&d)==FALSE,"missing second rejected");
    check(memcmp(&d,sector[0],3976)==0,"first half overwritten despite failure");
    for(size_t i=3976;i<sizeof d;i++) check(((u8*)&d)[i]==0xCC,"second half remains sentinel");
    printf("SECOND_SECTOR_MISSING partial_first_bytes=3976 preserved_second_bytes=3968\n");
}
static void verify_first_read_failure(void) {
    struct EReaderTrainerTowerSet a,d;
    reset_io(); make_valid(&a,8,17); check(CEReaderTool_SaveTrainerTower(&a)==TRUE,"write first missing fixture");
    memset(&d,0xCC,sizeof d); present[0]=false;
    check(CEReaderTool_LoadTrainerTower(&d)==FALSE,"missing first rejected");
    for(size_t i=0;i<sizeof d;i++) check(((u8*)&d)[i]==0xCC,"first missing leaves destination unchanged");
    printf("FIRST_SECTOR_MISSING destination_unchanged=7944\n");
}
static void verify_checksum_failure(void) {
    struct EReaderTrainerTowerSet a,d;
    reset_io(); make_valid(&a,8,19); check(CEReaderTool_SaveTrainerTower(&a)==TRUE,"write checksum fixture");
    sector[1][20]^=0x80; memset(&d,0xCC,sizeof d);
    check(CEReaderTool_LoadTrainerTower(&d)==FALSE,"checksum mismatch rejected");
    check(memcmp((u8*)&d+3976,sector[1],3968)==0,"second half copied before checksum failure");
    check(((u8*)&d)[3976+20]!=0xCC,"second half mutated on checksum failure");
    printf("SECOND_SECTOR_CHECKSUM_FAILURE destination_mutated=7944\n");
}
static void verify_success(void) {
    struct EReaderTrainerTowerSet a,d;
    reset_io(); make_valid(&a,8,23); check(CEReaderTool_SaveTrainerTower(&a)==TRUE,"positive writer");
    memset(&d,0xCC,sizeof d); check(CEReaderTool_LoadTrainerTower(&d)==TRUE,"positive reader");
    a.id=1; check(memcmp(&a,&d,sizeof d)==0,"positive exact content");
    printf("VALID_TWO_SECTOR_ROUNDTRIP bytes=7944\n");
}
static void verify_mixed(int n,bool expect_success) {
    struct EReaderTrainerTowerSet old,new,d;
    reset_io(); make_valid(&old,n,25); make_valid(&new,n,71);
    check(CEReaderTool_SaveTrainerTower(&old)==TRUE,"old generation write");
    u8 old_second[SECTOR_SIZE]; memcpy(old_second,sector[1],SECTOR_SIZE);
    check(CEReaderTool_SaveTrainerTower(&new)==TRUE,"new generation write");
    memcpy(sector[1],old_second,SECTOR_SIZE);
    memset(&d,0xCC,sizeof d);
    check(CEReaderTool_LoadTrainerTower(&d)==expect_success,"mixed generation result");
    check(memcmp(&d,sector[0],3976)==0,"mixed first new");
    check(memcmp((u8*)&d+3976,old_second,3968)==0,"mixed second old");
    printf("MIXED_GENERATION floors=%d accepted=%d mutated_bytes=7944\n",n,expect_success);
}
static void verify_writer_failure(void) {
    struct EReaderTrainerTowerSet a;
    reset_io(); make_valid(&a,8,7); write_ok[1]=false;
    check(CEReaderTool_SaveTrainerTower(&a)==FALSE,"second write fails");
    check(writes[0]==1 && writes[1]==1,"both writes attempted");
    check(sector[0][0]==8 && sector[1][0]==0,"first write committed second not");
    printf("SECOND_SECTOR_WRITE_FAILURE first_sector_mutated=1 second_unchanged=1\n");
}
static void verify_first_writer_failure_preserves_both(void) {
    struct EReaderTrainerTowerSet old, newer;
    u8 before[2][SECTOR_SIZE];
    reset_io(); make_valid(&old,8,31); make_valid(&newer,8,73);
    check(CEReaderTool_SaveTrainerTower(&old)==TRUE,"baseline first-write fixture");
    memcpy(before,sector,sizeof before);
    memset(writes,0,sizeof writes);
    write_ok[0]=false;
    check(CEReaderTool_SaveTrainerTower(&newer)==FALSE,"first write rejected");
    check(writes[0]==1 && writes[1]==0,"second write not attempted");
    check(memcmp(sector,before,sizeof before)==0,"both sectors preserved on first write failure");
    printf("FIRST_SECTOR_WRITE_FAILURE both_sectors_unchanged=1 second_write_attempts=0\n");
}
static void verify_second_writer_retry(void) {
    struct EReaderTrainerTowerSet old, newer, d;
    u8 old_second[SECTOR_SIZE];
    reset_io(); make_valid(&old,8,33); make_valid(&newer,8,79);
    check(CEReaderTool_SaveTrainerTower(&old)==TRUE,"old complete generation");
    memcpy(old_second,sector[1],SECTOR_SIZE);
    write_ok[1]=false;
    check(CEReaderTool_SaveTrainerTower(&newer)==FALSE,"new second writer fails");
    check(memcmp(sector[1],old_second,SECTOR_SIZE)==0,"old second retained");
    memset(&d,0xCC,sizeof d);
    check(CEReaderTool_LoadTrainerTower(&d)==FALSE,"mixed eight-floor generation rejected");
    check(memcmp(&d,sector[0],3976)==0,"failed load copied new first");
    check(memcmp((u8*)&d+3976,old_second,3968)==0,"failed load copied old second");
    write_ok[1]=true;
    check(CEReaderTool_SaveTrainerTower(&newer)==TRUE,"retry writes both");
    memset(&d,0xCC,sizeof d);
    check(CEReaderTool_LoadTrainerTower(&d)==TRUE,"retry recovers valid generation");
    newer.id=1;
    check(memcmp(&newer,&d,sizeof d)==0,"retry exact generation recovered");
    printf("SECOND_SECTOR_WRITE_RETRY failed_load_mutated=7944 retry_recovered=7944\n");
}
static void verify_second_reader_retry(void) {
    struct EReaderTrainerTowerSet a,d;
    reset_io(); make_valid(&a,8,47);
    check(CEReaderTool_SaveTrainerTower(&a)==TRUE,"reader retry baseline");
    present[1]=false; memset(&d,0xCC,sizeof d);
    check(CEReaderTool_LoadTrainerTower(&d)==FALSE,"missing second first read");
    check(memcmp(&d,sector[0],3976)==0,"first half mutated on first read");
    present[1]=true;
    check(CEReaderTool_LoadTrainerTower(&d)==TRUE,"second read retry");
    a.id=1;
    check(memcmp(&a,&d,sizeof d)==0,"retry overwrote stale partial destination");
    printf("SECOND_SECTOR_READ_RETRY initial_partial=3976 retry_recovered=7944\n");
}
int main(void) {
    verify_success(); verify_first_read_failure(); verify_second_read_failure(); verify_checksum_failure(); verify_mixed(4,true); verify_mixed(5,false); verify_writer_failure();
    verify_first_writer_failure_preserves_both(); verify_second_writer_retry(); verify_second_reader_retry();
    check(ReadTrainerTowerAndValidate()==FALSE,"stock stub false");
    printf("HOST_C_PINNED_FUNCTIONS PASS cases=10 gate=FAIL_INCOMPLETE approvals=0\n");
    return 0;
}
