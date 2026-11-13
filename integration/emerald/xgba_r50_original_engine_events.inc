/* R50: native original Emerald map-header / MapEvents bridge.
 * This adapter does NOT synthesize maps, dialogue, Fly or NPC encounters.
 * Foreign worlds activate ONLY after a separately verified ORIGINAL terrain,
 * palette, sprite mapping and collision layout has been installed. Until then
 * Emerald uses its usual engine path; no false foreign-world proof is emitted.
 */
#ifndef XGBA_R50_ENGINE_EVENTS
#error R50 source events must be explicitly enabled
#endif
#ifndef XGBA_R48_ORIGINAL_NPC_BRIDGE
#error R50 depends on the actual R48 NPC A-button and Fly-in hook
#endif
#include "__XGBA_R50_ENGINE_HEADER__"
#include <stdint.h>

#define XGBA_R50_BRIDGE_MAGIC 0x52353045u
struct XgbaR50BridgeProof {
    volatile u32 magic,verified_original_headers,real_guest_fetches;
    volatile u32 rejected,active_source_key,active_npcs,original_warps;
    volatile u32 original_map_installed,foreign_overworld_loaded;
};
EWRAM_DATA volatile struct XgbaR50BridgeProof gXgbaR50BridgeProof={0};
/* R49 pages are ephemeral; actual Emerald events use a deep-copied, aligned
 * source event array, not pointers into a cache about to be evicted. */
static EWRAM_DATA u8 sXgbaR50ReaderScratch[XGBA_R49_PAGE_BYTES]={0};
static EWRAM_DATA struct XgbaR50EngineEvents sXgbaR50OriginalEvents={0};
static EWRAM_DATA struct MapEvents sXgbaR50LiveEvents={0};
static EWRAM_DATA struct MapHeader sXgbaR50LiveHeader={0};
static EWRAM_DATA struct MapLayout sXgbaR50LiveLayout={0};
static EWRAM_DATA bool8 sXgbaR50Ready=FALSE;
static EWRAM_DATA u8 sXgbaR50World=255u,sXgbaR50Group=255u,sXgbaR50Number=255u;
/* End is a REAL native Emerald end opcode, never an invented conversation.
 * A-button resolver must replace this with a SHA-verified original script
 * before a foreign NPC is considered to have been spoken to. */
static const u8 sXgbaR50QuarantinedScript[4] __attribute__((aligned(4)))={0x02,0,0,0};

static int XgbaR50FetchOriginalPage(void *context,const char *id,
                                    uint8_t *target,uint16_t bytes)
{
    u32 read;
    (void)context;
    read=XgbaGuestFetch(id,target,bytes);
    if(read!=bytes){
        ++gXgbaR50BridgeProof.rejected;
        return 0;
    }
    ++gXgbaR50BridgeProof.real_guest_fetches;
    return 1;
}
/* Required caller is the authentic source graphics/terrain installer.
 * It must have verified the actual original map metatile grids, collisions,
 * palette/tileset and every source graphics ID before registering this map.
 * No test-only source ID switch or source-named label can satisfy this API. */
