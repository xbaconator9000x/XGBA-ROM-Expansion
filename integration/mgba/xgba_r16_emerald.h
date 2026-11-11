/* R16: reuse native XGBA/mGBA provider for source-built pret/pokeemerald.
 * This mode validates guest-issued CPU writes/reads; not a host-triggered fetch.
 * Source-backed original Emerald title continues running after XGBA fetch.
 */
#ifndef XGBA_R16_EMERALD_NATIVE_H
#define XGBA_R16_EMERALD_NATIVE_H
#define XGBA_R16_EMERALD_ENGINE 0x454D5244u
static void xgba_r16_emerald_run(struct mCore *core, uint32_t probe,
        const char *directory, const struct XgbaGbaDevice *device,
        const struct ResourceFile *resource,int enabled)
{
    if (!probe || probe < 0x02000000u || probe+24u >= 0x02040000u)
        fail("R16 invalid actual Emerald EWRAM probe symbol");
    if (core->busRead32(core,probe) != XGBA_R7_MMIO_MAGIC ||
        core->busRead32(core,probe+4u) != 3u ||
        core->busRead32(core,probe+20u) != XGBA_R16_EMERALD_ENGINE)
        fail("R16 original Emerald source boot did not issue XGBA MMIO request");
    unsigned valid=core->busRead32(core,probe+8u);
    unsigned received=core->busRead32(core,probe+12u);
    uint32_t dest=core->busRead32(core,probe+16u);
    if ((enabled && (valid!=1u || received!=64u ||
                     device->successful_reads!=1u || device->failed_reads ||
                     resource->reads!=1u || resource->lookups!=1u)) ||
        (!enabled && (valid || received || device->successful_reads ||
                      device->failed_reads || resource->reads || resource->lookups)))
        fail("R16 source-built Emerald guest/provider handshake mismatch");
    if(dest<0x02000000u || dest+64u>0x02040000u || (dest&3u))
        fail("R16 Emerald destination is not an aligned real GBA EWRAM buffer");
    uint8_t expected[64];
    memset(expected,0xA5,sizeof(expected));
    if(enabled) {
        FILE *fp=fopen(resource->path,"rb");
        if (!fp || fseeko(fp,(off_t)resource->offset,SEEK_SET) ||
            fread(expected,1,64,fp)!=64)
            fail("R16 provider source payload unavailable");
        fclose(fp);
    }
    for(unsigned i=0;i<64u;++i)
        if(core->busRead8(core,dest+i)!=expected[i])
            fail("R16 actual decompiled Emerald EWRAM differs from source bytes");
    /* The original game keeps executing its own unmodified main loop. */
    for(unsigned i=0;i<180u;++i)
        core->runFrame(core);
    char path[1024];
    if(snprintf(path,sizeof(path),"%s/emerald-boot-%s.png",
                directory,enabled?"enabled":"disabled") >= (int)sizeof(path))
        fail("R16 native LCD screenshot path too long");
    save_native_frame(core,path);
    printf("PASS_R16_SOURCE_BUILT_POKEEMERALD_XGBA_MMIO enabled=%d "
           "requests=%u bytes=%u zero_disabled_reads=%d "
           "original_emerald_main_frames=180 image=%s\n",
           enabled,device->successful_reads,received,
           !enabled?resource->reads==0:1,path);
}
#endif
