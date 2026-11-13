/* R52: source-authentic Emerald / Rocket / Heart & Soul map layout ABI.
 * Source layouts HnS/Rocket include 4 extra bytes at +24, which vanilla
 * Emerald must not read as part of its 24-byte MapLayout. R52 retains a
 * 32-byte/source-map index; no proprietary source bytes are in this header.
 *
 * 0 = original Emerald legacy 512/512 and u16 attributes
 * 1 = FRLG variant 640/384 + 7 primary palettes, u32 attributes, custom border
 * 2 = HnS/Rocket family 640/384 + 7 primary palettes, u32 attributes, fixed border
 * Others are kept private as unsupported and must NEVER silently reinterpret.
 */
#ifndef XGBA_R52_SOURCE_LAYOUT_PROFILE_H
#define XGBA_R52_SOURCE_LAYOUT_PROFILE_H
#include "xgba_r49_full_original_map_events.h"
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#define XGBA_R52_ROW 32u
#define XGBA_R52_PAGE 16384u
#define XGBA_R52_MAPS 2856u
#define XGBA_R52_PAGE_INVALID UINT16_MAX
#define XGBA_R52_EMERALD 0u
#define XGBA_R52_FRLG 1u
#define XGBA_R52_HNS 2u
#define XGBA_R52_FLAG_PROFILE_SUPPORTED 1u
#define XGBA_R52_FLAG_WIDE_PRIMARY 2u

typedef int (*XgbaR52Fetch)(void *,const char *,uint8_t *,uint16_t);
struct XgbaR52Reader {
    XgbaR52Fetch fetch;
    void *ctx;
    uint8_t *scratch;
    uint32_t indexed_maps,reads;
    uint16_t cached_page;
};
struct XgbaR52MapProfile {
    uint32_t key;
    uint8_t version,border_width,border_height,original_extra;
    uint16_t tiles_in_primary,metatiles_in_primary;
    uint8_t palettes_in_primary,attribute_bytes,flags,compression_flags;
    uint32_t source_layout_offset,primary_tileset_offset,secondary_tileset_offset;
    uint32_t original_row_crc;
};
_Static_assert(sizeof(struct XgbaR52MapProfile)==XGBA_R52_ROW,"R52 index ABI must be 32 bytes");

static inline int XgbaR52ReadIndexPage(struct XgbaR52Reader *r,unsigned page)
{
    char id[]="r52.mapmeta.000";
    if(!r || !r->fetch || !r->scratch || page>999u)return 0;
    if(r->cached_page==page)return 1;
    r->cached_page=XGBA_R52_PAGE_INVALID;
    id[12]=(char)('0'+(page/100u)%10u);
    id[13]=(char)('0'+(page/10u)%10u);
    id[14]=(char)('0'+page%10u);
    if(r->fetch(r->ctx,id,r->scratch,XGBA_R52_PAGE)!=1)return 0;
    ++r->reads;
    r->cached_page=(uint16_t)page;
    return 1;
}
static inline int XgbaR52LoadProfile(struct XgbaR52Reader *r,
                  uint32_t source_key,struct XgbaR52MapProfile *out)
{
    uint32_t lo=0,hi;
    const uint8_t *p;
    struct XgbaR52MapProfile next;
    if(!r || !out || !r->indexed_maps || r->indexed_maps>XGBA_R52_MAPS ||
       source_key>>24u || ((source_key>>16u)&255u)>2u)return 0;
    hi=r->indexed_maps;
    while(lo<hi){
        uint32_t mid=lo+(hi-lo)/2u;
        unsigned pos=(mid*XGBA_R52_ROW)%XGBA_R52_PAGE;
        unsigned page=(mid*XGBA_R52_ROW)/XGBA_R52_PAGE;
        uint32_t candidate;
        if(!XgbaR52ReadIndexPage(r,page))return 0;
        candidate=XgbaR49Le32(r->scratch+pos);
        if(candidate<source_key)lo=mid+1u;else hi=mid;
    }
    if(lo==r->indexed_maps || !XgbaR52ReadIndexPage(r,
                  (lo*XGBA_R52_ROW)/XGBA_R52_PAGE))return 0;
    p=r->scratch+(lo*XGBA_R52_ROW)%XGBA_R52_PAGE;
    if(XgbaR49Le32(p)!=source_key ||
       XgbaR49Le32(p+28u)!=XgbaR49Crc32(p,28u))return 0;
    next.key=source_key;
    next.version=p[4];next.border_width=p[5];
    next.border_height=p[6];next.original_extra=p[7];
    next.tiles_in_primary=XgbaR49Le16(p+8);
    next.metatiles_in_primary=XgbaR49Le16(p+10);
    next.palettes_in_primary=p[12];next.attribute_bytes=p[13];
    next.flags=p[14];next.compression_flags=p[15];
    next.source_layout_offset=XgbaR49Le32(p+16);
    next.primary_tileset_offset=XgbaR49Le32(p+20);
    next.secondary_tileset_offset=XgbaR49Le32(p+24);
    next.original_row_crc=XgbaR49Le32(p+28);
    if(next.version>2u || !((next.version==0u &&
         next.tiles_in_primary==512u && next.metatiles_in_primary==512u &&
         next.palettes_in_primary==6u && next.attribute_bytes==2u) ||
        ((next.version==1u || next.version==2u) &&
         next.tiles_in_primary==640u && next.metatiles_in_primary==640u &&
         next.palettes_in_primary==7u && next.attribute_bytes==4u)))
        return 0;
    if(!(next.flags & XGBA_R52_FLAG_PROFILE_SUPPORTED) ||
       next.flags & ~(XGBA_R52_FLAG_PROFILE_SUPPORTED|XGBA_R52_FLAG_WIDE_PRIMARY))
        return 0;
    if(next.version==1u && (!next.border_width || !next.border_height))
        return 0;
    if(!next.source_layout_offset ||
       !next.primary_tileset_offset || !next.secondary_tileset_offset)
        return 0;
    *out=next;
    return 1;
}
/* All original graphics remain external. This validates only semantics:
 * a source graphics installer must separately attest the exact original
 * 16-bit tile bytes, original 4bpp graphics, palettes and collision data. */
static inline uint16_t XgbaR52NativePrimarySplit(const struct XgbaR52MapProfile *p)
{
    return p ? p->metatiles_in_primary : 0u;
}
static inline int XgbaR52TranslateAttribute(const struct XgbaR52MapProfile *p,
                                             uint32_t original,uint16_t *native)
{
    unsigned behavior,layer;
    if(!p || !native)return 0;
    if(p->version==0u) {
        if(original>UINT16_MAX)return 0;
        *native=(uint16_t)original;
        return 1;
    }
    /* FRLG-family 32-bit behavior has 9 bits; vanilla Emerald's behavior
     * is 8 bits. High values cannot be squeezed without silently changing
     * gameplay, so refuse until native behavior ABI is widened. */
    behavior=original&0x1ffu;
    layer=(original>>29u)&3u;
    if(behavior>255u || layer>2u)return 0;
    *native=(uint16_t)(behavior | (layer<<12u));
    return 1;
}
#endif
