/* R18 genuine Emerald Flash save across independent native mGBA processes.
 * Uses original Game Boy Advance Save/NOR flash sector operations, Emerald's
 * trainer-ID-dependent pointer relocation and CB2_ContinueSavedGame.
 */
#ifndef XGBA_R18_EMERALD_FLASH_H
#define XGBA_R18_EMERALD_FLASH_H
#define R18_MAGIC 0x52313845u
#define R40_SCRIPT_ID "emerald.r40.script"
#define R40_NATIVE_VALUE 0x5A39u
#define R40_NATIVE_STATE_READY 1u
#define R40_NATIVE_STATE_RESTORED 2u
#define R40_NATIVE_STATE_REFUSED 0xE40u
static int r40_fixture(const struct ResourceFile *source)
{
    if(source->extra_count!=1u)return 0;
    if(strcmp(source->extra[0].id,R40_SCRIPT_ID) ||
       source->extra[0].length!=9u)
        fail("R40 script test expects exactly one nine-byte source-bound external resource");
    return 1;
}
static uint32_t r18_read(struct mCore *c,uint32_t p,unsigned field);
static void r40_assert(struct mCore *core,uint32_t save,unsigned phase)
{
    uint32_t state=r18_read(core,save,11u);
    uint32_t fetches=r18_read(core,save,12u);
    uint32_t executions=r18_read(core,save,13u);
    uint32_t value=r18_read(core,save,14u);
    uint32_t flag=r18_read(core,save,15u);
    uint32_t errors=r18_read(core,save,16u);
    if(state!=phase || fetches!=(phase==R40_NATIVE_STATE_RESTORED?0u:1u) ||
       executions!=(phase==R40_NATIVE_STATE_READY?1u:0u) ||
       value!=(phase==R40_NATIVE_STATE_REFUSED?0u:R40_NATIVE_VALUE) ||
       flag!=(phase==R40_NATIVE_STATE_REFUSED?0u:1u) ||
       errors!=(phase==R40_NATIVE_STATE_REFUSED?1u:0u))
        fail("R40 real Emerald game variable/flag, interpreter execution, or source SHA gate mismatched");
}
static uint32_t r18_read(struct mCore *c,uint32_t p,unsigned field)
{
    return c->busRead32(c,p+4u*field);
}
static void r18_check(struct mCore *c,uint32_t save)
{
    if(save<0x02000000u || save+44u>0x02040000u ||
       r18_read(c,save,0)!=R18_MAGIC)
        fail("R18 real source-built Emerald Flash save-state evidence missing");
}
/* R42 original Emerald gameplay, source-labelled scripts (never real HnS
 * / Rocket binary execution). R40 and R18 modes remain ABI unchanged. */
