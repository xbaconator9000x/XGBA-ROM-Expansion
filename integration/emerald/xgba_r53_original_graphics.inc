/* R53: ORIGINAL Emerald host-backed source tileset/palette/metatile installer.
 *
 * This is native ARM Emerald field engine integration, not a map viewer.
 * R51 original terrain + R50 original event arrays MUST be verified before
 * calling Stage. The source private R53 manifest holds SHA-verified 16 KiB
 * pages; the guest checks 64-byte metadata and original content CRC.
 *
 * BG graphics are resident in map-owned original Emerald heap until the\n * original queued DMA3 tile-copy is finished. Never DMA from reused XGBA scratch.
 * 1024 source metatiles + their collision/behavior attributes and all 13 BG
 * palettes remain in stable EWRAM, not in the leased 16 KiB resource scratch.
 * No fake/backup Emerald art, foreign script bytecode, or invented Fly.
 */
#ifndef XGBA_R53_ORIGINAL_GRAPHICS
#error R53 native graphics is an explicit opt-in
#endif
#ifndef XGBA_R52_SOURCE_LAYOUT
#error R53 authentic graphics require verified R52 version-specific ABI
#endif
#include "../common/xgba_r53_original_tileset_reader.h"
#include "malloc.h"

struct XgbaR53OriginalGraphicsProof{
    volatile u32 magic,source_key,tiles_primary,tiles_secondary;
    volatile u32 palettes,metatile_cells,crc_checked_sections;
    volatile u32 stream_page_reads,native_bg_tile_loads,commits,rejected;
};
EWRAM_DATA volatile struct XgbaR53OriginalGraphicsProof gXgbaR53GraphicsProof={0};
/* Allocate per-map source art residency from ORIGINAL Emerald's bounded
 * gHeap only after the previous map has relinquished its field resources.
 * A fixed EWRAM_DATA array previously overflowed the 256KiB hardware
 * linker region by 18,208 bytes. No emulated RAM expansion is assumed. */
struct XgbaR53ResidentSourceGraphics {
    u8 graphics[1024u*32u];\n    u16 metatiles[1024u*8u];
    u16 attributes[1024u];
    u16 palettes[13u*16u];
};
static EWRAM_DATA struct XgbaR53ResidentSourceGraphics *sXgbaR53Resident=NULL;
static EWRAM_DATA struct Tileset sXgbaR53Primary={0};
static EWRAM_DATA struct Tileset sXgbaR53Secondary={0};
static EWRAM_DATA struct XgbaR53Tileset sXgbaR53PrimaryMeta={0};
static EWRAM_DATA struct XgbaR53Tileset sXgbaR53SecondaryMeta={0};
static EWRAM_DATA bool8 sXgbaR53SourceActive=FALSE;

