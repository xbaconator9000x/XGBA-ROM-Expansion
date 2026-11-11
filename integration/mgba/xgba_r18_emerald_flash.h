/* R18 genuine Emerald Flash save across independent native mGBA processes.
 * Uses original Game Boy Advance Save/NOR flash sector operations, Emerald's
 * trainer-ID-dependent pointer relocation and CB2_ContinueSavedGame.
 */
#ifndef XGBA_R18_EMERALD_FLASH_H
#define XGBA_R18_EMERALD_FLASH_H
#define R18_MAGIC 0x52313845u
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
static void xgba_r18_emerald_run(struct mCore *core,uint32_t map,uint32_t save,
                                 const char *folder,const char *phase,
                                 const struct XgbaGbaDevice *device,
                                 const struct ResourceFile *resource,int enabled)
{
    if(!core||!map||!save||!folder||!phase||!enabled||!resource->second_id)
        fail("R18 requires original Emerald game, Flash proof, and both resources");
    r18_check(core,save);
    if(!strcmp(phase,"write")) {
        if(r18_read(core,save,2)!=0u || r18_read(core,save,1)==1u)
            fail("R18 first Emerald process unexpectedly continued an existing save");
        r14_wait(core,180u);
        r17_check_map(core,map,resource);
        if(device->successful_reads!=2u || device->failed_reads)
            fail("R18 original Emerald first load did not acquire external map");
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
    }else if(!strcmp(phase,"continue")) {
        if(r18_read(core,save,1)!=1u || r18_read(core,save,2)!=1u)
            fail("R18 new native Emerald process did not load actual saved Flash");
        r14_wait(core,200u);
        r17_check_map(core,map,resource);
        if(device->successful_reads!=2u || device->failed_reads ||
           resource->reads!=2u)
            fail("R18 native Emerald cold continuation did not re-fetch external map");
        r17_frame(core,folder,"03-cold-emerald-reacquired-littleroot");
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
    }else{
        fail("R18 native Emerald Flash phase unknown");
    }
}
#endif
