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
#include "../common/xgba_r56_original_obj_reader.h"
#include "../common/xgba_r66_original_obj_animation.h"
#include "../common/xgba_r63_native_return_path.h"
#include "../common/xgba_r70_original_witness_binding.h"

static bool8 XgbaR57InstallPendingMapSprites(u8 world,u8 group,u8 map);
static void XgbaR57ReleasePendingMapSprites(void);
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
/* Per-map roster is transient. Never reserve ~710B permanent EWRAM:
 * source-built original Emerald exceeded 256KiB EWRAM by 428B. Allocate
 * only AFTER original native heap reset, release BEFORE next heap reset. */
static EWRAM_DATA struct XgbaR55SourceSpriteRoster *sXgbaR55OriginalSprites=NULL;
static EWRAM_DATA const struct ObjectEventGraphicsInfo *
    sXgbaR55VerifiedGraphicInfo[XGBA_R55_SPRITE_SLOTS]={0};
static EWRAM_DATA bool8 sXgbaR55RosterHasSourceAssets=FALSE;
struct XgbaR55NativeSpriteProof {
    volatile u32 registered_source_gfx,real_obj_info_resolutions;
    volatile u32 original_world,refused_mismatched_source,unavailable_sprites;
    volatile u32 authenticated_original_resource_sections,rejected_original_crc;
};
EWRAM_DATA volatile struct XgbaR55NativeSpriteProof gXgbaR55NativeSpriteProof={0};
/* Called ONLY by the forthcoming SHA-verified ORIGINAL source OBJ sprite
 * importer. Supplying a numeric 16-bit source ID alone never establishes
 * source sprite art and cannot activate a foreign map. */
struct XgbaR55InstalledOriginalSpriteSource {
    const struct ObjectEventGraphicsInfo *info;
    u32 verified_palette_crc,verified_frames_crc;
};
/* R56 requires a real, host-SHA-backed original sprite source resource.
 * No caller-provided integer CRC can authenticate source art on its own.
 * The guest recomputes the complete original frame, palette, OAM and anim
 * content CRC for this world+full 16-bit source graphics identity.
 * The separately authored OBJ installer must still retain actual native
 * frames/OAM/palette backing for the live Emerald object lifetime. */
