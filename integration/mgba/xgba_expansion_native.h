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


enum {
    RHH_TRAINER_COUNT = 140,
    RHH_TRAINER_BYTES = 144,
    RHH_TRAINER_LAST_ID = 148,
    RHH_TRAINER_HASH = 152,
    RHH_TRAINER_GENERATION = 156,
    RHH_TRAINER_RESIDENT = 160,
    RHH_TRAINER_ATTEMPTS = 164,
    RHH_TRAINER_ATTEMPT_ID = 168,
    RHH_TRAINER_PROOF_END = 356,
    RHH_PAGE_RESIDENT = 40,
    RHH_BATTLE_FLOW = 172,
    RHH_BATTLE_OPPONENT = 176,
    RHH_BATTLE_MAIN_FRAMES = 180,
    RHH_BATTLE_SPRITE_PIC = 184,
    RHH_BATTLE_SPRITE_ARRIVED = 188,
    RHH_BATTLE_SPRITE_VISIBLE = 192,
    RHH_BATTLE_FALLBACK_COUNT = 196,
    RHH_BATTLE_FALLBACK_HASH = 200,
    RHH_BATTLE_FALLBACK_ID = 204,
    RHH_BATTLE_FALLBACK_BYTES = 208
};

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

/* Hash [start,start+length) of one exact source-owned extra resource. */
static uint32_t xgba_expansion_resource_slice_hash(
        const struct ResourceFile *resource, const char *id,
        uint32_t expected_bytes, uint32_t start, uint32_t length)
{
    for (unsigned i=0;i<resource->extra_count;++i) {
        const struct ExtraResourceFile *item=&resource->extra[i];
        if (strcmp(item->id,id))
            continue;
        if (item->length!=expected_bytes || start>expected_bytes ||
            length>expected_bytes-start || item->offset>INT64_MAX-start)
            fail("RHH Pokemon source page has unexpected size");
        FILE *file=fopen(resource->path,"rb");
        if (!file || fseeko(file,(off_t)(item->offset+start),SEEK_SET))
            fail("RHH Pokemon source page unavailable");
        uint32_t hash=2166136261u;
        for (uint32_t j=0;j<length;++j) {
            int byte=fgetc(file);
            if (byte==EOF) fail("RHH Pokemon source page truncated");
            hash=(hash^(uint8_t)byte)*16777619u;
        }
        fclose(file);
        return hash;
    }
    fail("RHH Pokemon source page not declared by the private manifest");
    return 0u;
}

static uint32_t xgba_expansion_vram_hash(struct mCore *core, uint32_t tile)
{
    uint32_t hash=2166136261u;
    for (uint32_t i=0;i<2048u;++i)
        hash=(hash^core->busRead8(core,0x06010000u+tile*32u+i))*16777619u;
    return hash;
}

/* Native acceptance for original Pokemon battle sprites. Runs after the
 * trainer proof in the same battle: waits for the guest's own latches
 * (buffer == VRAM == original palette), then asserts the front and back
 * witnesses against provider-owned source hashes and the real LCD. */
