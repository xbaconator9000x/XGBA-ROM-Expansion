/* R51 — native original Emerald field-engine terrain staging.
 *
 * This bridges a SHA-checked private grid from any source ROM to R50's
 * original Emerald map header and NPC event adapters. It deliberately does
 * not invent foreign palettes, graphics, scripts or Fly selections.
 *
 * A true source tileset + sprite installer MUST call Commit only after it
 * has authenticated and installed those original source graphics. Until
 * that happens normal Emerald GetMapLayout continues unchanged.
 */
#ifndef XGBA_R51_ORIGINAL_TERRAIN
#error R51 source geometry must be explicitly opted-in
#endif
#ifndef XGBA_R50_ENGINE_EVENTS
#error R51 original terrain requires the R50 native Emerald event adapter
#endif
#include "../common/xgba_r51_original_grid_reader.h"

struct XgbaR51TerrainProof {
    volatile u32 magic, source_key, source_grid_bytes, source_width, source_height;
    volatile u32 original_guest_page_fetches, prepared, native_layout_committed;
    volatile u32 missing_graphics, refused, actual_foreign_fly_trips;
};
EWRAM_DATA volatile struct XgbaR51TerrainProof gXgbaR51TerrainProof={0};
static EWRAM_DATA struct XgbaR51NativeGeometry sXgbaR51NativeTerrain={0};
static EWRAM_DATA struct MapLayout sXgbaR51RealMapLayout={0};
static EWRAM_DATA bool8 sXgbaR51OriginalTerrainPrepared=FALSE;

static int XgbaR51FetchRealPage(void *ctx,const char *name,u8 *dst,u16 count)
{
    (void)ctx;
    if(XgbaGuestFetch(name,dst,count)!=count){
        ++gXgbaR51TerrainProof.refused;
        return 0;
    }
    ++gXgbaR51TerrainProof.original_guest_page_fetches;
    return 1;
}

/* Must run AFTER prior game renderer relinquishes old pointers, BEFORE
 * R50 staging replaces any of the 16 KiB scratch pages and BEFORE source
 * tilesets are decoded. Keep no duplicate entire scratch in EWRAM. */
bool8 XgbaR51PrepareOriginalSourceGeometry(
    u8 world,u8 group,u8 number,XgbaR50ResolveSprite resolve_sprite,
    void *sprite_context,bool8 old_map_fade_completed)
{
    struct XgbaR51Reader reader={0};
    u32 key=((u32)world<<16)|((u32)group<<8)|number;
    if(!old_map_fade_completed || !resolve_sprite ||
       world>=3u || sXgbaR51NativeTerrain.valid ||
       sXgbaR51OriginalTerrainPrepared ||
       !gSaveBlock1Ptr ||
       (world!=0u && sXgbaR48PendingFlyWorld!=world)){
        ++gXgbaR51TerrainProof.refused;
        return FALSE;
    }
#ifdef XGBA_R52_SOURCE_LAYOUT
    if(!XgbaR52StageOriginalLayoutProfile(world,group,number,TRUE)){
        ++gXgbaR51TerrainProof.refused;
        return FALSE;
    }
#endif
    reader.fetch=XgbaR51FetchRealPage;
    reader.scratch=(u8 *)gXgbaR17Arena;
    reader.indexed_maps=XGBA_R51_ALL_SOURCE_MAPS;
    reader.cached_index_page=XGBA_R51_INVALID_PAGE;
    if(!XgbaR51StageOriginalGrid(&reader,key,&sXgbaR51NativeTerrain)){
#ifdef XGBA_R52_SOURCE_LAYOUT
        XgbaR52InvalidateSourceProfile();
#endif
        ++gXgbaR51TerrainProof.refused;
        return FALSE;
    }
    /* Event pages will overwrite scratch. The verified original grid is
     * already deep-copied into stable 5600-byte 4-aligned EWRAM. */
    if(!XgbaR50PrepareOriginalMapEvents(
          world,group,number,sXgbaR51NativeTerrain.width,
          sXgbaR51NativeTerrain.height,resolve_sprite,
          sprite_context,TRUE)){
        XgbaR51InvalidateGeometry(&sXgbaR51NativeTerrain);
#ifdef XGBA_R52_SOURCE_LAYOUT
        XgbaR52InvalidateSourceProfile();
#endif
        ++gXgbaR51TerrainProof.refused;
        return FALSE;
    }
    sXgbaR51OriginalTerrainPrepared=TRUE;
    gXgbaR51TerrainProof.magic=0x52353147u;
    gXgbaR51TerrainProof.source_key=key;
    gXgbaR51TerrainProof.source_grid_bytes=sXgbaR51NativeTerrain.grid_bytes;
    gXgbaR51TerrainProof.source_width=sXgbaR51NativeTerrain.width;
    gXgbaR51TerrainProof.source_height=sXgbaR51NativeTerrain.height;
    ++gXgbaR51TerrainProof.prepared;
    return TRUE;
}

