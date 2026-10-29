/* Test-only native mGBA entry into original-agbcc linked FireRed stub.
 * No gameplay dispatch, no e-Reader payload, no Flash transactions.
 */
#include <mgba/core/core.h>
#include <mgba/gba/core.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/arm/arm.h>
#include <mgba/internal/arm/isa-inlines.h>
#include <mgba-util/vfs.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

enum { MAX_STEPS = 32 };
static void need(bool ok, const char *why) {
    if (!ok) { fprintf(stderr, "FAIL %s\n", why); exit(3); }
}
static uint8_t *read_rom(const char *path, size_t *size) {
    FILE *f=fopen(path,"rb"); need(f!=NULL,"rom_open");
    need(fseek(f,0,SEEK_END)==0,"rom_seek");
    long n=ftell(f); need(n>0 && n<0x2000000,"rom_size");
    need(fseek(f,0,SEEK_SET)==0,"rom_rewind");
    uint8_t *p=malloc((size_t)n);
    need(p!=NULL && fread(p,1,(size_t)n,f)==(size_t)n,"rom_read");
    fclose(f); *size=(size_t)n; return p;
}
static void run(const uint8_t *rom,size_t rom_size,uint32_t address,uint32_t input) {
    struct mCore *core=GBACoreCreate();
    need(core!=NULL && core->init(core),"native_core_init");
    mCoreInitConfig(core,NULL);
    struct VFile *vf=VFileFromConstMemory(rom,rom_size);
    need(vf!=NULL && core->loadROM(core,vf),"native_rom_load");
    core->reset(core);
    struct GBA *gba=core->board;
    struct ARMCore *cpu=gba->cpu;
    need(cpu!=NULL,"native_arm_cpu");
    core->busWrite32(core,0x02001000U,0x5A17C0DEU);
    need(core->busRead32(core,0x02001000U)==0x5A17C0DEU,"ewram_marker_setup");
    cpu->gprs[0]=input;
    cpu->gprs[ARM_SP]=0x03007F00U;
    cpu->gprs[ARM_LR]=0x03000001U;
    cpu->executionMode=MODE_THUMB;
    cpu->cpsr.t=1;
    cpu->gprs[ARM_PC]=address;
    ThumbWritePC(cpu);
    unsigned steps=0;
    bool returned=false;
    for (;steps<MAX_STEPS;steps++) {
        core->step(core);
        uint32_t pc=(uint32_t)cpu->gprs[ARM_PC];
        if(pc>=0x03000000U && pc<=0x03000008U) {
            returned=true;steps++;break;
        }
    }
    uint32_t result=(uint32_t)cpu->gprs[0];
    need(returned && steps>0 && steps<=MAX_STEPS,"original_stub_return");
    need(result==0,"original_stub_false");
    need(core->busRead32(core,0x02001000U)==0x5A17C0DEU,"ewram_marker_unchanged");
    printf("CASE input=0x%08x returned=1 steps=%u result=0x%08x marker=unchanged\n",
           input,steps,result);
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
}
int main(int argc,char **argv) {
    need(argc==3,"usage_ROM_AND_SYMBOL");
    size_t size=0;
    uint8_t *rom=read_rom(argv[1],&size);
    char *end=NULL;
    unsigned long parsed=strtoul(argv[2],&end,0);
    need(end && *end=='\0' && parsed>=0x08000000UL &&
         parsed<0x0A000000UL,"linked_symbol_address");
    uint32_t address=(uint32_t)parsed & ~1U;
    run(rom,size,address,0);
    run(rom,size,address,0xFFFFFFFFU);
    run(rom,size,address,0x13579BDFU);
    puts("SUMMARY native_mgba=true original_agbcc_arm=true linked_stub_false=true synthetic_direct_entry=true stock_gameplay=false flash_transaction=false physical_hardware=false phase1_gate=FAIL_INCOMPLETE approvals=0");
    free(rom);
    return 0;
}
