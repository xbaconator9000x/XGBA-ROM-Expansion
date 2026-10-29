/* Phase 1: unchanged original-agbcc FireRed reader instructions in unchanged mGBA.
 * Test-only direct CPU entry, synthetic Poryscript-generated table relocated into
 * a source-built FireRed ROM copy. Not stock gameplay or native table bounds safety.
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
#include <string.h>

enum { TABLE_SIZE=32, TABLE_PAD=4096, MAX_STEPS=500 };
static void need(bool x, const char *name) {
    if (!x) { fprintf(stderr,"FAIL %s\n",name); exit(3); }
}
static uint8_t *read_file(const char *path, size_t *size) {
    FILE *f=fopen(path,"rb");
    need(f!=NULL,"open_input");
    need(fseek(f,0,SEEK_END)==0,"seek_input");
    long n=ftell(f);
    need(n>0,"input_size");
    need(fseek(f,0,SEEK_SET)==0,"rewind_input");
    uint8_t *p=malloc((size_t)n);
    need(p!=NULL && fread(p,1,(size_t)n,f)==(size_t)n,"read_input");
    fclose(f); *size=(size_t)n; return p;
}
static uint32_t read32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static void write32(uint8_t *p,uint32_t v) {
    for(int i=0;i<4;i++)p[i]=(uint8_t)(v>>(i*8));
}
static void run_case(const uint8_t *original,size_t originalSize,
                     const uint8_t *table,uint32_t reader,uint32_t header,
                     uint8_t tag,unsigned malformed) {
    size_t offset=(originalSize+4095U)&~(size_t)4095U;
    size_t romSize=offset+TABLE_PAD;
    need(romSize<0x02000000U,"ROM_aperture");
    uint8_t *rom=malloc(romSize);
    need(rom!=NULL,"ROM_alloc");
    memset(rom,0xFF,romSize);
    memcpy(rom,original,originalSize);
    uint8_t *out=rom+offset;
    memcpy(out,table,TABLE_SIZE);
    uint32_t tableAddress=0x08000000U+(uint32_t)offset;
    const unsigned reloc[]={1,6,15,23};
    for(size_t i=0;i<4;i++) {
        uint32_t old=read32(out+reloc[i]);
        need(old>=0x08000000U && old<0x08000000U+TABLE_SIZE,"table_pointer");
        write32(out+reloc[i],tableAddress+(old-0x08000000U));
    }
    /* Preserve the actual CLI-generated first two records, then deliberately
     * remove its offset-10 outer sentinel. The only replacement sentinel is
     * beyond the original 32-byte table, or absent within the step budget.
     * This tests native out-of-extent traversal, not memory safety.
     */
    if (malformed) {
        need(tag==99 && malformed<=3,"malformed_case_contract");
        memset(out+10,0x7F,TABLE_PAD-10);
        if (malformed==2) out[35]=0;
        if (malformed==3) out[105]=0;
    }
    struct mCore *core=GBACoreCreate();
    need(core!=NULL && core->init(core),"native_core_init");
    mCoreInitConfig(core,NULL);
    struct VFile *vf=VFileFromConstMemory(rom,romSize);
    need(vf!=NULL && core->loadROM(core,vf),"native_ROM_load");
    core->reset(core);
    struct GBA *gba=core->board;
    struct ARMCore *cpu=gba->cpu;
    need(cpu!=NULL,"native_ARM_core");
    core->busWrite32(core,header+8,tableAddress);
    need(core->busRead32(core,header+8)==tableAddress,"real_gMapHeader_pointer");
    cpu->gprs[0]=tag;
    cpu->gprs[ARM_SP]=0x03007F00;
    cpu->gprs[ARM_LR]=0x03000001;
    cpu->executionMode=MODE_THUMB;
    cpu->cpsr.t=1;
    cpu->gprs[ARM_PC]=reader;
    ThumbWritePC(cpu);
    int steps=0;
    bool returned=false;
    for(;steps<MAX_STEPS;steps++) {
        core->step(core);
        uint32_t pc=(uint32_t)cpu->gprs[ARM_PC];
        if(pc>=0x03000000 && pc<=0x03000008) {returned=true;steps++;break;}
    }
    uint32_t result=(uint32_t)cpu->gprs[0];
    if(!malformed) {
        need(returned,"valid_reader_did_not_return");
        uint32_t want=tag==3 ? tableAddress+29 : tag==2 ? tableAddress+11 : 0;
        need(result==want,"valid_reader_pointer");
    } else if (malformed==1) {
        need(!returned && steps==MAX_STEPS-1,
             "missing_sentinel_did_not_exhaust_bounded_budget");
    } else {
        need(returned && result==0,
             "out_of_table_synthetic_sentinel_not_followed");
    }
    need(steps>0 && steps<=MAX_STEPS,"bounded_instruction_count");
    printf("CASE tag=%u malformed=%u returned=%u steps=%d result=0x%08x table=0x%08x\n",
           tag,malformed,returned?1:0,steps,result,tableAddress);
    mCoreConfigDeinit(&core->config);
    core->deinit(core);
    free(rom);
}
int main(int argc,char **argv) {
    need(argc==5,"usage ROM TABLE READER_ADDR HEADER_ADDR");
    size_t romSize=0,tableSize=0;
    uint8_t *rom=read_file(argv[1],&romSize);
    uint8_t *table=read_file(argv[2],&tableSize);
    need(tableSize==TABLE_SIZE,"original_CLI_table_size");
    uint32_t reader=(uint32_t)strtoul(argv[3],NULL,0);
    uint32_t header=(uint32_t)strtoul(argv[4],NULL,0);
    need(reader>=0x08000000 && reader<0x0A000000,"reader_ROM_address");
    need(header>=0x02000000 && header<0x03000000,"gMapHeader_EWRAM_address");
    run_case(rom,romSize,table,reader,header,3,false);
    run_case(rom,romSize,table,reader,header,2,false);
    run_case(rom,romSize,table,reader,header,99,false);
    run_case(rom,romSize,table,reader,header,99,1);
    run_case(rom,romSize,table,reader,header,99,2);
    run_case(rom,romSize,table,reader,header,99,3);
    puts("SUMMARY native_mgba=true original_agbcc_arm=true actual_poryscript_cli_table=true synthetic_direct_entry=true stock_reachability=false physical_flash=false phase1_gate=FAIL_INCOMPLETE approvals=0");
    free(rom);free(table);return 0;
}
