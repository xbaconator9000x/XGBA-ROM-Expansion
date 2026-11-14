/* R52: original Emerald field-engine binding for source-versioned map IDs.
 * This is not a source selector: the traits are SHA-verified host pages from
 * the actual original ROM layout ABI. R50/R51 still require authenticated
 * terrain, palette and installed NPC graphics before activating a map.
 */
#ifndef XGBA_R52_SOURCE_LAYOUT
#error R52 original layout metadata is an explicit native opt-in
#endif
#ifndef XGBA_R51_ORIGINAL_TERRAIN
#error R52 source metadata requires native R51 original terrain
#endif
#include "../common/xgba_r52_source_layout_profile.h"

struct XgbaR52LayoutProof {
    volatile u32 magic,verified_source_key,original_version,original_primary_split;
    volatile u32 original_primary_palettes,original_attribute_bytes;
    volatile u32 source_page_fetches,refused,real_emerald_field_uses;
};
EWRAM_DATA volatile struct XgbaR52LayoutProof gXgbaR52LayoutProof={0};
static EWRAM_DATA struct XgbaR52MapProfile sXgbaR52Profile={0};
static EWRAM_DATA bool8 sXgbaR52ProfileReady=FALSE;

static int XgbaR52FetchRealLayoutPage(void *ctx,const char *id,
                                     u8 *target,u16 length)
{
    (void)ctx;
    if(!XgbaR48StagePagedResourceName(id) ||
       XgbaGuestFetch((const char *)sXgbaR48ResourceName,
                      target,length)!=length){
        ++gXgbaR52LayoutProof.refused;
        return 0;
    }
    ++gXgbaR52LayoutProof.source_page_fetches;
    return 1;
}
/* Only after the old source renderer is released. The 16KiB scratch arena
 * is reused immediately for R51 original map grid and R50 NPC/event pages.
 * Only a single 32-byte verified profile remains in EWRAM. */
static bool8 XgbaR52StageOriginalLayoutProfile(
    u8 world,u8 group,u8 map,bool8 previous_renderer_released)
{
    struct XgbaR52Reader r={0};
    struct XgbaR52MapProfile p;
    u32 key=((u32)world<<16)|((u32)group<<8)|map;
    if(!previous_renderer_released || sXgbaR52ProfileReady || world>=3u){
        ++gXgbaR52LayoutProof.refused;
        return FALSE;
    }
    r.fetch=XgbaR52FetchRealLayoutPage;
    r.scratch=(u8 *)gXgbaR17Arena;
    r.indexed_maps=XGBA_R52_MAPS;
    r.cached_page=XGBA_R52_PAGE_INVALID;
    if(!XgbaR52LoadProfile(&r,key,&p)){
        ++gXgbaR52LayoutProof.refused;
        return FALSE;
    }
    sXgbaR52Profile=p;
    sXgbaR52ProfileReady=TRUE;
    gXgbaR52LayoutProof.magic=0x52353250u;
    gXgbaR52LayoutProof.verified_source_key=key;
    gXgbaR52LayoutProof.original_version=p.version;
    gXgbaR52LayoutProof.original_primary_split=p.metatiles_in_primary;
    gXgbaR52LayoutProof.original_primary_palettes=p.palettes_in_primary;
    gXgbaR52LayoutProof.original_attribute_bytes=p.attribute_bytes;
    return TRUE;
}
static void XgbaR52InvalidateSourceProfile(void)
{
    sXgbaR52ProfileReady=FALSE;
    gXgbaR52LayoutProof.verified_source_key=0xffffffffu;
}
/* Called from actual original Emerald field_camera.c and fieldmap.c.
 * Ordinary Emerald continues with 512: a foreign numeric 0:9 cannot be
 * mistaken for original Emerald 0:9 without a committed source map. */
u16 XgbaR52PrimaryMetatileCount(void)
{
    if(sXgbaR52ProfileReady && sXgbaR50Ready && gSaveBlock1Ptr &&
       sXgbaR52Profile.key==sXgbaR50OriginalEvents.active_source_key &&
       XgbaR80SourceLocationMatchesNative(
           sXgbaR50World,sXgbaR50Group,sXgbaR50Number)){
        ++gXgbaR52LayoutProof.real_emerald_field_uses;
        return sXgbaR52Profile.metatiles_in_primary;
    }
    return 512u;
}
u16 XgbaR52PrimaryTilesCount(void)
{
    if(sXgbaR52ProfileReady && sXgbaR50Ready && gSaveBlock1Ptr &&
       sXgbaR52Profile.key==sXgbaR50OriginalEvents.active_source_key &&
       XgbaR80SourceLocationMatchesNative(
           sXgbaR50World,sXgbaR50Group,sXgbaR50Number))
        return sXgbaR52Profile.tiles_in_primary;
    return 512u;
}
u16 XgbaR52PrimaryPaletteCount(void)
{
    if(sXgbaR52ProfileReady && sXgbaR50Ready && gSaveBlock1Ptr &&
       sXgbaR52Profile.key==sXgbaR50OriginalEvents.active_source_key &&
       XgbaR80SourceLocationMatchesNative(
           sXgbaR50World,sXgbaR50Group,sXgbaR50Number))
        return sXgbaR52Profile.palettes_in_primary;
    return 6u;
}
void XgbaR52OriginalFrameProof(void)
{
    if(sXgbaR52ProfileReady &&
       gXgbaR52LayoutProof.verified_source_key!=sXgbaR52Profile.key)
        ++gXgbaR52LayoutProof.refused;
}