struct XgbaR56NativeBackingCheck{
    const struct ObjectEventGraphicsInfo *info;
    const u16 *palette;
    struct XgbaR56SourceObject original;
};
static int XgbaR56CheckGenuineNativeSpriteBacking(
    void *context,unsigned section,const uint8_t *bytes,
    uint32_t offset,uint32_t count)
{
    const struct XgbaR56NativeBackingCheck *c=
        (const struct XgbaR56NativeBackingCheck *)context;
    const struct ObjectEventGraphicsInfo *info=c?c->info:NULL;
    unsigned i;
    uint32_t frame_size;
    if(!c || !info || !bytes || offset!=0u ||
       section>=XGBA_R56_SECTIONS)return 0;
    if(section==1u)
        return count==32u && c->palette &&
               memcmp(bytes,c->palette,32u)==0;
    if(section==2u){
        return count==XGBA_R66_OAM_BYTES && info->oam &&
            sizeof(struct OamData)==XGBA_R66_OAM_BYTES &&
            XgbaR66OriginalOamValid(bytes,count,
                                    c->original.width,c->original.height) &&
            memcmp(info->oam,bytes,count)==0;
    }
    if(section==3u){
        return count<=XGBA_R66_ANIM_MAX_BYTES && info->anims &&
            info->anims[0] && sizeof(union AnimCmd)==4u &&
            XgbaR66OriginalFirstAnimationValid(bytes,count,
                                                c->original.frame_count) &&
            memcmp(info->anims[0],bytes,count)==0;
    }
    if(section!=0u)return 0;
    if(!info->images || info->width!=c->original.width ||
       info->height!=c->original.height ||
       count!=c->original.sizes[0])return 0;
    frame_size=(uint32_t)c->original.width*c->original.height/2u;
    for(i=0u;i<c->original.frame_count;i++){
        const struct SpriteFrameImage *image=&info->images[i];
        if(!image->data || image->size!=frame_size ||
           memcmp(image->data,bytes+frame_size*i,frame_size)!=0)
            return 0;
    }
    return 1;
}
static bool8 XgbaR56AuthenticateOriginalSourceForNativeSprite(
    u8 world,u16 original_id,const struct ObjectEventGraphicsInfo *info,
    const u16 *palette_data,u32 palette_crc,u32 frames_crc)
{
    struct XgbaR56Reader reader={0};
    struct XgbaR56SourceObject source={0};
    struct XgbaR56NativeBackingCheck backing={0};
    unsigned part;
    if(world==0u || world>=3u || !palette_crc || !frames_crc ||
       !sXgbaR54OriginalHeapPreReset || sXgbaR54SourceMapPreparedInWarp)
        return FALSE;
    reader.fetch=XgbaR53FetchNativePage;
    reader.scratch=(u8 *)gXgbaR17Arena;
    if(!info || !palette_data ||
       !XgbaR56ReadMeta(&reader,world,original_id,&source) ||
       source.crc[0]!=frames_crc || source.crc[1]!=palette_crc)
        goto refused;
    backing.info=info;backing.palette=palette_data;
    backing.original=source;
    for(part=0u;part<XGBA_R56_SECTIONS;part++){
        /* ALL four authenticated original sections must match stable native
         * backing: frames, palette, OAM and first animation. No silent
         * substituted static GBA OAM/animation is eligible for registration. */
        if(!XgbaR56VisitSection(&reader,&source,part,
              XgbaR56CheckGenuineNativeSpriteBacking,&backing))
            goto refused;
    }
    gXgbaR55NativeSpriteProof.authenticated_original_resource_sections+=
        XGBA_R56_SECTIONS;
    return TRUE;
refused:
    ++gXgbaR55NativeSpriteProof.rejected_original_crc;
    return FALSE;
}
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
       !gSaveBlock1Ptr || sXgbaR55OriginalSprites ||
       sXgbaR48PendingFlyWorld!=world ||
       gSaveBlock1Ptr->location.mapGroup!=group ||
       gSaveBlock1Ptr->location.mapNum!=map)
        return FALSE;
    sXgbaR55OriginalSprites=AllocZeroed(sizeof(*sXgbaR55OriginalSprites));
    if(!sXgbaR55OriginalSprites)return FALSE;
    if(!XgbaR55ResetSourceRoster(sXgbaR55OriginalSprites,world,group,map)){
        Free(sXgbaR55OriginalSprites);sXgbaR55OriginalSprites=NULL;
        return FALSE;
    }
    for(i=0;i<XGBA_R55_SPRITE_SLOTS;i++)
        sXgbaR55VerifiedGraphicInfo[i]=NULL;
    sXgbaR55RosterHasSourceAssets=FALSE;
    return TRUE;
}
bool8 XgbaR55RegisterOriginalSpriteGraphics(u8 world,u16 source_gfx,
    const struct ObjectEventGraphicsInfo *native_verified_info,
    const u16 *source_native_palette_backing,
    u32 original_palette_crc,u32 original_frames_crc)
{
    struct XgbaR55InstalledOriginalSpriteSource source={0};
    u8 slot;
    unsigned idx;
    if(!native_verified_info || world>=3u ||
       !sXgbaR54OriginalHeapPreReset ||
       sXgbaR54SourceMapPreparedInWarp ||
       !sXgbaR55OriginalSprites ||
       sXgbaR55OriginalSprites->world!=world ||
       !original_palette_crc || !original_frames_crc)
        return FALSE;
    source.info=native_verified_info;
    source.verified_palette_crc=original_palette_crc;
    source.verified_frames_crc=original_frames_crc;
    if(!XgbaR56AuthenticateOriginalSourceForNativeSprite(
            world,source_gfx,native_verified_info,
            source_native_palette_backing,
            original_palette_crc,original_frames_crc))
        return FALSE;
    if(!XgbaR55AcquireVerifiedSourceSprite(
        sXgbaR55OriginalSprites,world,source_gfx,
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
    if(sXgbaR55OriginalSprites){
        /* Caller must be the actual faded native map loader with
         * source animation/DMA callbacks quiescent. */
        Free(sXgbaR55OriginalSprites);
        sXgbaR55OriginalSprites=NULL;
    }
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
       XgbaR55FindVerifiedSprite(sXgbaR55OriginalSprites,
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
    if(!sXgbaR55RosterHasSourceAssets || !sXgbaR55OriginalSprites ||
       !sXgbaR54SourceMapPreparedInWarp ||
       !sXgbaR50Ready || !gSaveBlock1Ptr ||
       sXgbaR50World!=sXgbaR55OriginalSprites->world ||
       gSaveBlock1Ptr->location.mapGroup!=sXgbaR55OriginalSprites->source_group ||
       gSaveBlock1Ptr->location.mapNum!=sXgbaR55OriginalSprites->source_map ||
       installed_slot<XGBA_R55_SPRITE_FIRST ||
       installed_slot>XGBA_R55_SPRITE_LAST)
        return NULL;
    index=installed_slot-XGBA_R55_SPRITE_FIRST;
    if(index>=sXgbaR55OriginalSprites->count ||
       sXgbaR55VerifiedGraphicInfo[index]==NULL)
        return NULL;
    ++gXgbaR55NativeSpriteProof.real_obj_info_resolutions;
    return sXgbaR55VerifiedGraphicInfo[index];
}
/* R70: require the same exact source artwork on the original witness
 * template and the physically spawned native object-event actor. The R55
 * roster must be the active source map, not a stale allocation. */
bool8 XgbaR70ResolveAuthenticWitnessGraphics(u8 world,u8 group,u8 map,
                                               u8 *slot)
{
    if(!slot || world>=3u)return FALSE;
    if(world==0u)
        return XgbaR70VerifiedWitnessNativeSlot(NULL,world,group,map,slot);
    if(!sXgbaR54SourceMapPreparedInWarp || !sXgbaR50Ready ||
       !sXgbaR55RosterHasSourceAssets || !sXgbaR55OriginalSprites ||
       !gSaveBlock1Ptr || sXgbaR50World!=world ||
       gSaveBlock1Ptr->location.mapGroup!=group ||
       gSaveBlock1Ptr->location.mapNum!=map ||
       !XgbaR70VerifiedWitnessNativeSlot(sXgbaR55OriginalSprites,
                                          world,group,map,slot))
        return FALSE;
    return XgbaR55GetVerifiedNativeOriginalObjectGraphics(*slot)!=NULL;
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
/* Caller is the ORIGINAL fade/load state machine, at case 0 BEFORE
 * native heap reset. The original BG DMA must be retired. Release old
 * source layout, event pointers and original per-map sprite mapping. */
static bool8 XgbaR54ReleaseOldSourceBeforeNativeHeapReset(void)
{
    if(IsDma3ManagerBusyWithBgCopy() &&
       (sXgbaR53SourceActive || sXgbaR51NativeTerrain.valid))
        return FALSE;
    if(sXgbaR53SourceActive || sXgbaR51NativeTerrain.valid ||
       sXgbaR50Ready){
        XgbaR51ReleaseOriginalGeometryAfterFade(TRUE);
        if(sXgbaR53SourceActive || sXgbaR51NativeTerrain.valid ||
           sXgbaR50Ready)
            return FALSE;
    }
    XgbaR57ReleasePendingMapSprites();
    XgbaR55ForgetSourceSpriteRegistrations();
    return TRUE;
}
static bool8 XgbaR54PendingWarpMatchesCurrentLocation(void)
{
    return XgbaR54HasSourceMapWarpPending() &&
      gSaveBlock1Ptr->location.mapGroup==sXgbaR48PendingFlyGroup &&
      gSaveBlock1Ptr->location.mapNum==sXgbaR48PendingFlyMap;
}
/* R63: source0 is already linked into the ACTUAL Emerald game ROM.
 * Verify original ROM header and actual witness placement, then let the
 * vanilla engine do the return warp. Never require R53/R56 source0 art.
 * This is an arrival precondition, not an arrival/progression witness. */
static bool8 XgbaR63NativeEmeraldReturnHeaderPresent(void)
{
    const struct MapHeader *native=gMapGroups[0][9];
    unsigned i;
    if(!native || !native->mapLayout || !native->events ||
       !native->events->objectEvents ||
       !XgbaR63VerifyNativeReturnHeader(
          0u,0u,9u,native->mapLayout->width,native->mapLayout->height,
          native->events->objectEventCount,
          XGBA_R63_NATIVE_LANDING_X,XGBA_R63_NATIVE_LANDING_Y))
        return FALSE;
    for(i=0u;i<native->events->objectEventCount;i++){
        const struct ObjectEventTemplate *npc=&native->events->objectEvents[i];
        if(npc->localId==2u && npc->x==12 && npc->y==13)
            return TRUE;
    }
    return FALSE;
}
/* Return: 0 no foreign source or native Emerald return,
 * 1 requires original foreign source staging,
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
    /* The third Fly destination is the source-built Emerald already in
     * cartridge ROM. Retire old foreign resources at case 0 and let
     * LoadMapFromWarp + case-1 heap reset install the native map normally.
     * Keep the pending world0 token until actual field arrival confirms it. */
    if(sXgbaR48PendingFlyWorld==XGBA_R63_NATIVE_WORLD){
        if(!XgbaR63NativeEmeraldReturnHeaderPresent()){
            ++gXgbaR54NativeWarpProof.rejected_wrong_destination;
            return 2u;
        }
        return 0u;
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
    /* Previous source-owned graphics MUST have been released while its
     * heap was intact by the case-0 faded-source cleanup, *before* the
     * original ResetMirageTowerAndSaveBlockPtrs heap reset. Freeing stale
     * pointers here would corrupt the freshly reset Emerald allocator. */
    if(sXgbaR51NativeTerrain.valid || sXgbaR50Ready ||
       sXgbaR53SourceActive){
        ++gXgbaR54NativeWarpProof.rejected_dma_release;
        return FALSE;
    }
    if(!XgbaR57InstallPendingMapSprites(world,group,map) ||
       !XgbaR51PrepareOriginalSourceGeometry(world,group,map,
          XgbaR54ResolveOriginalSpriteSlot,NULL,TRUE) ||
       !XgbaR53InstallOriginalSourceGraphics()){
        ++gXgbaR54NativeWarpProof.rejected_resource_load;
        /* Never let Emerald load its colliding source-local numeric map
         * if an original foreign sprite, CRC or original grid failed. */
        XgbaR51ReleaseOriginalGeometryAfterFade(TRUE);
        XgbaR57ReleasePendingMapSprites();
        XgbaR55ForgetSourceSpriteRegistrations();
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
/* R76: missing foreign assets must never strand the player in a black LCD
 * busy loop. Revert to the real native Emerald 0:9 map with a real fade/load;
 * do NOT count a Fly leg or carry an unsafe foreign map header into Emerald.
 * If an in-flight DMA still owns source graphics, retry this case next frame.
 */
static bool8 XgbaR54FailClosedBeforeForeignHeader(void)
{
    ++gXgbaR54NativeWarpProof.rejected_resource_load;
    if(IsDma3ManagerBusyWithBgCopy())return FALSE;
    if(sXgbaR53SourceActive || sXgbaR51NativeTerrain.valid ||
       sXgbaR50Ready)
        XgbaR51ReleaseOriginalGeometryAfterFade(TRUE);
    if(sXgbaR53SourceActive || sXgbaR51NativeTerrain.valid ||
       sXgbaR50Ready)return FALSE;
    XgbaR57ReleasePendingMapSprites();
    XgbaR55ForgetSourceSpriteRegistrations();
    /* Revoke the unfulfilled Fly token before the original field engine
     * obtains gMapGroups[0][9]; no false cross-world progress is recorded. */
    sXgbaR48PendingFlyWorld=0xffu;
    sXgbaR48PendingFlyGroup=0xffu;
    sXgbaR48PendingFlyMap=0xffu;
    sXgbaR48SourceMapLoaded=FALSE;
    sXgbaR48ImportedWorld=0u;
    sXgbaR48ImportedGroup=0u;
    sXgbaR48ImportedMap=0u;
    sXgbaR48FlyLeg=0u;
    sXgbaR48NpcTalkedMask=0u;
    gXgbaR48OriginalNpcProof.source_map_loaded=0u;
    sXgbaR54OriginalHeapPreReset=FALSE;
    sXgbaR54SourceMapPreparedInWarp=FALSE;
    /* The landing is explicitly the original source0 Emerald cartridge map,
     * not an authored placeholder or the numeric collision from Rocket. */
    SetWarpDestination(0,9,WARP_ID_NONE,
                       XGBA_R63_NATIVE_LANDING_X,
                       XGBA_R63_NATIVE_LANDING_Y);
    return TRUE;
}
