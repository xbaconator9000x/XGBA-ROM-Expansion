/* R54: genuine original Emerald faded-field warp admission.
 *
 * This module is called in ORIGINAL src/overworld.c LoadMapInStepsLocal
 * immediately after FieldClearVBlankHBlankCallbacks and before the original
 * LoadMapFromWarp -> LoadCurrentMapData -> LoadObjEventTemplatesFromHeader.
 * Do not call this from a mock viewer, D-pad source switch, or frame proof.
 *
 * Native game heap is reset BEFORE R53 allocates its source-owned graphics.
 * The ordinary case-1 MoveSaveBlocks_ResetHeap must then be skipped exactly
 * once for a committed foreign source; otherwise the original engine would
 * invalidate queued BG DMA pointers and live palettes/metatiles.
 *
 * Foreign sprites are NOT source-translated here. A 16-bit original foreign
 * sprite ID must have actually been installed by a separate original OBJ
 * sprite compiler/renderer; until then source worlds 1/2 refuse to load,
 * instead of producing Emerald substitute or truncated graphics.
 * This is an executable warp entry path, NOT a completed cross-world Fly.
 */
#ifndef XGBA_R54_REAL_WARP_ADMISSION
#error R54 source warp admission requires explicit original Emerald opt-in
#endif
#ifndef XGBA_R53_ORIGINAL_GRAPHICS
#error R54 requires source tiles/palettes/collision validation
#endif
#include "constants/event_objects.h"
#include "../common/xgba_r55_source_qualified_sprite_slots.h"

struct XgbaR54NativeWarpProof {
    volatile u32 magic,native_faded_load_entries,source_prepare_attempts;
    volatile u32 source_committed_warps,source_world,last_source_key;
    volatile u32 missing_source_sprites,rejected_wrong_destination;
    volatile u32 rejected_resource_load,rejected_dma_release;
    volatile u32 native_heap_resets_before_source,skipped_native_heap_resets;
    volatile u32 actual_native_fly_success; /* stays zero until real original Fly */
};
EWRAM_DATA volatile struct XgbaR54NativeWarpProof gXgbaR54NativeWarpProof={0};
static EWRAM_DATA bool8 sXgbaR54OriginalHeapPreReset=FALSE;
static EWRAM_DATA bool8 sXgbaR54SourceMapPreparedInWarp=FALSE;
/* EWRAM_DATA is placed in a zero-cleared GBA runtime section. Its static
 * nonzero C initializer is not a hardware boot guarantee. R48's 0xFF
 * no-pending-Fly sentinel therefore needs an explicit original-engine
 * first-boot initialization BEFORE any source-world admission check. */
static EWRAM_DATA bool8 sXgbaR54FlySentinelBootInitialized=FALSE;
/* Native original source sprite graphics pointers are not populated by
 * authored Emerald substitutes. R55 installation requires a real original
 * source sprite compiler that has authenticated each 16-bit source identity
 * and installed the frame, animations and palette in stable GBA memory. */
static EWRAM_DATA struct XgbaR55SourceSpriteRoster sXgbaR55OriginalSprites={0};
static EWRAM_DATA const struct ObjectEventGraphicsInfo *
    sXgbaR55VerifiedGraphicInfo[XGBA_R55_SPRITE_SLOTS]={0};
static EWRAM_DATA bool8 sXgbaR55RosterHasSourceAssets=FALSE;
struct XgbaR55NativeSpriteProof {
    volatile u32 registered_source_gfx,real_obj_info_resolutions;
    volatile u32 original_world,refused_mismatched_source,unavailable_sprites;
};
EWRAM_DATA volatile struct XgbaR55NativeSpriteProof gXgbaR55NativeSpriteProof={0};
/* Called ONLY by the forthcoming SHA-verified ORIGINAL source OBJ sprite
 * importer. Supplying a numeric 16-bit source ID alone never establishes
 * source sprite art and cannot activate a foreign map. */
