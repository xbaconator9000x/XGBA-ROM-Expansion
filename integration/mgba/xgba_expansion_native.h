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


static uint32_t xgba_expansion_source_hash(const struct ResourceFile *resource,
                                            const char *prefix,
                                            uint32_t expected_bytes)
{
    uint32_t hash=2166136261u, seen=0u;
    for (unsigned i=0;i<resource->extra_count;++i) {
        const struct ExtraResourceFile *item=&resource->extra[i];
        if (strncmp(item->id,prefix,strlen(prefix)))
            continue;
        if (item->length>16384u || item->length>expected_bytes-seen)
            fail("RHH original map/tileset page exceeds bounded source");
        FILE *file=fopen(resource->path,"rb");
        if (!file || item->offset>INT64_MAX ||
            fseeko(file,(off_t)item->offset,SEEK_SET))
            fail("RHH native source page unavailable");
        for (uint64_t j=0;j<item->length;++j) {
            int byte=fgetc(file);
            if (byte==EOF) fail("RHH source page unexpectedly truncated");
            hash=(hash^(uint8_t)byte)*16777619u;
        }
        fclose(file);
        seen+=(uint32_t)item->length;
    }
    if (seen!=expected_bytes)
        fail("RHH native proof must cover complete original source asset bytes");
    return hash;
}

static void xgba_expansion_native_field_load(struct mCore *core,
           uint32_t probe, const char *target, const char *directory,
           const struct XgbaGbaDevice *device,
           const struct ResourceFile *resource, int enabled)
{
    /* Appended native witness begins after original 44-byte boot proof. */
    const uint32_t state=core->busRead32(core,probe+44u);
    const uint32_t layout=core->busRead32(core,probe+48u);
    const uint32_t used_map=core->busRead32(core,probe+52u);
    const uint32_t used_tiles=core->busRead32(core,probe+56u);
    const uint32_t actual_map=core->busRead32(core,probe+60u);
    const uint32_t actual_tiles=core->busRead32(core,probe+64u);
    const uint32_t map_bytes=core->busRead32(core,probe+68u);
    const uint32_t tile_bytes=core->busRead32(core,probe+72u);
    const uint32_t expected_layout=!strcmp(target,"emerald")?10u:481u;
    const uint32_t expected_tiles=!strcmp(target,"emerald")?16384u:20480u;
    char prefix[24];
    if (state!=3u || layout!=expected_layout ||
        !map_bytes || map_bytes>20480u || tile_bytes!=expected_tiles ||
        used_map!=(enabled?1u:0u) || used_tiles!=(enabled?1u:0u))
    {
        fprintf(stderr, "RHH_MAP_OBSERVED target=%s enabled=%d state=%u "
                "layout=%u expected_layout=%u map_used=%u tiles_used=%u "
                "map_bytes=%u tile_bytes=%u expected_tile_bytes=%u "
                "provider_reads=%u extra_pages=%u\\n",
                target,enabled,state,layout,expected_layout,used_map,
                used_tiles,map_bytes,tile_bytes,expected_tiles,
                device->successful_reads,resource->extra_count);
        fail("RHH original fieldmap and tile loading did not complete expected external/fallback path");
    }
    if (snprintf(prefix,sizeof(prefix),"rhh.m.%04x.",layout)>=(int)sizeof(prefix))
        fail("RHH map source ID format exceeds host space");
    const uint32_t expect_map=xgba_expansion_source_hash(resource,prefix,map_bytes);
    if (snprintf(prefix,sizeof(prefix),"rhh.p.%04x.",layout)>=(int)sizeof(prefix))
        fail("RHH tileset source ID format exceeds host space");
    const uint32_t expect_tiles=xgba_expansion_source_hash(resource,prefix,tile_bytes);
    if (actual_map!=expect_map)
        fail("RHH real map loader produced a different copied map grid from verified source pages");
    if (enabled && actual_tiles!=expect_tiles)
        fail("RHH real primary tileset path loaded VRAM different from verified source tiles");
    /* The smoke entrypoint loads only the map and primary tileset.
     * The manifest also contains secondary pages for gameplay, which must
     * not be counted as reads by this isolated loader. Derive the exact
     * number from the independently verified complete asset lengths. */
    const uint32_t expected_reads=1u+(map_bytes+16383u)/16384u+
                                      (tile_bytes+16383u)/16384u;
    if ((enabled && (device->successful_reads!=expected_reads ||
                     resource->reads!=expected_reads ||
                     device->failed_reads)) ||
        (!enabled && (device->successful_reads || resource->reads ||
                      device->failed_reads)))
        fail("RHH native original map or multi-page tile source reads do not match");
    /* Preserve LCD as genuine native engine continuation, NOT proof that the
     * smoke-loaded tiles are rendered as a playable map on the title screen. */
    core->setKeys(core,0u);
    for (unsigned i=0;i<240u;++i)
        core->runFrame(core);
    char path[1024];
    if (snprintf(path,sizeof(path),"%s/expansion-%s-%s.png",
                 directory,target,enabled?"enabled":"disabled") >= (int)sizeof(path))
        fail("RHH map native screenshot path exceeds limit");
    const void *pixels=NULL;
    size_t stride=0u;
    core->getPixels(core,&pixels,&stride);
    if (!pixels || stride<240u)
        fail("RHH source map native LCD framebuffer unattached");
    save_native_frame(core,path);
    printf("PASS_XGBA_RHH_NATIVE_REAL_FIELD_LOADER "
           "target=%s enabled=%d layout=%u map_bytes=%u tiles_bytes=%u "
           "map_source_used=%u tile_source_used=%u provider_reads=%u "
           "map_source_hash=%08x tiles_source_hash=%08x real_lcd=%s\n",
           target,enabled,layout,map_bytes,tile_bytes,used_map,used_tiles,
           device->successful_reads,actual_map,actual_tiles,path);
}

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
    if (resource->extra_count) {
        xgba_expansion_native_field_load(core,probe,target,directory,
                                         device,resource,enabled);
        return;
    }

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