struct XgbaR53NativeWrite{
    u16 start_metatile,start_palette;
    u8 original_attribute_bytes,source_version;
    u16 tile_start;
};
static int XgbaR53FetchNativePage(void *ctx,const char *id,u8 *dst,u16 length)
{
    u32 count;
    (void)ctx;
    count=XgbaGuestFetch(id,dst,length);
    if(count!=length){
        ++gXgbaR53GraphicsProof.rejected;
        return 0;
    }
    ++gXgbaR53GraphicsProof.stream_page_reads;
    return 1;
}
static int XgbaR53NativeWriteSection(void *ctx,u8 kind,
        const u8 *data,u32 offset,u32 size)
{
    struct XgbaR53NativeWrite *w=(struct XgbaR53NativeWrite *)ctx;
    u32 maxsize,base;
    if(!w || !data || !sXgbaR53Resident || (offset&1u) || (size&1u))
        return 0;
    if(kind==1u){
        base=(u32)w->start_metatile*16u;
        maxsize=sizeof(sXgbaR53Resident->metatiles);
        if(base>maxsize || offset>maxsize-base ||
           size>maxsize-base-offset)return 0;
        memcpy((u8 *)sXgbaR53Resident->metatiles+base+offset,data,size);
        return 1;
    }
    if(kind==2u){
        u32 i;
        base=(u32)w->start_metatile*2u;
        maxsize=sizeof(sXgbaR53Resident->attributes);
        if(w->original_attribute_bytes==2u){
            if(base>maxsize || offset>maxsize-base ||
               size>maxsize-base-offset)return 0;
            memcpy((u8 *)sXgbaR53Resident->attributes+base+offset,data,size);
            return 1;
        }
        /* FRLG 32-bit metatile attributes do NOT fit Emerald u16 without
         * a source-defined translation. Require exact behavior/layer support.
         * Version 1 is not used by the two target foreign maps. */
        if(w->original_attribute_bytes!=4u || (size&3u))return 0;
        for(i=0;i<size;i+=4u){
            u16 translated;
            u32 index=(offset+i)/4u+w->start_metatile;
            if(index>=1024u ||
               !XgbaR52TranslateAttribute(&sXgbaR52Profile,
                    XgbaR49Le32(data+i),&translated))return 0;
            sXgbaR53Resident->attributes[index]=translated;
        }
        return 1;
    }
    if(kind==3u){
        base=(u32)w->start_palette*32u;
        maxsize=sizeof(sXgbaR53Resident->palettes);
        if(base>maxsize || offset>maxsize-base ||
           size>maxsize-base-offset)return 0;
        memcpy((u8 *)sXgbaR53Resident->palettes+base+offset,data,size);
        return 1;
    }
    if(kind==0u){
        /* Original LoadBgTiles enqueues DMA3 transfers, not an immediate
         * CPU copy. The single XGBA scratch page is overwritten on the
         * next fetch. Keep all 1024 original source tiles alive until the
         * field has retired the DMA queue. */
        base=(u32)w->tile_start*32u;
        maxsize=sizeof(sXgbaR53Resident->graphics);
        if((offset&31u)||(size&31u)||base>maxsize ||
           offset>maxsize-base || size>maxsize-base-offset)return 0;
        memcpy(sXgbaR53Resident->graphics+base+offset,data,size);
        return 1;
    }
    return 0;
}
static bool8 XgbaR53SourceTileDataReady(void)
{
    return sXgbaR53SourceActive && sXgbaR53Resident && sXgbaR50Ready &&
           sXgbaR51NativeTerrain.valid &&
           sXgbaR52ProfileReady &&
           sXgbaR53PrimaryMeta.world==sXgbaR50World &&
           sXgbaR52Profile.key==sXgbaR50OriginalEvents.active_source_key &&
           gXgbaR53GraphicsProof.source_key==sXgbaR52Profile.key;
}
/* Public native map-loader entry point to call after the previous field fade.
 * A success here installs original source tileset structures and commits
 * original R51 terrain and R50 genuine event templates. Full Fly still
 * requires a genuine warp dispatcher and original NPC sprite/script importer. */