struct XgbaR55InstalledOriginalSpriteSource {
    const struct ObjectEventGraphicsInfo *info;
    u32 verified_palette_crc,verified_frames_crc;
};
static int XgbaR55VerifyProvidedSourceGraphics(void *ctx,uint8_t world,
    uint16_t original,uint8_t assigned,uint32_t *palette,uint32_t *frames)
{
    const struct XgbaR55InstalledOriginalSpriteSource *source=
        (const struct XgbaR55InstalledOriginalSpriteSource *)ctx;
    const struct ObjectEventGraphicsInfo *info=source?source->info:NULL;
    (void)original;
    if(!info || world>=3u || !info->images || !info->oam ||
       !info->anims || !info->size || !palette || !frames ||
       !source->verified_palette_crc || !source->verified_frames_crc ||
       assigned<XGBA_R55_SPRITE_FIRST || assigned>XGBA_R55_SPRITE_LAST)
        return 0;
    /* The original source ROM sprite importer must authenticate these
     * ORIGINAL frames and palette on host before invoking this callback.
     * A source label and numeric sprite ID do not count as graphics. */
    *palette=source->verified_palette_crc;
    *frames=source->verified_frames_crc;
    return 1;
}
/* This entry point can only be called by an actual original asset installer
 * at a genuine faded original source transition, after native heap reset.
 * The installer must retain image/OAM/animations/palette backing until
 * XgbaR55ForgetSourceSpriteRegistrations is called at the next fade. */
bool8 XgbaR55BeginOriginalSourceSpriteRegistration(u8 world,u8 group,u8 map)
{
    unsigned i;
    if(world==0u || world>=3u || !sXgbaR54OriginalHeapPreReset ||
       sXgbaR54SourceMapPreparedInWarp ||
       !gSaveBlock1Ptr ||
       sXgbaR48PendingFlyWorld!=world ||
       gSaveBlock1Ptr->location.mapGroup!=group ||
       gSaveBlock1Ptr->location.mapNum!=map ||
       !XgbaR55ResetSourceRoster(&sXgbaR55OriginalSprites,world,group,map))
        return FALSE;
    for(i=0;i<XGBA_R55_SPRITE_SLOTS;i++)
        sXgbaR55VerifiedGraphicInfo[i]=NULL;
    sXgbaR55RosterHasSourceAssets=FALSE;
    return TRUE;
}
bool8 XgbaR55RegisterOriginalSpriteGraphics(u8 world,u16 source_gfx,
    const struct ObjectEventGraphicsInfo *native_verified_info,
    u32 original_palette_crc,u32 original_frames_crc)
{
    struct XgbaR55InstalledOriginalSpriteSource source={0};
    u8 slot;
    unsigned idx;
    if(!native_verified_info || world>=3u ||
       !sXgbaR54OriginalHeapPreReset ||
       sXgbaR54SourceMapPreparedInWarp ||
       sXgbaR55OriginalSprites.world!=world ||
       !original_palette_crc || !original_frames_crc)
        return FALSE;
    source.info=native_verified_info;
    source.verified_palette_crc=original_palette_crc;
    source.verified_frames_crc=original_frames_crc;
    if(!XgbaR55AcquireVerifiedSourceSprite(
        &sXgbaR55OriginalSprites,world,source_gfx,
        XgbaR55VerifyProvidedSourceGraphics,&source,&slot))
        return FALSE;
    idx=(unsigned)slot-XGBA_R55_SPRITE_FIRST;
    if(idx>=XGBA_R55_SPRITE_SLOTS)return FALSE;
    if(sXgbaR55VerifiedGraphicInfo[idx] &&
       sXgbaR55VerifiedGraphicInfo[idx]!=native_verified_info)
        return FALSE;
    sXgbaR55VerifiedGraphicInfo[idx]=native_verified_info;
    sXgbaR55RosterHasSourceAssets=TRUE;
    ++gXgbaR55NativeSpriteProof.registered_source_gfx;
    gXgbaR55NativeSpriteProof.original_world=world;
    return TRUE;
}
void XgbaR55ForgetSourceSpriteRegistrations(void)
{
    unsigned i;
    sXgbaR55RosterHasSourceAssets=FALSE;
    sXgbaR55OriginalSprites.count=0u;
    for(i=0;i<XGBA_R55_SPRITE_SLOTS;i++)
        sXgbaR55VerifiedGraphicInfo[i]=NULL;
}