static void xgba_expansion_native_pokemon_battle(struct mCore *core,
        uint32_t probe, const char *target, const char *directory,
        const struct XgbaGbaDevice *device,
        const struct ResourceFile *resource, int enabled)
{
    /* Word indices inside each 18-field side block of the guest proof. */
    enum { F=212, B=284, ATT=0, ATTS=1, TR=2, TRS=3, TRB=4, TRH=5, TRG=6,
           TRR=7, FBC=8, FBS=9, FBB=10, FBH=11, OK=12, SPS=13, TILE=14,
           PAL=15, FRAME=16, LIVE=17 };
    const uint32_t base[2]={F,B};
    uint32_t v[2][18];
    for (unsigned frames=0;frames<4000u;++frames) {
        if (core->busRead32(core,probe+F+4u*OK) &&
            core->busRead32(core,probe+B+4u*OK))
            break;
        /* Intro text auto-advances; tap A only if it unexpectedly stalls. */
        core->setKeys(core,(frames>1500u && (frames%60u)<2u)?1u:0u);
        core->runFrame(core);
    }
    core->setKeys(core,0u);
    if (!core->busRead32(core,probe+F+4u*OK) ||
        !core->busRead32(core,probe+B+4u*OK))
        fail("RHH guest never latched original Pokemon battle sprites in VRAM");
    for (unsigned i=0;i<8u;++i)
        core->runFrame(core);
    for (unsigned side=0;side<2u;++side)
        for (unsigned i=0;i<18u;++i)
            v[side][i]=core->busRead32(core,probe+base[side]+4u*i);
    if (core->busRead32(core,probe+RHH_BATTLE_FLOW)!=2u ||
        !v[0][LIVE] || !v[1][LIVE])
        fail("RHH Pokemon battle sprites not on screen at LCD capture");
    /* Original lead species are Bulbasaur (player) and Geodude (opponent). */
    if (v[0][ATTS]!=74u || v[1][ATTS]!=1u || v[0][SPS]!=74u ||
        v[1][SPS]!=1u || v[0][ATT]<1u || v[1][ATT]<1u)
        fail("RHH Pokemon battle did not load the original Geodude/Bulbasaur sprites");
    if (core->busRead32(core,probe+RHH_PAGE_RESIDENT)!=0u)
        fail("RHH Pokemon battle left the external page lease resident");
    if (device->failed_reads)
        fail("RHH Pokemon battle provider reported a failed read");
    if (!v[0][PAL] || !v[1][PAL] || !v[0][FRAME] || v[0][FRAME]>2u ||
        v[1][FRAME]!=1u)
        fail("RHH Pokemon battle palette or VRAM witness invalid");
    const char *ids[2]={"rhh.mon.f.004a","rhh.mon.b.0001"};
    const uint32_t sizes[2]={4096u,2048u};
    uint32_t source_hash[2];
    for (unsigned side=0;side<2u;++side)
        source_hash[side]=xgba_expansion_resource_slice_hash(
            resource,ids[side],sizes[side],0u,sizes[side]);
    /* Host-side live VRAM check: tiles on the LCD equal an original frame. */
    uint32_t vram=xgba_expansion_vram_hash(core,v[0][TILE]);
    if (vram!=xgba_expansion_resource_slice_hash(resource,ids[0],4096u,0u,2048u) &&
        vram!=xgba_expansion_resource_slice_hash(resource,ids[0],4096u,2048u,2048u))
        fail("RHH opponent Pokemon VRAM tiles differ from the original source");
    vram=xgba_expansion_vram_hash(core,v[1][TILE]);
    if (vram!=xgba_expansion_resource_slice_hash(resource,ids[1],2048u,0u,2048u))
        fail("RHH player Pokemon VRAM tiles differ from the original source");
    if (enabled) {
        for (unsigned side=0;side<2u;++side) {
            if (v[side][TR]<1u || v[side][TR]>v[side][ATT] ||
                v[side][TRB]!=v[side][TR]*sizes[side] ||
                v[side][TRS]!=v[side][ATTS] || v[side][TRR]!=0u ||
                v[side][TRG]<1u || v[side][FBC])
                fail("RHH Pokemon battle external transfer witness invalid");
            if (v[side][TRH]!=source_hash[side])
                fail("RHH Pokemon battle sprite differs from verified source page");
        }
        if (device->successful_reads<=v[0][TR]+v[1][TR] ||
            resource->reads<=v[0][TR]+v[1][TR])
            fail("RHH Pokemon battle provider reads do not cover transfers");
    } else {
        if (device->successful_reads || resource->reads || resource->lookups)
            fail("RHH disabled Pokemon battle used the external provider");
        for (unsigned side=0;side<2u;++side) {
            if (v[side][TR] || v[side][TRB] || v[side][TRH])
                fail("RHH disabled Pokemon battle recorded an external transfer");
            if (v[side][FBC]<1u || v[side][FBS]!=v[side][ATTS] ||
                v[side][FBB]!=sizes[side] || v[side][FBH]!=source_hash[side])
                fail("RHH original Pokemon decompressor differs from verified source sprite");
        }
    }
    char path[1024];
    if (snprintf(path,sizeof(path),"%s/rhh-%s-pokemon-battle-%s.png",directory,
                 target,enabled?"external":"fallback")>=(int)sizeof(path))
        fail("RHH Pokemon battle screenshot path exceeds limit");
    const void *pixels=NULL;
    size_t stride=0u;
    core->getPixels(core,&pixels,&stride);
    if (!pixels || stride<240u)
        fail("RHH Pokemon battle LCD framebuffer unattached");
    save_native_frame(core,path);
    printf("PASS_XGBA_RHH_NATIVE_POKEMON_BATTLE target=%s enabled=%d "
           "front_species=%u back_species=%u front_transfers=%u "
           "back_transfers=%u front_hash=%08x back_hash=%08x "
           "front_source_hash=%08x back_source_hash=%08x "
           "front_fallbacks=%u back_fallbacks=%u front_palette=%08x "
           "back_palette=%08x provider_reads=%u lease_released=1 real_lcd=%s\n",
           target,enabled,v[0][SPS],v[1][SPS],v[0][TR],v[1][TR],
           enabled?v[0][TRH]:v[0][FBH],enabled?v[1][TRH]:v[1][FBH],
           source_hash[0],source_hash[1],v[0][FBC],v[1][FBC],
           v[0][PAL],v[1][PAL],device->successful_reads,path);
}