/* Native layout binding occurs only after foreign tileset + palette
 * installation. Original geometry + native Emerald NPC/event template
 * binding does NOT magically establish foreign graphics compatibility. */
bool8 XgbaR51CommitAfterOriginalSourceGraphics(
    const struct MapLayout *verified_source_tileset_layout,
    bool8 original_primary_tiles_verified,
    bool8 original_secondary_tiles_verified,
    bool8 original_palettes_and_collision_verified)
{
    struct MapLayout layout;
    if(!sXgbaR51OriginalTerrainPrepared ||
       !sXgbaR51NativeTerrain.valid ||
       !verified_source_tileset_layout ||
       !original_primary_tiles_verified ||
       !original_secondary_tiles_verified ||
       !original_palettes_and_collision_verified ||
       !verified_source_tileset_layout->primaryTileset ||
       !verified_source_tileset_layout->secondaryTileset ||
       !verified_source_tileset_layout->width ||
       !verified_source_tileset_layout->height ||
       verified_source_tileset_layout->width!=sXgbaR51NativeTerrain.width ||
       verified_source_tileset_layout->height!=sXgbaR51NativeTerrain.height){
        ++gXgbaR51TerrainProof.missing_graphics;
        return FALSE;
    }
    layout=*verified_source_tileset_layout;
    layout.map=(const u16 *)XgbaR51NativeBytes(&sXgbaR51NativeTerrain);
    layout.border=(const u16 *)(XgbaR51NativeBytes(&sXgbaR51NativeTerrain)+
                               sXgbaR51NativeTerrain.grid_bytes);
    sXgbaR51RealMapLayout=layout;
    if(!XgbaR50CommitOriginalMapAfterGraphics(&sXgbaR51RealMapLayout,TRUE)){
        ++gXgbaR51TerrainProof.refused;
        return FALSE;
    }
    sXgbaR51OriginalTerrainPrepared=FALSE;
    ++gXgbaR51TerrainProof.native_layout_committed;
    /* IMPORTANT: no Fly proof emitted here. The original game must still
     * load the map, spawn NPCs and invoke its actual Fly arrival callback. */
    return TRUE;
}

/* Call only after a genuine original-game map fade; never during rendering,
 * script dispatch, camera access or an active battle. */
#ifdef XGBA_R53_ORIGINAL_GRAPHICS
bool8 XgbaR53ReleaseSourceGraphicsAfterFade(bool8 previous_renderer_released);
#endif
void XgbaR51ReleaseOriginalGeometryAfterFade(bool8 previous_renderer_released)
{
    if(!previous_renderer_released)return;
#ifdef XGBA_R53_ORIGINAL_GRAPHICS
    /* Original field renderer is no longer holding any palette/metatile
     * pointers; return the R53 heap allocation before R50 invalidation. */
    if(!XgbaR53ReleaseSourceGraphicsAfterFade(TRUE))return;
#endif
    XgbaR50ReleaseAfterOriginalWarpFade(TRUE);
    XgbaR51InvalidateGeometry(&sXgbaR51NativeTerrain);
    sXgbaR51OriginalTerrainPrepared=FALSE;
#ifdef XGBA_R52_SOURCE_LAYOUT
    XgbaR52InvalidateSourceProfile();
#endif
}

/* Real Emerald's frame loop observes active source geometry without changing
 * the map or claiming a foreign Fly. This also keeps the runtime module
 * linked into the exact original ARM game for native memory validation. */
void XgbaR51ObserveOriginalFieldFrame(void)
{
    if(sXgbaR51OriginalTerrainPrepared &&
       sXgbaR51NativeTerrain.valid &&
       gXgbaR51TerrainProof.source_key==sXgbaR51NativeTerrain.source_key)
        gXgbaR51TerrainProof.source_grid_bytes=sXgbaR51NativeTerrain.grid_bytes;
}

/* R73 read-only source-owned route verification. */
#include "xgba_r73_original_warp_preflight.inc"