static void XgbaR54InitializeOriginalFlyPendingSentinel(void)
{
    if(sXgbaR54FlySentinelBootInitialized)return;
    sXgbaR48PendingFlyWorld=0xffu;
    sXgbaR48PendingFlyGroup=0xffu;
    sXgbaR48PendingFlyMap=0xffu;
    sXgbaR54FlySentinelBootInitialized=TRUE;
}


/* Source0 (vanilla Emerald) object IDs already have authentic native
 * sprites present in Emerald's own object-event graphics table. For
 * Rocket/HnS the original IDs need a private source sprite importer,
 * frame palette DMA and a source ID-to-slot remap BEFORE this callback can
 * accept them. A checked 16-bit foreign id must never become a u8 cast. */
static int XgbaR54ResolveOriginalSpriteSlot(void *context,
    uint8_t source,uint16_t original_sprite,uint8_t *installed_slot)
{
    (void)context;
    if(!installed_slot)return 0;
    if(source==0u && original_sprite<=255u){
        *installed_slot=(uint8_t)original_sprite;
        return 1;
    }
    if(source!=0u && sXgbaR55RosterHasSourceAssets &&
       XgbaR55FindVerifiedSprite(&sXgbaR55OriginalSprites,
                                 source,original_sprite,installed_slot)){
        unsigned idx=(unsigned)*installed_slot-XGBA_R55_SPRITE_FIRST;
        if(idx<XGBA_R55_SPRITE_SLOTS &&
           sXgbaR55VerifiedGraphicInfo[idx]!=NULL)
            return 1;
    }
    ++gXgbaR55NativeSpriteProof.unavailable_sprites;
    ++gXgbaR54NativeWarpProof.missing_source_sprites;
    return 0;
}
/* Deterministic verified 16-bit sprite -> native source art. This bridge
 * returns NULL when the user-owned source OBJ frames have not been installed;
 * the original Emerald GetObjectEventGraphicsInfo then remains unchanged. */
const struct ObjectEventGraphicsInfo *
XgbaR55GetVerifiedNativeOriginalObjectGraphics(u8 installed_slot)
{
    unsigned index;
    if(!sXgbaR55RosterHasSourceAssets || !sXgbaR54SourceMapPreparedInWarp ||
       !sXgbaR50Ready || !gSaveBlock1Ptr ||
       sXgbaR50World!=sXgbaR55OriginalSprites.world ||
       gSaveBlock1Ptr->location.mapGroup!=sXgbaR55OriginalSprites.source_group ||
       gSaveBlock1Ptr->location.mapNum!=sXgbaR55OriginalSprites.source_map ||
       installed_slot<XGBA_R55_SPRITE_FIRST ||
       installed_slot>XGBA_R55_SPRITE_LAST)
        return NULL;
    index=installed_slot-XGBA_R55_SPRITE_FIRST;
    if(index>=sXgbaR55OriginalSprites.count ||
       sXgbaR55VerifiedGraphicInfo[index]==NULL)
        return NULL;
    ++gXgbaR55NativeSpriteProof.real_obj_info_resolutions;
    return sXgbaR55VerifiedGraphicInfo[index];
}
/* Native overworld local state machine owns the preceding fade. This
 * explicit source target is queued only after native Fly destination UI
 * selection and source-specific original script preconditions. */
static bool8 XgbaR54HasSourceMapWarpPending(void)
{
    if(!gSaveBlock1Ptr || sXgbaR48PendingFlyWorld==0xffu)return FALSE;
    if(sXgbaR48PendingFlyWorld>=3u ||
       sXgbaR48PendingFlyGroup>=255u ||
       sXgbaR48PendingFlyMap>=255u)
        return FALSE;
    return TRUE;
}
static bool8 XgbaR54PendingWarpMatchesCurrentLocation(void)
{
    return XgbaR54HasSourceMapWarpPending() &&
      gSaveBlock1Ptr->location.mapGroup==sXgbaR48PendingFlyGroup &&
      gSaveBlock1Ptr->location.mapNum==sXgbaR48PendingFlyMap;
}
/* Return: 0 no foreign source, 1 requires original source staging,
 * 2 refuse wrong world/destination, 3 previous source DMA still busy.
 * Do not mutate map state inside this preflight. */