/* Native acceptance for the original RHH trainer battle graphics loader.
 * The guest alone reaches DecompressTrainerFrontPic; the host only observes
 * guest witnesses, provider counters and the real LCD. */
static void xgba_expansion_native_trainer_battle(struct mCore *core,
        uint32_t probe, const char *target, const char *directory,
        const struct XgbaGbaDevice *device,
        const struct ResourceFile *resource, int enabled)
{
    if (!target || !directory || probe<0x02000000u ||
        probe>0x02040000u-RHH_TRAINER_PROOF_END || (probe&3u))
        fail("RHH trainer battle proof must be aligned actual game EWRAM");
    /* The guest alone enters the original battle; wait (bounded by the
     * launcher frame budget) until its own witnesses report the real
     * trainer sprite on screen, then continue a few frames and re-check. */
    if (core->busRead32(core,probe+RHH_BATTLE_FLOW)!=2u ||
        !core->busRead32(core,probe+RHH_BATTLE_SPRITE_ARRIVED) ||
        !core->busRead32(core,probe+RHH_BATTLE_SPRITE_VISIBLE))
        fail("RHH guest never rendered an original trainer battle opponent sprite");
    core->setKeys(core,0u);
    for (unsigned i=0;i<8u;++i)
        core->runFrame(core);
    if (core->busRead32(core,probe+RHH_BATTLE_FLOW)!=2u ||
        !core->busRead32(core,probe+RHH_BATTLE_SPRITE_VISIBLE))
        fail("RHH trainer battle opponent sprite not on screen at LCD capture");
    const uint32_t attempts=core->busRead32(core,probe+RHH_TRAINER_ATTEMPTS);
    const uint32_t attempt_id=core->busRead32(core,probe+RHH_TRAINER_ATTEMPT_ID);
    const uint32_t count=core->busRead32(core,probe+RHH_TRAINER_COUNT);
    const uint32_t bytes=core->busRead32(core,probe+RHH_TRAINER_BYTES);
    const uint32_t last_id=core->busRead32(core,probe+RHH_TRAINER_LAST_ID);
    const uint32_t hash=core->busRead32(core,probe+RHH_TRAINER_HASH);
    const uint32_t generation=core->busRead32(core,probe+RHH_TRAINER_GENERATION);
    const uint32_t resident=core->busRead32(core,probe+RHH_TRAINER_RESIDENT);
    const uint32_t fallback_count=core->busRead32(core,probe+RHH_BATTLE_FALLBACK_COUNT);
    const uint32_t fallback_hash=core->busRead32(core,probe+RHH_BATTLE_FALLBACK_HASH);
    const uint32_t fallback_id=core->busRead32(core,probe+RHH_BATTLE_FALLBACK_ID);
    const uint32_t fallback_bytes=core->busRead32(core,probe+RHH_BATTLE_FALLBACK_BYTES);
    const uint32_t sprite_pic=core->busRead32(core,probe+RHH_BATTLE_SPRITE_PIC);
    const uint32_t opponent=core->busRead32(core,probe+RHH_BATTLE_OPPONENT);
    const uint32_t main_frames=core->busRead32(core,probe+RHH_BATTLE_MAIN_FRAMES);
    /* The pinned engine selects the version-specific original Hiker artwork. */
    const uint32_t expected_pic = strcmp(target,"emerald")==0 ? 11u : 105u;
    fprintf(stderr,"RHH battle witnesses: opponent=%u attempt=%u sprite=%u count=%u bytes=%u last=%u fallback=%u resident=%u generation=%u\n", opponent,attempt_id,sprite_pic,count,bytes,last_id,fallback_count,resident,generation);
    const uint32_t expected_opponent = strcmp(target,"emerald")==0 ? 1u : 87u;
    if (opponent!=expected_opponent || main_frames<1u || attempts<1u || attempt_id!=expected_pic ||
        sprite_pic!=expected_pic)
        fail("RHH trainer battle did not draw the original Hiker opponent");
    if (core->busRead32(core,probe+RHH_PAGE_RESIDENT)!=0u)
        fail("RHH trainer battle left the external page lease resident");
    if (device->failed_reads)
        fail("RHH trainer battle provider reported a failed read");
    char id[24];
    if (snprintf(id,sizeof(id),"rhh.trainer.%04x",attempt_id)>=(int)sizeof(id))
        fail("RHH trainer source ID format exceeds host space");
    const uint32_t source_hash=xgba_expansion_source_hash(resource,id,2048u);
    if (enabled) {
        if (count<1u || count>attempts || bytes!=count*2048u || last_id!=expected_pic ||
            resident!=0u || generation<1u || fallback_count)
            fail("RHH trainer battle external transfer witness invalid");
        if (hash!=source_hash)
            fail("RHH trainer battle sprite differs from verified source page");
        if (device->successful_reads<=count || resource->reads<=count)
            fail("RHH trainer battle provider reads do not cover transfers");
    } else {
        if (count || bytes || hash || last_id || device->successful_reads ||
            resource->reads || resource->lookups)
            fail("RHH disabled trainer battle used the external provider");
        if (fallback_count<1u || fallback_id!=expected_pic || fallback_bytes!=2048u ||
            fallback_hash!=source_hash)
            fail("RHH original fallback decompressor differs from verified source sprite");
    }
    char path[1024];
    if (snprintf(path,sizeof(path),"%s/rhh-%s-trainer-battle-%s.png",directory,
                 target,enabled?"external":"fallback")>=(int)sizeof(path))
        fail("RHH trainer battle screenshot path exceeds limit");
    const void *pixels=NULL;
    size_t stride=0u;
    core->getPixels(core,&pixels,&stride);
    if (!pixels || stride<240u)
        fail("RHH trainer battle LCD framebuffer unattached");
    save_native_frame(core,path);
    printf("PASS_XGBA_RHH_NATIVE_TRAINER_BATTLE target=%s enabled=%d "
           "attempts=%u attempt_id=%u transfers=%u trainer_bytes=%u "
           "trainer_id=%u trainer_hash=%08x source_hash=%08x "
           "fallback_decodes=%u battle_frames=%u provider_reads=%u "
           "lease_released=1 real_lcd=%s\n",
           target,enabled,attempts,attempt_id,count,bytes,last_id,
           enabled?hash:fallback_hash,source_hash,fallback_count,main_frames,
           device->successful_reads,path);
    xgba_expansion_native_pokemon_battle(core,probe,target,directory,device,
                                         resource,enabled);
}
#endif
