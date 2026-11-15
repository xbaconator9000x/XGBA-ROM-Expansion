/*
 * R96 source-built RHH real-overworld acceptance on native patched mGBA.
 * Exercises genuine NewGameInitData/CB2_Overworld, real D-pad and LCD frames.
 * No host-side writes to EWRAM, save blocks, graphics or map coordinates.
 * Probe is appended after the previous 76-byte map-smoke witness.
 */
#ifndef XGBA_EXPANSION_OVERWORLD_NATIVE_H
#define XGBA_EXPANSION_OVERWORLD_NATIVE_H

enum {
    RHH_LIVE_STATE = 76,
    RHH_LIVE_FRAMES = 80,
    RHH_LIVE_LAYOUT = 84,
    RHH_LIVE_FIRST_LAYOUT = 88,
    RHH_LIVE_X = 92,
    RHH_LIVE_Y = 96,
    RHH_LIVE_MOVEMENTS = 100,
    RHH_LIVE_TRANSITIONS = 104,
    RHH_LIVE_MAP_READS = 108,
    RHH_LIVE_PRIMARY_READS = 112,
    RHH_LIVE_SECONDARY_READS = 116,
    RHH_LIVE_BYTES = 120,
    RHH_LIVE_STAGE = 124
};
static void rhh_overworld_screen(struct mCore *core, const char *dir,
                                 const char *target, const char *phase,
                                 int enabled)
{
    char path[1024];
    if (snprintf(path, sizeof(path), "%s/rhh-%s-%s-%s.png", dir, target,
                 enabled ? "external" : "fallback", phase) >= (int)sizeof(path))
        fail("RHH overworld evidence screenshot pathname overflow");
    const void *pixels = NULL;
    size_t stride = 0;
    core->getPixels(core, &pixels, &stride);
    if (!pixels || stride < 240u)
        fail("RHH actual gameplay LCD buffer unavailable");
    save_native_frame(core, path);
}

