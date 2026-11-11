/* R15 native FireRed Flash save persistence across actual separate mGBA processes.
 * Takes real LCD screenshots only. Never publishes raw .sav or proprietary data.
 */
#ifndef XGBA_R15_SAVE_H
#define XGBA_R15_SAVE_H
#define R15_SAVE_MAGIC 0x52313550u
#define R15_SAVE_OK 1u
static uint32_t r15_read(struct mCore *c,uint32_t p,unsigned n)
{
    return c->busRead32(c,p+n*4u);
}
static void r15_proof(struct mCore *c,uint32_t p)
{
    if(p<0x02000000u||p+36u>0x02040000u||
       r15_read(c,p,0)!=R15_SAVE_MAGIC)
        fail("R15 real FireRed save probe missing from actual EWRAM");
}
static void r15_png(struct mCore *c,const char *dir,const char *name)
{
    char path[1024];
    if(snprintf(path,sizeof(path),"%s/%s.png",dir,name)>=(int)sizeof(path))
        fail("R15 native screenshot path overflow");
    save_native_frame(c,path);
}
static void xgba_r15_run(struct mCore *c,uint32_t p,uint32_t save_probe,
                         const char *dir,const char *phase,
                         const struct XgbaGbaDevice *d,
                         const struct ResourceFile *r,int enabled)
{
    if(!c||!p||!save_probe||!dir||!phase||!r->second_id)
        fail("R15 requires actual FireRed, native mGBA and two sidecars");
    r15_proof(c,save_probe);
    if(!strcmp(phase,"write")) {
        if(!enabled||r15_read(c,save_probe,2)||
           r15_read(c,save_probe,1)==R15_SAVE_OK)
            fail("R15 first launch did not start from empty native Flash");
        r14_wait(c,120);
        r14_expect(c,p,3,0);
        r14_verify(c,p,r,0,0,0);
        r14_press(c,1u<<6,18); /* native D-pad up: real house door */
        r14_wait(c,180);
        r14_expect(c,p,4,0);
        r14_verify(c,p,r,1,13,10);
        r15_png(c,dir,"01-house-before-save");
        r14_press(c,1u<<2,3); /* SELECT invokes actual TrySavingData(SAVE_NORMAL) */
        r14_wait(c,60);
        r15_proof(c,save_probe);
        fprintf(stderr,
                "R15_SAVE_DIAG boot_status=%u boot_continue=%u requests=%u "
                "save_result=%u map=%u:%u position=%u,%u "
                "host_success=%u host_fail=%u lookups=%u reads=%u\\n",
                r15_read(c,save_probe,1),r15_read(c,save_probe,2),
                r15_read(c,save_probe,3),r15_read(c,save_probe,4),
                r15_read(c,save_probe,5),r15_read(c,save_probe,6),
                r15_read(c,save_probe,7),r15_read(c,save_probe,8),
                d->successful_reads,d->failed_reads,r->lookups,r->reads);
        if(r15_read(c,save_probe,3)!=1u||
           r15_read(c,save_probe,4)!=R15_SAVE_OK||
           r15_read(c,save_probe,5)!=4u||
           r15_read(c,save_probe,6)!=0u||
           d->failed_reads||d->successful_reads!=2u||r->reads!=2u)
            fail("R15 FireRed original sector save routine did not report success");
        r14_expect(c,p,4,0);
        r14_verify(c,p,r,1,13,10);
        r15_png(c,dir,"02-house-after-flash-save");
        printf("PASS_R15_REAL_FIRERED_FLASH_WRITE original_save=1 saved_map=4:0 native_reads=%u\n",
               d->successful_reads);
    }else if(!strcmp(phase,"continue")){
        if(!enabled||r15_read(c,save_probe,1)!=R15_SAVE_OK||
           r15_read(c,save_probe,2)!=1u)
            fail("R15 cold-boot original FireRed LoadGameSave did not succeed");
        r14_wait(c,150);
        r14_expect(c,p,4,0);
        r14_verify(c,p,r,1,13,10);
        if(d->failed_reads||d->successful_reads!=1u||r->reads!=1u)
            fail("R15 cold boot did not reacquire external house pack exactly once");
        r15_png(c,dir,"03-cold-boot-house-reloaded");
        r14_press(c,1u<<7,18);
        r14_wait(c,180);
        r14_expect(c,p,3,0);
        r14_verify(c,p,r,0,0,0);
        if(d->successful_reads!=2u)
            fail("R15 native exit did not reacquire outdoor pack");
        r15_png(c,dir,"04-after-cold-boot-pallet");
        printf("PASS_R15_REAL_FIRERED_COLD_CONTINUE native_flash_loaded=1 "
               "external_reacquire=1 maps=house_to_pallet reads=%u\n",
               d->successful_reads);
    }else if(!strcmp(phase,"corrupt")){
        if(!enabled||r15_read(c,save_probe,1)!=R15_SAVE_OK||
           r15_read(c,save_probe,2)!=1u)
            fail("R15 corrupt test must still load original valid game save");
        if(r14_u32(c,p,1)!=0xE14u||d->successful_reads!=0u||
           d->failed_reads==0u)
            fail("R15 wrong SHA resource did not refuse before external dereference");
        puts("PASS_R15_CORRUPT_PACK_REFUSED valid_flash_save=1 invalid_pack_read=0 "
             "guest_fail_closed=1");
    }else fail("R15 invalid native execution phase");
}
#endif