#define R42_STATE_READY 1u
#define R42_STATE_RESTORED 2u
#define R42_STATE_COMPLETE 3u
#define R42_ROCKET_VALUE 0x524Bu
#define R42_JOHTO_VALUE 0x484Eu
static int r42_fixture(const struct ResourceFile *source)
{
    if(source->extra_count!=2u)return 0;
    if(strcmp(source->extra[0].id,"rocket.r42.event") ||
       strcmp(source->extra[1].id,"heart_soul.r42.event") ||
       source->extra[0].length!=96u || source->extra[1].length!=96u)
        fail("R42 native event requires exactly two source-labelled 96-byte sidecar assets");
    return 1;
}
static void r42_assert(struct mCore *core,uint32_t save,unsigned state)
{
    unsigned current=r18_read(core,save,11u);
    unsigned fetches=r18_read(core,save,12u);
    unsigned launches=r18_read(core,save,13u);
    unsigned rocket_flag=r18_read(core,save,14u);
    unsigned johto_flag=r18_read(core,save,15u);
    unsigned rocket_var=r18_read(core,save,16u);
    unsigned johto_var=r18_read(core,save,17u);
    unsigned nugget=r18_read(core,save,18u);
    unsigned scarf=r18_read(core,save,19u);
    unsigned errors=r18_read(core,save,20u);
    fprintf(stderr,"R42 native state=%u fetch=%u calls=%u flags=%u,%u vars=%u,%u bag=%u,%u err=%u\\n",
            current,fetches,launches,rocket_flag,johto_flag,rocket_var,johto_var,nugget,scarf,errors);
    if(current!=state || errors!=0u ||
       fetches!=(state==R42_STATE_RESTORED?0u:2u) ||
       launches!=(state==R42_STATE_RESTORED?0u:state==R42_STATE_COMPLETE?2u:1u) ||
       rocket_flag!=1u || rocket_var!=R42_ROCKET_VALUE || nugget!=1u)
        fail("R42 original Emerald Rocket-source adaptation did not execute actual item/flag/var");
    if(state==R42_STATE_COMPLETE || state==R42_STATE_RESTORED) {
        if(johto_flag!=1u || johto_var!=R42_JOHTO_VALUE || scarf!=1u)
            fail("R42 original Emerald Johto-source adaptation did not execute actual item/flag/var");
    } else if(johto_flag!=0u || johto_var!=0u || scarf!=0u) {
        fail("R42 Johto source event triggered before L button");
    }
}
static void xgba_r42_emerald_run(struct mCore *core,uint32_t map,uint32_t save,
                                const char *folder,const char *phase,
                                const struct XgbaGbaDevice *device,
                                const struct ResourceFile *resource)
{
    if(!strcmp(phase,"r42-write")) {
        if(r18_read(core,save,2)!=0u || r18_read(core,save,1)==1u)
            fail("R42 original Emerald first boot must have no previous Flash");
        r14_wait(core,180u);
        r17_check_map(core,map,resource);
        r17_frame(core,folder,"00-original-emerald-external-littleroot");
        r14_press(core,1u<<8,3u); /* original physical R button */
        /* Native Emerald's text printer and waitmessage must finish before
         * waitbuttonpress can receive A; 45 frames only speeds up the text,
         * leaving the global event context locked and suppressing L. */
        r14_wait(core,150u);
        r42_assert(core,save,R42_STATE_READY);
        r17_frame(core,folder,"01-native-rocket-event-dialogue");
        r14_press(core,1u<<0,3u); /* original A, dismiss message */
        r14_wait(core,45u);
        r14_press(core,1u<<0,3u); /* no-op if already dismissed */
        r14_wait(core,45u);
        r14_press(core,1u<<9,3u); /* original physical L button */
        r14_wait(core,150u);
        r42_assert(core,save,R42_STATE_COMPLETE);
        r17_frame(core,folder,"02-native-johto-event-dialogue");
        r14_press(core,1u<<0,3u);
        r14_wait(core,45u);
        r14_press(core,1u<<0,3u);
        r14_wait(core,45u);
        if(device->successful_reads!=4u || device->failed_reads)
            fail("R42 original Emerald failed two independently verified external event reads");
        r14_press(core,1u<<2,3u); /* actual GBA SELECT -> original TrySavingData */
        for(unsigned i=0;i<3400u && r18_read(core,save,4u)==0u;++i) {
            core->setKeys(core,0u);core->runFrame(core);
        }
        r14_wait(core,20u);
        if(r18_read(core,save,3u)!=1u || r18_read(core,save,4u)!=1u)
            fail("R42 native original Emerald Flash-sector save callback unsuccessful");
        r42_assert(core,save,R42_STATE_COMPLETE);
        r17_frame(core,folder,"03-real-flash-saved-both-events");
        puts("PASS_R42_NATIVE_GAME_TWO_EXTERNAL_EVENTS dialogue=1 rocket_nugget=1 johto_silk_scarf=1 native_flash=1");
    }else if(!strcmp(phase,"r42-continue")) {
        if(r18_read(core,save,1u)!=1u || r18_read(core,save,2u)!=1u)
            fail("R42 native Emerald did not cold load original Flash");
        r14_wait(core,210u);
        r17_check_map(core,map,resource);
        r42_assert(core,save,R42_STATE_RESTORED);
        if(device->successful_reads!=2u || device->failed_reads)
            fail("R42 cold restarted native Emerald unnecessarily fetched original script packs");
        r17_frame(core,folder,"04-cold-restarted-original-emerald-items-restored");
        puts("PASS_R42_NATIVE_EMERALD_COLD_RESTORED_BOTH_EVENTS original_flash=1 no_reexecution=1 bag=2 flags=2 vars=2");
    }else fail("R42 native emulator requested unsupported phase");
}
/* R49 test-only: source-built Emerald must still run/save with a host-side
 * manifest holding >16 distinct future original-event resources. These are
 * authored event-shaped CI pages, NOT original ROM NPCs or interactions. */