bool8 XgbaR53InstallOriginalSourceGraphics(void)
{
    struct XgbaR53Reader r={0};
    struct XgbaR53NativeWrite wr={0};
    struct MapLayout layout={0};
    unsigned side,part;
    struct XgbaR53Tileset p[2];
    struct XgbaR53NativeWrite writers[2];
    if(!sXgbaR51OriginalTerrainPrepared ||
       !sXgbaR51NativeTerrain.valid || !sXgbaR52ProfileReady ||
       sXgbaR53SourceActive || sXgbaR50Ready ||
       sXgbaR52Profile.key!=sXgbaR51NativeTerrain.source_key ||
       sXgbaR50OriginalEvents.active_source_key!=sXgbaR52Profile.key){
        ++gXgbaR53GraphicsProof.rejected;return FALSE;
    }
    r.fetch=XgbaR53FetchNativePage;
    r.scratch=(u8 *)gXgbaR17Arena;
    if(!XgbaR53MetaLoad(&r,sXgbaR50World,sXgbaR52Profile.version,
               sXgbaR52Profile.primary_tileset_offset,0u,&p[0]) ||
       !XgbaR53MetaLoad(&r,sXgbaR50World,sXgbaR52Profile.version,
               sXgbaR52Profile.secondary_tileset_offset,1u,&p[1])){
        ++gXgbaR53GraphicsProof.rejected;return FALSE;
    }
    if(p[0].tiles!=sXgbaR52Profile.tiles_in_primary ||
       p[0].metatiles!=sXgbaR52Profile.metatiles_in_primary ||
       p[0].palettes!=sXgbaR52Profile.palettes_in_primary ||
       p[0].attribute_bytes!=sXgbaR52Profile.attribute_bytes ||
       p[1].tiles+p[0].tiles!=1024u ||
       p[1].metatiles+p[0].metatiles!=1024u ||
       p[1].palettes+p[0].palettes!=13u){
        ++gXgbaR53GraphicsProof.rejected;return FALSE;
    }
    if(sXgbaR53Resident){
        ++gXgbaR53GraphicsProof.rejected;return FALSE;
    }
    sXgbaR53Resident=AllocZeroed(sizeof(*sXgbaR53Resident));
    if(!sXgbaR53Resident){
        /* Hard engine heap pressure is a legitimate non-destructive
         * refusal. Do not steal the R17 scratch or overflow real EWRAM. */
        ++gXgbaR53GraphicsProof.rejected;return FALSE;
    }
    for(side=0;side<2u;side++){
        writers[side]=wr;
        writers[side].start_metatile=side?p[0].metatiles:0u;
        writers[side].start_palette=side?p[0].palettes:0u;
        writers[side].tile_start=side?p[0].tiles:0u;
        writers[side].original_attribute_bytes=p[side].attribute_bytes;
        writers[side].source_version=p[side].version;
        /* Original decompressed graphics go into stable native heap RAM;
         * DMA3 can then safely run asynchronously from this pinned source. */
        if(!XgbaR53VisitSection(&r,&p[side],0u,
                    XgbaR53NativeWriteSection,&writers[side])){
            ++gXgbaR53GraphicsProof.rejected;
            Free(sXgbaR53Resident);sXgbaR53Resident=NULL;return FALSE;
        }
        for(part=1;part<4u;part++)
            if(!XgbaR53VisitSection(&r,&p[side],part,
                                    XgbaR53NativeWriteSection,&writers[side])){
                ++gXgbaR53GraphicsProof.rejected;
                Free(sXgbaR53Resident);sXgbaR53Resident=NULL;return FALSE;
            }
    }
    sXgbaR53Primary=(struct Tileset){0};
    sXgbaR53Secondary=(struct Tileset){0};
    sXgbaR53Primary.isCompressed=FALSE;
    sXgbaR53Secondary.isCompressed=FALSE;
    sXgbaR53Primary.isSecondary=FALSE;
    sXgbaR53Secondary.isSecondary=TRUE;
    sXgbaR53Primary.tiles=NULL;
    sXgbaR53Secondary.tiles=NULL;
    sXgbaR53Primary.palettes=(const u16 (*)[16])sXgbaR53Resident->palettes;
    sXgbaR53Secondary.palettes=(const u16 (*)[16])sXgbaR53Resident->palettes;
    sXgbaR53Primary.metatiles=sXgbaR53Resident->metatiles;
    sXgbaR53Secondary.metatiles=sXgbaR53Resident->metatiles+p[0].metatiles*8u;
    sXgbaR53Primary.metatileAttributes=sXgbaR53Resident->attributes;
    sXgbaR53Secondary.metatileAttributes=sXgbaR53Resident->attributes+p[0].metatiles;
    sXgbaR53Primary.callback=NULL;
    sXgbaR53Secondary.callback=NULL;
    layout.width=sXgbaR51NativeTerrain.width;
    layout.height=sXgbaR51NativeTerrain.height;
    layout.primaryTileset=&sXgbaR53Primary;
    layout.secondaryTileset=&sXgbaR53Secondary;
    if(!XgbaR51CommitAfterOriginalSourceGraphics(&layout,TRUE,TRUE,TRUE)){
        ++gXgbaR53GraphicsProof.rejected;
        Free(sXgbaR53Resident);sXgbaR53Resident=NULL;return FALSE;
    }
    sXgbaR53PrimaryMeta=p[0];
    sXgbaR53SecondaryMeta=p[1];
    gXgbaR53GraphicsProof.magic=0x52353347u;
    gXgbaR53GraphicsProof.source_key=sXgbaR52Profile.key;
    gXgbaR53GraphicsProof.tiles_primary=p[0].tiles;
    gXgbaR53GraphicsProof.tiles_secondary=p[1].tiles;
    gXgbaR53GraphicsProof.palettes=13u;
    gXgbaR53GraphicsProof.metatile_cells=1024u;
    gXgbaR53GraphicsProof.crc_checked_sections=r.verified_sections;
    ++gXgbaR53GraphicsProof.commits;
    sXgbaR53SourceActive=TRUE;
    return TRUE;
}
/* This is called from the actual original Emerald fieldmap.c graphics DMA
 * copy paths. 0: normal Emerald tileset, +1: original external graphics
 * verified/loaded, -1: damaged or stale source => refuse and never read NULL.
 */