static u8 XgbaR54InspectFadedOriginalMapLoad(void)
{
    XgbaR54InitializeOriginalFlyPendingSentinel();
    ++gXgbaR54NativeWarpProof.native_faded_load_entries;
    gXgbaR54NativeWarpProof.magic=0x52353457u;
    sXgbaR54OriginalHeapPreReset=FALSE;
    sXgbaR54SourceMapPreparedInWarp=FALSE;
    if(sXgbaR53SourceActive && IsDma3ManagerBusyWithBgCopy()){
        ++gXgbaR54NativeWarpProof.rejected_dma_release;
        return 3u;
    }
    if(sXgbaR48PendingFlyWorld==0xffu)return 0u;
    if(!XgbaR54PendingWarpMatchesCurrentLocation()){
        ++gXgbaR54NativeWarpProof.rejected_wrong_destination;
        return 2u;
    }
    return 1u;
}
/* Caller executes actual native ResetMirageTowerAndSaveBlockPtrs BEFORE
 * invoking this; it must not repeat that reset at case 1. For already
 * loaded source world geometry, do not reuse stale R51 buffer or R50 NPCs. */
static bool8 XgbaR54InstallPendingOriginalSourceAtNativeWarp(void)
{
    const u8 world=sXgbaR48PendingFlyWorld;
    const u8 group=sXgbaR48PendingFlyGroup;
    const u8 map=sXgbaR48PendingFlyMap;
    if(!XgbaR54PendingWarpMatchesCurrentLocation() ||
       !sXgbaR54OriginalHeapPreReset || sXgbaR54SourceMapPreparedInWarp){
        ++gXgbaR54NativeWarpProof.rejected_wrong_destination;
        return FALSE;
    }
    ++gXgbaR54NativeWarpProof.source_prepare_attempts;
    /* Before replacing source0 event bytes, release all source map
     * pointers after genuine fade and completed original DMA3. */
    if(sXgbaR51NativeTerrain.valid || sXgbaR50Ready ||
       sXgbaR53SourceActive){
        XgbaR51ReleaseOriginalGeometryAfterFade(TRUE);
        if(sXgbaR51NativeTerrain.valid || sXgbaR50Ready ||
           sXgbaR53SourceActive){
            ++gXgbaR54NativeWarpProof.rejected_dma_release;
            return FALSE;
        }
    }
    if(!XgbaR51PrepareOriginalSourceGeometry(world,group,map,
          XgbaR54ResolveOriginalSpriteSlot,NULL,TRUE) ||
       !XgbaR53InstallOriginalSourceGraphics()){
        ++gXgbaR54NativeWarpProof.rejected_resource_load;
        /* Never let Emerald load its colliding source-local numeric map
         * if an original foreign sprite, CRC or original grid failed. */
        XgbaR51ReleaseOriginalGeometryAfterFade(TRUE);
        return FALSE;
    }
    sXgbaR54SourceMapPreparedInWarp=TRUE;
    gXgbaR54NativeWarpProof.source_world=world;
    gXgbaR54NativeWarpProof.last_source_key=
        ((u32)world<<16)|((u32)group<<8)|map;
    ++gXgbaR54NativeWarpProof.source_committed_warps;
    return TRUE;
}
/* Original map loader's first step has already done its gated heap reset.
 * Original case 1 must not free the new live source art allocation.
 * Clear the flag immediately; never let it affect a subsequent warp. */
static bool8 XgbaR54ShouldSkipOriginalCaseOneHeapReset(void)
{
    bool8 skip=sXgbaR54OriginalHeapPreReset;
    sXgbaR54OriginalHeapPreReset=FALSE;
    if(skip)++gXgbaR54NativeWarpProof.skipped_native_heap_resets;
    return skip;
}
static void XgbaR54MarkNativePreloadHeapReset(void)
{
    sXgbaR54OriginalHeapPreReset=TRUE;
    ++gXgbaR54NativeWarpProof.native_heap_resets_before_source;
}
static void XgbaR54FailClosedBeforeForeignHeader(void)
{
    /* A wrong-world Emerald header is worse than a bounded refusal.
     * Future end-user UI may recover to origin map after reporting error. */
    ++gXgbaR54NativeWarpProof.rejected_resource_load;
    for(;;){}
}
