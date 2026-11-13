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
#include "../common/xgba_r50_engine_event_adapter.h"
#include <stdint.h>

extern const struct MapHeader *const *const gMapGroups[];
#define XGBA_R50_BRIDGE_MAGIC 0x52353045u
struct XgbaR50BridgeProof {
    volatile u32 magic,verified_original_headers,real_guest_fetches;
    volatile u32 rejected,active_source_key,active_npcs,original_warps;
    volatile u32 original_map_installed,foreign_overworld_loaded;
};
EWRAM_DATA volatile struct XgbaR50BridgeProof gXgbaR50BridgeProof={0};
/* R49 pages are ephemeral; actual Emerald events use a deep-copied, aligned
 * source event array, not pointers into a cache about to be evicted. */
/* R50 shares the protected 16KiB heap-tail arena with original map tiles.
 * Event paging happens only after old graphics are released by a warp fade;
 * source events are deep-copied before new graphics reclaim the arena. */
#if XGBA_R17_RESERVE < XGBA_R49_PAGE_BYTES
#error R50 original event paging requires a 16KiB protected heap-tail arena
#endif
static EWRAM_DATA bool8 sXgbaR50EventsPrepared=FALSE;
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
/* Stage exact source-qualified original object events during a real faded
 * native warp: the previous map must have relinquished its graphics arena.
 * Never overwrite a currently rendered or active original map. */
bool8 XgbaR50PrepareOriginalMapEvents(
    u8 world,u8 group,u8 number,u16 width,u16 height,
    XgbaR50ResolveSprite graphics_slot,void *graphics_context,
    bool8 original_renderer_released)
{
    struct XgbaR49Reader reader={0};
    u32 key;
    if(!original_renderer_released || !graphics_slot ||
       sXgbaR50Ready || sXgbaR50EventsPrepared ||
       world>=3u || group!=0u || (world==2u?number!=4u:number!=9u) ||
       !width || !height || width>255u || height>255u ||
       (world!=0u && sXgbaR48PendingFlyWorld!=world)){
        ++gXgbaR50BridgeProof.rejected;
        return FALSE;
    }
    /* Old arena pointers are dead. The next verified original map tileset
     * load reacquires and overwrites these temporary page bytes. */
    sXgbaR17Active=FALSE;
    key=((u32)world<<16)|((u32)group<<8)|number;
    reader.fetch=XgbaR50FetchOriginalPage;
    reader.scratch=(uint8_t *)gXgbaR17Arena;
    reader.indexed_maps=XGBA_R49_ALL_MAPS;
    reader.cached_index_page=XGBA_R49_INVALID_PAGE;
    if(!XgbaR50StageEvents(&reader,key,width,height,
          graphics_slot,graphics_context,
          (u32)(uintptr_t)sXgbaR50QuarantinedScript,
          &sXgbaR50OriginalEvents)){
        ++gXgbaR50BridgeProof.rejected;
        return FALSE;
    }
    sXgbaR50World=world;
    sXgbaR50Group=group;
    sXgbaR50Number=number;
    sXgbaR50EventsPrepared=TRUE;
    gXgbaR50BridgeProof.magic=XGBA_R50_BRIDGE_MAGIC;
    gXgbaR50BridgeProof.active_source_key=key;
    gXgbaR50BridgeProof.active_npcs=sXgbaR50OriginalEvents.object_count;
    gXgbaR50BridgeProof.original_warps=
        sXgbaR50OriginalEvents.original_warp_count;
    ++gXgbaR50BridgeProof.verified_original_headers;
    return TRUE;
}
/* Bind authentic verified layout/collision and source object records only
 * AFTER original graphics/tilesets have reoccupied the map arena. */
bool8 XgbaR50CommitOriginalMapAfterGraphics(
    const struct MapLayout *layout,bool8 original_assets_sha_verified)
{
    struct MapEvents events={0};
    struct MapHeader header;
    const u8 *packed;
    if(!sXgbaR50EventsPrepared || sXgbaR50Ready ||
       !original_assets_sha_verified || !layout || !layout->map ||
       !layout->border || !layout->primaryTileset ||
       !layout->secondaryTileset ||
       layout->width!=sXgbaR50OriginalEvents.width ||
       layout->height!=sXgbaR50OriginalEvents.height){
        ++gXgbaR50BridgeProof.rejected;
        return FALSE;
    }
    /* Numeric map collisions stay keyed by R49 source ID, not native slot.
     * Current three witnesses are 0:9 Emerald/Rocket and 0:4 HnS. */
    header=*gMapGroups[sXgbaR50Group][sXgbaR50Number];
    packed=XgbaR50EventBytes(&sXgbaR50OriginalEvents);
    events.objectEventCount=sXgbaR50OriginalEvents.object_count;
    events.warpCount=0u;    /* native source warp still untranslated */
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
    sXgbaR50LiveLayout=*layout;
    sXgbaR50LiveEvents=events;
    header.mapLayout=&sXgbaR50LiveLayout;
    header.events=&sXgbaR50LiveEvents;
    header.mapScripts=NULL;
    header.connections=NULL;
    sXgbaR50LiveHeader=header;
    sXgbaR50EventsPrepared=FALSE;
    sXgbaR50Ready=TRUE;
    return TRUE;
}
/* Call only after genuine original Emerald field fade has retired all
 * previous map/graphics pointers; not a source-selector simulation. */
void XgbaR50ReleaseAfterOriginalWarpFade(bool8 real_field_renderer_released)
{
    if(!real_field_renderer_released)return;
    sXgbaR50Ready=FALSE;
    sXgbaR50EventsPrepared=FALSE;
    sXgbaR17Active=FALSE;
    sXgbaR48SourceMapLoaded=FALSE;
    gXgbaR48OriginalNpcProof.source_map_loaded=0u;
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
void XgbaR50VerifyLoadedEngineMap(void)
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
