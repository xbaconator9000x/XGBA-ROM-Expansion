/* R73 original Emerald R50/R51-native source-scoped warp preflight.
 * A validated route does not commit an Emerald warp. Source world events
 * remain intentionally quarantined until arbitrary original source maps,
 * sprite assets and world-qualified Flash persistence can be installed.
 */
#include "../common/xgba_r73_source_warp_preflight.h"
bool8 XgbaR73PreflightLoadedForeignWarp(u8 warp_index,
                                       struct XgbaR73SourceWarpRoute *route)
{
    struct XgbaR51Reader maps={0};
    struct XgbaR51IndexRow dest={0};
    struct XgbaR49Reader events={0};
    struct XgbaR49OriginalEvents dest_events={0};
    const u8 *warps,*warp;
    u32 key,target;
    u8 world;
    if(!route || !gSaveBlock1Ptr || !sXgbaR50Ready ||
       !sXgbaR51NativeTerrain.valid || !sXgbaR48SourceMapLoaded ||
       sXgbaR50World==0u || sXgbaR50World>=3u ||
       warp_index>=sXgbaR50OriginalEvents.original_warp_count ||
       sXgbaR50OriginalEvents.original_warp_count==0u ||
       gSaveBlock1Ptr->location.mapGroup!=sXgbaR50Group ||
       gSaveBlock1Ptr->location.mapNum!=sXgbaR50Number)
        return FALSE;
    world=sXgbaR50World;
    key=XgbaR73ScopedKey(world,sXgbaR50Group,sXgbaR50Number);
    if(key!=sXgbaR50OriginalEvents.active_source_key)return FALSE;
    /* R50 deep-copied these original records before arena reassignment. */
    warps=XgbaR50EventBytes(&sXgbaR50OriginalEvents)+
          sXgbaR50OriginalEvents.object_bytes;
    warp=warps+(u32)warp_index*XGBA_R73_WARP_BYTES;
    if(warp[6]==127u && warp[7]==127u)return FALSE;
    target=XgbaR73ScopedKey(world,warp[7],warp[6]);
    maps.fetch=XgbaR51FetchRealPage;
    maps.scratch=(u8 *)gXgbaR17Arena;
    maps.indexed_maps=XGBA_R51_ALL_SOURCE_MAPS;
    maps.cached_index_page=XGBA_R51_INVALID_PAGE;
    if(!XgbaR51FindSourceMap(&maps,target,&dest))return FALSE;
    events.fetch=XgbaR50FetchOriginalPage;
    events.scratch=(u8 *)gXgbaR17Arena;
    events.indexed_maps=XGBA_R49_ALL_MAPS;
    events.cached_index_page=XGBA_R49_INVALID_PAGE;
    if(!XgbaR49LoadOriginalMapEvents(&events,target,&dest_events))
        return FALSE;
    return XgbaR73ProveOriginalWarp(
        key,sXgbaR51NativeTerrain.width,sXgbaR51NativeTerrain.height,
        warps,sXgbaR50OriginalEvents.original_warp_count,warp_index,
        target,dest.width,dest.height,dest_events.warps,
        dest_events.warp_count,route)==XGBA_R73_OK;
}