static int r49_fixture_registered_pages(const struct ResourceFile *source)
{
    unsigned i;
    if(source->extra_count!=32u)return 0;
    for(i=0u;i<32u;i++){
        char id[64];
        snprintf(id,sizeof(id),"r49.synthetic.original_event_page.%03u",i);
        if(strcmp(source->extra[i].id,id) ||
           source->extra[i].length!=256u ||
           source->extra[i].offset<=32u*1024u*1024u)
            fail("R49 exact authored resource register regression unexpected");
    }
    return 1;
}
static void xgba_r18_emerald_run(struct mCore *core,uint32_t map,uint32_t save,
                                 const char *folder,const char *phase,
                                 const struct XgbaGbaDevice *device,
                                 const struct ResourceFile *resource,int enabled)
{
    if(!core||!map||!save||!folder||!phase||!enabled||!resource->second_id)
        fail("R18 requires original Emerald game, Flash proof, and both resources");
    const int r40=r40_fixture(resource);
    const int r42=r42_fixture(resource);
    const int r49=r49_fixture_registered_pages(resource);
    if(resource->extra_count && !r40 && !r42 && !r49)
        fail("Unrecognized original Emerald external script source set");
    r18_check(core,save);
    if(r42) {
        xgba_r42_emerald_run(core,map,save,folder,phase,device,resource);
        return;
    }
    if(!strcmp(phase,"write")) {
        if(r18_read(core,save,2)!=0u || r18_read(core,save,1)==1u)
            fail("R18 first Emerald process unexpectedly continued an existing save");
        r14_wait(core,180u);
        r17_check_map(core,map,resource);
        if(r40) {
            /* Native field callback may start after the R18 map-ready proof.
             * Pump real emulated frames rather than injecting event state. */
            for(unsigned i=0;i<600u && r18_read(core,save,11u)==0u;++i) {
                core->setKeys(core,0u);
                core->runFrame(core);
            }
            fprintf(stderr,"R40 first-boot diag: state=%u fetches=%u executions=%u value=%u flag=%u errors=%u reads=%u failed=%u lookups=%u\\n",
                    r18_read(core,save,11u),r18_read(core,save,12u),
                    r18_read(core,save,13u),r18_read(core,save,14u),
                    r18_read(core,save,15u),r18_read(core,save,16u),
                    device->successful_reads,device->failed_reads,resource->lookups);
            r40_assert(core,save,R40_NATIVE_STATE_READY);
        }
        if(device->successful_reads!=(r40?3u:2u) || device->failed_reads)
            fail("R18 original Emerald first load did not acquire external map/script");
        r17_frame(core,folder,"01-original-emerald-before-flash");
        r14_press(core,1u<<2,3u); /* SELECT -> real TrySavingData, not host save */
        for(unsigned f=0;f<3400u && r18_read(core,save,4)==0u;++f) {
            core->setKeys(core,0u);
            core->runFrame(core);
        }
        r14_wait(core,20u);
        r18_check(core,save);
        fprintf(stderr,"R18_EMERALD_SAVE_DIAG boot=%u continue=%u requests=%u "
                "result=%u map=%u:%u pos=%u,%u type=%u reads=%u fail=%u\n",
                r18_read(core,save,1),r18_read(core,save,2),
                r18_read(core,save,3),r18_read(core,save,4),
                r18_read(core,save,5),r18_read(core,save,6),
                r18_read(core,save,7),r18_read(core,save,8),
                r18_read(core,save,10),device->successful_reads,device->failed_reads);
        if(r18_read(core,save,3)!=1u ||
           r18_read(core,save,4)!=1u || /* SAVE_STATUS_OK */
           r18_read(core,save,5)!=0u || r18_read(core,save,6)!=9u)
            fail("R18 original Emerald saving routine failed to complete genuine Flash sectors");
        r17_check_map(core,map,resource);
        r17_frame(core,folder,"02-original-emerald-after-flash-write");
        puts("PASS_R18_EMERALD_ORIGINAL_FLASH_WRITE game_save=1 sector_write=1 map=0:9");
        if(r40) {
            r40_assert(core,save,R40_NATIVE_STATE_READY);
            puts("PASS_R40_NATIVE_EMERALD_SCRIPT_FLASH_WRITE interpreter=original_scripttable source=sidecar flag=1 var=23097");
        }
    }else if(!strcmp(phase,"continue")) {
        if(r18_read(core,save,1)!=1u || r18_read(core,save,2)!=1u)
            fail("R18 new native Emerald process did not load actual saved Flash");
        r14_wait(core,200u);
        r17_check_map(core,map,resource);
        if(device->successful_reads!=2u || device->failed_reads ||
           resource->reads!=2u)
            fail("R18 native Emerald cold continuation did not re-fetch external map");
        r17_frame(core,folder,"03-cold-emerald-reacquired-littleroot");
        if(r40) {
            r40_assert(core,save,R40_NATIVE_STATE_RESTORED);
            puts("PASS_R40_NATIVE_EMERALD_COLD_SCRIPT_FLASH_RESTORE original_LoadGameSave=1 script_reexecutions=0 flag=1 var=23097");
        }
        printf("PASS_R18_EMERALD_COLD_FLASH_CONTINUE original_LoadGameSave=1 "
               "CB2_ContinueSavedGame=1 external_littleroot_reacquired=1 "
               "native_grid=1 bg_vram=1 reads=%u\n",
               device->successful_reads);
    }else if(!strcmp(phase,"corrupt")){
        if(r18_read(core,save,1)!=1u || r18_read(core,save,2)!=1u)
            fail("R18 wrong-pack test did not load genuine Emerald Flash save");
        if(r17_word(core,map,1)!=0xE17u || resource->reads<1u ||
           device->successful_reads!=1u || device->failed_reads<1u)
            fail("R18 corrupted external pack was not rejected by native emulator");
        puts("PASS_R18_EMERALD_COLD_BAD_PACK_REFUSED original_flash_valid=1 "
             "corrupt_external_map_refused=1");
    }else if(!strcmp(phase,"r40-corrupt") && r40) {
        /* Independent clean boot. A deliberately altered source script must
         * be refused by native mGBA's pinned SHA check, before any real
         * Emerald command is executed or a Flash save is requested. */
        if(r18_read(core,save,2)!=0u)
            fail("R40 corrupt-script negative test had a prior Flash save");
        r14_wait(core,180u);
        r17_check_map(core,map,resource);
        r40_assert(core,save,R40_NATIVE_STATE_REFUSED);
        if(device->successful_reads!=2u || device->failed_reads<1u ||
           r18_read(core,save,3)!=0u)
            fail("R40 corrupt external script was executed or saved");
        puts("PASS_R40_BAD_EXTERNAL_SCRIPT_SHA_REFUSED native_original_flag=0 native_original_var=0 no_flash_write=1");
    }else{
        fail("R18 native Emerald Flash phase unknown");
    }
}
#endif
