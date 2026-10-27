/* Phase 1: compile exact pinned FireRed + mGBA Flash functions into a stubbed bus.
   No native ROM, hardware or full emulator executes here. */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
enum { GBA_SAVEDATA_FLASH512=4, GBA_SAVEDATA_FLASH1M=5 };
enum { FLASH_STATE_RAW=0, FLASH_STATE_START=1, FLASH_STATE_CONTINUE=2 };
enum { FLASH_COMMAND_START=0xAA, FLASH_COMMAND_CONTINUE=0x55,
       FLASH_COMMAND_ERASE_CHIP=0x10, FLASH_COMMAND_ERASE_SECTOR=0x30,
       FLASH_COMMAND_NONE=0, FLASH_COMMAND_ERASE=0x80, FLASH_COMMAND_ID=0x90,
       FLASH_COMMAND_PROGRAM=0xA0, FLASH_COMMAND_SWITCH_BANK=0xB0,
       FLASH_COMMAND_TERMINATE=0xF0 };
enum { FLASH_BASE_HI=0x5555, FLASH_BASE_LO=0x2AAA,
       GBA_SIZE_FLASH512=0x10000, GBA_SIZE_FLASH1M=0x20000,
       FLASH_ERASE_CYCLES=30000, FLASH_PROGRAM_CYCLES=650,
       mSAVEDATA_DIRT_NEW=1, MAP_WRITE=2 };
struct mTiming { int placeholder; };
struct mTimingEvent { int placeholder; };
struct GBA { struct mTiming timing; };
struct VFile {
  void (*unmap)(struct VFile*, void*, size_t);
  long (*size)(struct VFile*);
  bool (*truncate)(struct VFile*, size_t);
  void* (*map)(struct VFile*, size_t, int);
};
struct GBASavedata {
  struct GBA* p;
  int type;
  uint8_t* data;
  uint8_t* currentBank;
  int command;
  int flashState;
  int dirty;
  struct mTimingEvent dust;
  unsigned settling;
  struct VFile* vf;
};
static struct GBA gba;
static struct GBASavedata s;
static int callbacks;
static int scheduled;
static int checks;
static int waitCalls;
static u8 waitPhase, waitLast;
static u16 regWaitcnt;
#define REG_WAITCNT regWaitcnt
#define WAITCNT_SRAM_MASK 0x3
#define WAITCNT_SRAM_8 0
#define FLASH_BASE (s.currentBank)
struct FlashType { u16 wait[2]; };
static struct FlashType flashType = { {3, 1} };
static const struct FlashType *gFlash = &flashType;
static void SetReadFlash1(u16* dest) { (void)dest; }
static u16 waitFlashStub(u8 phase, u8* addr, u8 last) {
  (void)addr;
  ++waitCalls; waitPhase=phase; waitLast=last;
  return 0;
}
static u16 (*WaitForFlashWrite)(u8,u8*,u8) = waitFlashStub;
static void mTimingDeschedule(struct mTiming* t, struct mTimingEvent* e) {
  (void)t; (void)e; scheduled=0;
}
static void mTimingSchedule(struct mTiming* t, struct mTimingEvent* e, int cycles) {
  (void)t; (void)e; scheduled=cycles;
}
#define mLOG(...) ((void)0)
#define mCALLBACKS_INVOKE(p, x) do { (void)(p); ++callbacks; } while(0)
#define FLASH_WRITE(addr,val) GBASavedataWriteFlash(&s,(u16)(addr),(u8)(val))
static void _flashSwitchBank(struct GBASavedata*, int);
static void _flashErase(struct GBASavedata*);
static void _flashEraseSector(struct GBASavedata*, uint16_t);
void GBASavedataWriteFlash(struct GBASavedata*, uint16_t, uint8_t);
/* PINNED_FUNCTIONS_INSERT */
static void check(bool ok, const char* what) {
  ++checks;
  if (!ok) { fprintf(stderr,"FAIL %s\n",what); exit(3); }
}
static void unlock(void) {
  FLASH_WRITE(0x5555,0xAA);
  FLASH_WRITE(0x2AAA,0x55);
}
static void program(uint16_t addr, uint8_t value) {
  unlock(); FLASH_WRITE(0x5555,0xA0); FLASH_WRITE(addr,value);
}
static void eraseSector(uint16_t addr) {
  unlock(); FLASH_WRITE(0x5555,0x80);
  unlock(); FLASH_WRITE(addr,0x30);
}
int main(void) {
  uint8_t* bytes=(uint8_t*)malloc(GBA_SIZE_FLASH1M);
  check(bytes!=NULL,"allocation");
  memset(bytes,0xFF,GBA_SIZE_FLASH1M);
  s.p=&gba; s.type=GBA_SAVEDATA_FLASH1M; s.data=bytes;
  s.currentBank=bytes; s.vf=NULL; s.flashState=FLASH_STATE_RAW;
  for (int i=0;i<32;++i) {
    SwitchFlashBank((u8)(i/16));
    check(s.currentBank==bytes+(i/16)*0x10000,"bank selection");
    program((u16)((i%16)*0x1000),(uint8_t)(i+1));
  }
  for (int i=0;i<32;++i)
    check(bytes[i*0x1000]==(uint8_t)(i+1),"32-sector banked programming");
  SwitchFlashBank(1);
  eraseSector(4*0x1000);
  check(bytes[20*0x1000]==0xFF,"bank1 target sector erased");
  check(bytes[19*0x1000]==20,"bank1 adjacent sector retained");
  check(bytes[4*0x1000]==5,"bank0 same-offset sector retained");
  check(s.settling==4,"sector settling index");
  check(scheduled==FLASH_ERASE_CYCLES,"sector erase timing");
  uint8_t* prior=s.currentBank;
  SwitchFlashBank(2);
  check(s.currentBank==prior,"invalid bank rejected");
  check(s.command==FLASH_COMMAND_NONE,"invalid bank command cleared");
  uint8_t old=bytes[21*0x1000];
  FLASH_WRITE(0x5000,0x12);
  check(bytes[21*0x1000]==old,"unlocked data cannot be written");
  check(EraseFlashChip_MX()==0,"actual FireRed chip erase returned success");
  check(waitCalls==1 && waitPhase==3 && waitLast==0xFF,"FireRed chip erase wait phase");
  check(regWaitcnt==WAITCNT_SRAM_8,"FireRed wait state restored");
  for(int i=0;i<32;++i)
    check(bytes[i*0x1000]==0xFF,"full chip erase");
  check((s.dirty & mSAVEDATA_DIRT_NEW)!=0,"dirty flag");
  s.type=GBA_SAVEDATA_FLASH512;
  s.currentBank=bytes;
  callbacks=0;
  SwitchFlashBank(1);
  check(s.type==GBA_SAVEDATA_FLASH1M,"512K bank1 upgrades to 1M");
  check(s.currentBank==bytes+0x10000,"upgraded bank points into second half");
  check(callbacks==1,"memory block change callback");
  program(0x1234,0x00);
  program(0x1234,0xFF);
  check(bytes[0x10000+0x1234]==0xFF,"emulator direct byte overwrite");
  printf("{\"compiled_pinned_functions\":5,\"assertions\":%d,\"sector_programs\":32,\"chip_erase\":true,\"sector_erase\":true,\"invalid_bank_rejected\":true,\"flash512_upgrade\":true,\"full_emulator_executed\":false,\"phase1_gate\":\"FAIL_INCOMPLETE\"}\n",checks);
  free(bytes);
  return 0;
}