static void xgba_expansion_native_overworld(struct mCore *core,
          uint32_t probe, const char *target, const char *directory,
          const struct XgbaGbaDevice *device,
          const struct ResourceFile *resource, int enabled)
{
    const uint32_t start_id = !strcmp(target,"emerald") ? 10u : 481u;
    const uint32_t next_id = !strcmp(target,"emerald") ? 17u : 492u;
    if (core->busRead32(core,probe+RHH_LIVE_STATE)!=1u ||
        core->busRead32(core,probe+RHH_LIVE_LAYOUT)!=start_id ||
        core->busRead32(core,probe+RHH_LIVE_FRAMES)<12u)
    {
        fprintf(stderr, "RHH_WORLD_BOOT_DIAG target=%s enabled=%d "
            "boot_state=%u stage=%u live_state=%u live_frames=%u "
            "first_layout=%u current_layout=%u x=%u y=%u source_maps=%u "
            "source_primary=%u guest_reads=%u guest_rejections=%u\\n",
            target, enabled,
            core->busRead32(core,probe+8u),
            core->busRead32(core,probe+RHH_LIVE_STAGE),
            core->busRead32(core,probe+RHH_LIVE_STATE),
            core->busRead32(core,probe+RHH_LIVE_FRAMES),
            core->busRead32(core,probe+RHH_LIVE_FIRST_LAYOUT),
            core->busRead32(core,probe+RHH_LIVE_LAYOUT),
            core->busRead32(core,probe+RHH_LIVE_X),
            core->busRead32(core,probe+RHH_LIVE_Y),
            core->busRead32(core,probe+RHH_LIVE_MAP_READS),
            core->busRead32(core,probe+RHH_LIVE_PRIMARY_READS),
            device->successful_reads,device->failed_reads);
        fail("RHH playable new-game callback never entered original town overworld");
    }
    uint32_t x0 = core->busRead32(core,probe+RHH_LIVE_X);
    uint32_t y0 = core->busRead32(core,probe+RHH_LIVE_Y);
    if (enabled && (!core->busRead32(core,probe+RHH_LIVE_MAP_READS) ||
                    !core->busRead32(core,probe+RHH_LIVE_PRIMARY_READS)))
        fail("RHH real overworld never fetched external original town map/tileset");
    if (!enabled && (device->successful_reads || resource->reads))
        fail("RHH disabled-provider overworld read external assets");
    rhh_overworld_screen(core,directory,target,"00-initial-real-town",enabled);
    /* Real GBA physical D-pad: right=bit4, up=bit6. No memory injection. */
    core->setKeys(core,1u<<4);
    for(unsigned frame=0;frame<30u;frame++) core->runFrame(core);
    core->setKeys(core,0u);
    for(unsigned frame=0;frame<16u;frame++) core->runFrame(core);
    uint32_t moves=core->busRead32(core,probe+RHH_LIVE_MOVEMENTS);
    uint32_t x1=core->busRead32(core,probe+RHH_LIVE_X);
    uint32_t y1=core->busRead32(core,probe+RHH_LIVE_Y);
    fprintf(stderr,
        "RHH_REAL_OVERWORLD_DIAG target=%s enabled=%d start=(%u,%u) after-right=(%u,%u)"
        " movements=%u map=%u frames=%u reads=%u\n",
        target,enabled,x0,y0,x1,y1,moves,
        core->busRead32(core,probe+RHH_LIVE_LAYOUT),
        core->busRead32(core,probe+RHH_LIVE_FRAMES),
        device->successful_reads);
    if (!moves || (x0==x1 && y0==y1))
        fail("RHH native physical D-pad did not move actual game player");
    rhh_overworld_screen(core,directory,target,"01-dpad-movement",enabled);
    /* Continue north across original town/route connection. The game
     * must trigger any scripts/collision/warp itself. Do not spoof position. */
    core->setKeys(core,1u<<6);
    for(unsigned frame=0;frame<220u;frame++) core->runFrame(core);
    core->setKeys(core,0u);
    for(unsigned frame=0;frame<60u;frame++) core->runFrame(core);
    uint32_t final_map=core->busRead32(core,probe+RHH_LIVE_LAYOUT);
    uint32_t transitions=core->busRead32(core,probe+RHH_LIVE_TRANSITIONS);
    uint32_t source_maps=core->busRead32(core,probe+RHH_LIVE_MAP_READS);
    uint32_t source_primary=core->busRead32(core,probe+RHH_LIVE_PRIMARY_READS);
    rhh_overworld_screen(core,directory,target,"02-after-north",enabled);
    fprintf(stderr,"RHH_ROUTE_ATTEMPT target=%s enabled=%d initial=%u intended=%u"
            " actual=%u transitions=%u last=(%u,%u) movements=%u source_maps=%u"
            " source_primary=%u provider_reads=%u\n",
            target,enabled,start_id,next_id,final_map,transitions,
            core->busRead32(core,probe+RHH_LIVE_X),
            core->busRead32(core,probe+RHH_LIVE_Y),
            core->busRead32(core,probe+RHH_LIVE_MOVEMENTS),
            source_maps,source_primary,device->successful_reads);
    if (final_map!=next_id || transitions<1u)
        fail("RHH playable town-to-route native map transition unverified");
    if ((enabled && (source_maps<2u || source_primary<2u ||
                     device->successful_reads<5u || device->failed_reads)) ||
        (!enabled && (source_maps || source_primary ||
                      device->successful_reads || device->failed_reads)))
        fail("RHH original town/route MMIO lifecycle disagrees with real guest game");
    printf("PASS_RHH_REAL_OVERWORLD_NATIVE target=%s enabled=%d"
           " initial_layout=%u route_layout=%u physical_dpad_moves=%u"
           " original_map_transitions=%u original_source_maps=%u"
           " source_primary_sets=%u verified_host_page_reads=%u\n",
           target,enabled,start_id,final_map,
           core->busRead32(core,probe+RHH_LIVE_MOVEMENTS),
           transitions,source_maps,source_primary,device->successful_reads);
}
#endif
