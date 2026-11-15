/*
 * RHH pokeemerald-expansion: genuine native mGBA source-built game probe.
 *
 * This verifies the REAL expanding game CPU issued an XGBA guest MMIO fetch
 * into native EWRAM, using the existing shared provider. NOT merely a ROM
 * compile or fixture-generated visual and NOT map/Flash acceptance.
 * Included only in xgba_mgba_headless.c after save_native_frame().
 */
#ifndef XGBA_EXPANSION_NATIVE_H
#define XGBA_EXPANSION_NATIVE_H

static void xgba_expansion_native_run(struct mCore *core, uint32_t probe,
        const char *target, const char *directory,
        const struct XgbaGbaDevice *device,
        const struct ResourceFile *resource, int enabled)
{
    if (!target || !directory || !probe ||
        probe < 0x02000000u || probe > 0x02040000u-44u ||
        (probe & 3u))
        fail("RHH expansion proof must be aligned actual game EWRAM");

    uint32_t marker=0;
    const char *required_id=NULL;
    if (!strcmp(target,"emerald")) {
        marker=0x454D5244u;
        required_id="expansion.emerald.bridge";
    } else if (!strcmp(target,"firered")) {
        marker=0x46525244u;
        required_id="expansion.firered.bridge";
    } else if (!strcmp(target,"leafgreen")) {
        marker=0x4C464752u;
        required_id="expansion.leafgreen.bridge";
    } else {
        fail("RHH unsupported game target requested for native proof");
    }
    if (strcmp(resource->id,required_id) || resource->length != 16384u)
        fail("RHH native provider resource does not match actual game target");

    const uint32_t magic=core->busRead32(core,probe);
    const uint32_t variant=core->busRead32(core,probe+4u);
    const uint32_t state=core->busRead32(core,probe+8u);
    const uint32_t used=core->busRead32(core,probe+12u);
    const uint32_t valid=core->busRead32(core,probe+16u);
    const uint32_t destination=core->busRead32(core,probe+20u);
    if (magic != XGBA_R7_MMIO_MAGIC || variant != marker || state != 3u)
        fail("RHH engine boot did not complete its actual guest MMIO request");
    if (destination < 0x02000000u || destination > 0x02040000u-16384u ||
        (destination & 3u))
        fail("RHH external resource destination outside physical 256KiB EWRAM");
    if ((enabled && (used!=16384u || valid!=1u ||
        device->successful_reads!=1u || device->failed_reads ||
        resource->reads!=1u || resource->lookups!=1u)) ||
        (!enabled && (used || valid || device->successful_reads ||
        device->failed_reads || resource->reads || resource->lookups)))
        fail("RHH guest MMIO result differs from provider's verified read count");

    if (core->busRead32(core,probe+28u)!=16384u ||
        core->busRead32(core,probe+32u)!=0x18500u ||
        core->busRead32(core,probe+36u)<1u ||
        core->busRead32(core,probe+40u)!=(enabled?16384u:0u))
        fail("RHH expansion page ownership/heap capacity/lifetime invalid");

    uint8_t expected[16384];
    memset(expected,0xA5,sizeof(expected));
    if (enabled) {
        FILE *file=fopen(resource->path,"rb");
        if (!file || resource->offset > INT64_MAX ||
            fseeko(file,(off_t)resource->offset,SEEK_SET) ||
            fread(expected,1,sizeof(expected),file)!=sizeof(expected))
            fail("RHH provider payload cannot be independently verified");
        fclose(file);
    }
    for (unsigned i=0;i<16384u;++i)
        if (core->busRead8(core,destination+i)!=expected[i])
            fail("Actual expanded game EWRAM does not match external source bytes");

    core->setKeys(core,0u);
    for(unsigned i=0;i<650u;++i)
        core->runFrame(core);
    const uint32_t ticks=core->busRead32(core,probe+24u);
    /* The expanded framework runs its ordinary loop after fetch. Verify
     * its allocator, decompression and graphics lifecycle did NOT overwrite
     * the resident 16KiB page during that real engine activity. */
    for (unsigned i=0;i<16384u;++i)
        if (core->busRead8(core,destination+i)!=expected[i])
            fail("RHH original engine overwrote protected XGBA page after gameplay frames");
    if(ticks<100u)
        fail("RHH expanded game main loop did not continue after guest fetch");

    char path[1024];
    if (snprintf(path,sizeof(path),"%s/expansion-%s-%s.png",
                 directory,target,enabled?"enabled":"disabled") >= (int)sizeof(path))
        fail("RHH native LCD screenshot path too long");
    /* A missing render buffer must fail safely instead of crashing the host.
     * This is a REAL native mGBA LCD capture, not a substituted image. */
    const void *pixels=NULL;
    size_t stride=0u;
    core->getPixels(core,&pixels,&stride);
    if (!pixels || stride < 240u)
        fail("RHH native mGBA framebuffer not attached");
    save_native_frame(core,path);
    printf("PASS_XGBA_RHH_EXPANSION_NATIVE_GUEST_MMIO "
           "target=%s enabled=%d requests=%u bytes=%u "
           "continued_game_ticks=%u page_intact_after_frames=1 "
           "zero_disabled_reads=%d lcd=%s\n",
           target,enabled,device->successful_reads,used,ticks,
           !enabled?resource->reads==0:1,path);
}
#endif