s16 XgbaR53TryLoadOriginalTileset(const struct Tileset *tileset)
{
    struct XgbaR53Reader r={0};
    struct XgbaR53NativeWrite wr={0};
    const struct XgbaR53Tileset *m;
    if(tileset!=&sXgbaR53Primary && tileset!=&sXgbaR53Secondary)return 0;
    if(!XgbaR53SourceTileDataReady())return -1;
    m=tileset==&sXgbaR53Primary?
      &sXgbaR53PrimaryMeta:&sXgbaR53SecondaryMeta;
    wr.start_metatile=tileset==&sXgbaR53Primary?
       0u:sXgbaR53PrimaryMeta.metatiles;
    wr.start_palette=tileset==&sXgbaR53Primary?
       0u:sXgbaR53PrimaryMeta.palettes;
    wr.tile_start=tileset==&sXgbaR53Primary?
       0u:sXgbaR53PrimaryMeta.tiles;
    wr.original_attribute_bytes=m->attribute_bytes;
    wr.source_version=m->version;
    /* Original Emerald BG renderer queues its DMA3 copy. Source backing
     * MUST remain stable after this call and until actual faded-field
     * release completes. No asynchronous DMA references to XGBA scratch. */
    if(LoadBgTiles(2,sXgbaR53Resident->graphics+
                   (u32)wr.tile_start*32u,(u16)m->sizes[0],
                   wr.tile_start)==0xffffu)
        return -1;
    ++gXgbaR53GraphicsProof.native_bg_tile_loads;
    return 1;
}
void XgbaR53RefuseCorruptedSourceGraphics(void)
{
    ++gXgbaR53GraphicsProof.rejected;
    for(;;){}
}
bool8 XgbaR53ReleaseSourceGraphicsAfterFade(bool8 previous_renderer_released)
{
    if(!previous_renderer_released)return FALSE;
    /* Old native BG DMA must finish before original source graphic backing
     * may be freed or handed to another map. The previous renderer being
     * faded does not prove its queued DMA has retired. */
    if(IsDma3ManagerBusyWithBgCopy())return FALSE;
    sXgbaR53SourceActive=FALSE;
    if(sXgbaR53Resident){
        Free(sXgbaR53Resident);sXgbaR53Resident=NULL;
    }
    return TRUE;
}