bool8 XgbaR50InstallOriginalMapEvents(
    u8 world,u8 group,u8 number,const struct MapLayout *verified_original_layout,
    XgbaR50ResolveSprite verified_graphics_slot,void *graphics_context,
    bool8 verified_original_assets)
{
    struct XgbaR49Reader reader={0};
    struct MapEvents events={0};
    struct MapHeader header;
    const u8 *packed;
    u32 key;
    if(!verified_original_assets || !verified_original_layout ||
       !verified_original_layout->map ||
       !verified_original_layout->primaryTileset ||
       !verified_original_layout->secondaryTileset ||
       !verified_graphics_slot || world>=3u ||
       (world!=0u && sXgbaR48PendingFlyWorld!=world) ||
       verified_original_layout->width<=0 ||
       verified_original_layout->height<=0 ||
       verified_original_layout->width>255 ||
       verified_original_layout->height>255){
        ++gXgbaR50BridgeProof.rejected;
        return FALSE;
    }
    /* Do not mutate an already-live map header while the original Emerald
     * object engine is using its event pointers. Only stage before a warp. */
    if(sXgbaR50Ready){
        ++gXgbaR50BridgeProof.rejected;
        return FALSE;
    }
    key=((u32)world<<16)|((u32)group<<8)|number;
    reader.fetch=XgbaR50FetchOriginalPage;
    reader.scratch=sXgbaR50ReaderScratch;
    reader.indexed_maps=XGBA_R49_ALL_MAPS;
    reader.cached_index_page=XGBA_R49_INVALID_PAGE;
    if(!XgbaR50StageEvents(&reader,key,
          (u16)verified_original_layout->width,
          (u16)verified_original_layout->height,
          verified_graphics_slot,graphics_context,
          (u32)(uintptr_t)sXgbaR50QuarantinedScript,
          &sXgbaR50OriginalEvents)){
        ++gXgbaR50BridgeProof.rejected;
        return FALSE;
    }
    /* The source index never overlaps Emerald's native map header by number:
     * 0:9 in Emerald and 0:9 in Rocket are independent source keys. */
    header=*gMapGroups[group][number];
    packed=XgbaR50EventBytes(&sXgbaR50OriginalEvents);
    events.objectEventCount=sXgbaR50OriginalEvents.object_count;
    events.warpCount=0u; /* source-aware warp execution still required */
    events.coordEventCount=0u;
    events.bgEventCount=0u;
    events.objectEvents=(const struct ObjectEventTemplate *)packed;
    events.warps=(const struct WarpEvent *)(packed+
                       sXgbaR50OriginalEvents.object_bytes);
    events.coordEvents=(const struct CoordEvent *)(packed+
                       sXgbaR50OriginalEvents.object_bytes+
                       sXgbaR50OriginalEvents.warp_bytes);
    events.bgEvents=(const struct BgEvent *)(packed+
                       sXgbaR50OriginalEvents.object_bytes+
                       sXgbaR50OriginalEvents.warp_bytes+
                       sXgbaR50OriginalEvents.coordinate_bytes);
    sXgbaR50LiveLayout=*verified_original_layout;
    sXgbaR50LiveEvents=events;
    header.mapLayout=&sXgbaR50LiveLayout;
    header.events=&sXgbaR50LiveEvents;
    /* Do not execute original ROM map scripts until source-specific opcode
     * relocation, specials and safe state namespace are implemented. */
    header.mapScripts=NULL;
    header.connections=NULL; /* source-specific connections not rewritten */
    sXgbaR50LiveHeader=header;
    sXgbaR50World=world;sXgbaR50Group=group;sXgbaR50Number=number;
    sXgbaR50Ready=TRUE;
    gXgbaR50BridgeProof.magic=XGBA_R50_BRIDGE_MAGIC;
    gXgbaR50BridgeProof.active_source_key=key;
    gXgbaR50BridgeProof.active_npcs=events.objectEventCount;
    gXgbaR50BridgeProof.original_warps=
        sXgbaR50OriginalEvents.original_warp_count;
    ++gXgbaR50BridgeProof.verified_original_headers;
    return TRUE;
}
static const struct MapHeader *XgbaR50HeaderFor(
    u16 group,u16 number,const struct MapHeader *native_header)
{
    if(sXgbaR50Ready && group==sXgbaR50Group &&
       number==sXgbaR50Number &&
       (sXgbaR50World==sXgbaR48PendingFlyWorld ||
        (sXgbaR50World==0u && sXgbaR48PendingFlyWorld==255u))){
        return &sXgbaR50LiveHeader;
    }
    return native_header;
}
static const struct MapLayout *XgbaR50LayoutFor(const struct MapLayout *base)
{
    if(sXgbaR50Ready && gSaveBlock1Ptr &&
       gSaveBlock1Ptr->location.mapGroup==sXgbaR50Group &&
       gSaveBlock1Ptr->location.mapNum==sXgbaR50Number &&
       (sXgbaR50World==sXgbaR48PendingFlyWorld ||
        (sXgbaR50World==0u && sXgbaR48PendingFlyWorld==255u)))
        return &sXgbaR50LiveLayout;
    return XgbaR17Resolve(base);
}
/* Called from an ACTUAL original Emerald overworld frame. The full R48
 * attestation also requires the original NPC at its actual coordinates. */
static void XgbaR50VerifyLoadedEngineMap(void)
{
    if(!gSaveBlock1Ptr || !gMapHeader.mapLayout || !gMapHeader.events)return;
    if(sXgbaR50Ready && gMapHeader.mapLayout==&sXgbaR50LiveLayout &&
       gMapHeader.events==&sXgbaR50LiveEvents &&
       gSaveBlock1Ptr->location.mapGroup==sXgbaR50Group &&
       gSaveBlock1Ptr->location.mapNum==sXgbaR50Number){
        XgbaR48SetSourceMapLoaded(sXgbaR50World,sXgbaR50Group,sXgbaR50Number,TRUE);
        if(gXgbaR48OriginalNpcProof.source_map_loaded){
            gXgbaR50BridgeProof.original_map_installed=1u;
            if(sXgbaR50World!=0u)
                gXgbaR50BridgeProof.foreign_overworld_loaded=1u;
        }
    }
}
