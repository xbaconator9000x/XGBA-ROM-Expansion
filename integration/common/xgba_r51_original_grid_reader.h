/* R51 — original 3-ROM world geometry into real Emerald field map cells.
 * Complete source maps are held privately in SHA-backed 16 KiB host pages,
 * indexed by (world, original map group, original map ID). This adapter
 * stages the exact original 16-bit grid and 8-byte border, including every
 * metatile collision/elevation bit. It NEVER fabricates missing graphics.
 *
 * The guest output buffer must be caller-owned and remain stable throughout
 * Emerald's map/camera lifetime. The 16 KiB scratch is LEASED, never stacked
 * or permanently allocated. Loading a new grid requires a faded transition
 * with the old field renderer released, not a source-ID button press.
 */
#ifndef XGBA_R51_ORIGINAL_GRID_READER_H
#define XGBA_R51_ORIGINAL_GRID_READER_H
#include "xgba_r49_full_original_map_events.h"
#include <stdint.h>
#include <string.h>
#define XGBA_R51_PAGE_BYTES 16384u
#define XGBA_R51_INDEX_ROW_BYTES 32u
#define XGBA_R51_ALL_SOURCE_MAPS 2856u
#define XGBA_R51_MAX_GUEST_GRID 5600u
#define XGBA_R51_GRID_BORDER_BYTES 8u
#define XGBA_R51_INVALID_PAGE UINT16_MAX

typedef int (*XgbaR51Fetch)(void *context,const char *id,
                             uint8_t *target,uint16_t size);
struct XgbaR51Reader {
    XgbaR51Fetch fetch;
    void *ctx;
    uint8_t *scratch;
    uint32_t indexed_maps;
    uint16_t cached_index_page;
    uint32_t fetched_pages;
};
struct XgbaR51IndexRow {
    uint32_t key;
    uint16_t width,height;
    uint32_t byte_offset,grid_bytes;
    uint32_t original_grid_offset,original_border_offset,crc;
    uint32_t original_header_offset;
};
struct XgbaR51NativeGeometry {
    uint32_t source_key;
    uint32_t original_grid_offset,original_border_offset,original_header_offset;
    uint16_t width,height,grid_bytes;
    uint8_t valid;
    uint8_t alignment_padding;
    /* Naturally 4-byte-aligned; 5600 includes the map border. */
    uint32_t raw_aligned[XGBA_R51_MAX_GUEST_GRID/4u];
};
#define XgbaR51NativeBytes(g) ((uint8_t *)(g)->raw_aligned)
static inline uint16_t XgbaR51LE16(const uint8_t *p){return XgbaR49Le16(p);}
static inline uint32_t XgbaR51LE32(const uint8_t *p){return XgbaR49Le32(p);}
static inline int XgbaR51FetchPage(struct XgbaR51Reader *r,unsigned kind,unsigned page)
{
    const char *prefix=kind?"r51.grid.":"r51.index.";
    char id[32];unsigned len=0,i,digits=kind?5u:3u;
    if(!r || !r->fetch || !r->scratch || kind>1u ||
       page>=(kind?100000u:1000u))return 0;
    if(!kind && r->cached_index_page==page)return 1;
    r->cached_index_page=XGBA_R51_INVALID_PAGE;
    while(prefix[len]){if(len>=sizeof(id)-digits-1u)return 0;id[len]=prefix[len];len++;}
    for(i=digits;i>0u;i--){
        unsigned power=1u,j;
        for(j=1u;j<i;j++)power*=10u;
        id[len++]=(char)('0'+((page/power)%10u));
    }
    id[len]=0;
    if(r->fetch(r->ctx,id,r->scratch,XGBA_R51_PAGE_BYTES)!=1)return 0;
    ++r->fetched_pages;
    if(!kind)r->cached_index_page=(uint16_t)page;
    return 1;
}
static inline int XgbaR51FindSourceMap(struct XgbaR51Reader *r,
                                  uint32_t key,struct XgbaR51IndexRow *out)
{
    uint32_t lo=0,hi;
    const uint8_t *p;
    if(!r || !out || !r->indexed_maps || r->indexed_maps>65535u ||
       key>>24u || ((key>>16u)&255u)>2u)return 0;
    hi=r->indexed_maps;
    while(lo<hi){
        uint32_t mid=lo+(hi-lo)/2u;
        unsigned offset=(mid*XGBA_R51_INDEX_ROW_BYTES)%XGBA_R51_PAGE_BYTES;
        unsigned page=(mid*XGBA_R51_INDEX_ROW_BYTES)/XGBA_R51_PAGE_BYTES;
        uint32_t candidate;
        if(!XgbaR51FetchPage(r,0,page))return 0;
        candidate=XgbaR51LE32(r->scratch+offset);
        if(candidate<key)lo=mid+1u;else hi=mid;
    }
    if(lo>=r->indexed_maps ||
       !XgbaR51FetchPage(r,0,
          (lo*XGBA_R51_INDEX_ROW_BYTES)/XGBA_R51_PAGE_BYTES))return 0;
    p=r->scratch+(lo*XGBA_R51_INDEX_ROW_BYTES)%XGBA_R51_PAGE_BYTES;
    if(XgbaR51LE32(p)!=key)return 0;
    out->key=key;
    out->width=XgbaR51LE16(p+4u);
    out->height=XgbaR51LE16(p+6u);
    out->byte_offset=XgbaR51LE32(p+8u);
    out->grid_bytes=XgbaR51LE32(p+12u);
    out->original_grid_offset=XgbaR51LE32(p+16u);
    out->original_border_offset=XgbaR51LE32(p+20u);
    out->crc=XgbaR51LE32(p+24u);
    out->original_header_offset=XgbaR51LE32(p+28u);
    if(!out->width || !out->height ||
       (uint64_t)out->width*out->height*2u!=out->grid_bytes ||
       (uint64_t)out->grid_bytes+XGBA_R51_GRID_BORDER_BYTES>UINT32_MAX ||
       out->byte_offset>UINT32_MAX-out->grid_bytes-XGBA_R51_GRID_BORDER_BYTES)
        return 0;
    return 1;
}
static inline int XgbaR51StageOriginalGrid(struct XgbaR51Reader *reader,
        uint32_t source_key,struct XgbaR51NativeGeometry *out)
{
    struct XgbaR51IndexRow entry;
    uint32_t current,remain,got=0u,total,crc;
    uint8_t *dst;
    if(!reader || !out || out->valid)return 0;
    if(!XgbaR51FindSourceMap(reader,source_key,&entry))return 0;
    total=entry.grid_bytes+XGBA_R51_GRID_BORDER_BYTES;
    /* Real original Emerald's backup/camera grid must have capacity. Never
     * silently shrink, reshape or omit any preserved source map. */
    if(total>XGBA_R51_MAX_GUEST_GRID ||
       (uint64_t)(entry.width+15u)*(entry.height+14u)>0x2800u)
        return 0;
    dst=XgbaR51NativeBytes(out);
    current=entry.byte_offset;remain=total;
    while(remain){
        unsigned page=current/XGBA_R51_PAGE_BYTES;
        unsigned offset=current%XGBA_R51_PAGE_BYTES;
        unsigned step=XGBA_R51_PAGE_BYTES-offset;
        if(step>remain)step=remain;
        if(!XgbaR51FetchPage(reader,1u,page))return 0;
        memcpy(dst+got,reader->scratch+offset,step);
        current+=step;got+=step;remain-=step;
    }
    crc=XgbaR49Crc32(dst,total);
    if(crc!=entry.crc)return 0;
    out->source_key=source_key;
    out->width=entry.width;out->height=entry.height;
    out->grid_bytes=(uint16_t)entry.grid_bytes;
    out->original_grid_offset=entry.original_grid_offset;
    out->original_border_offset=entry.original_border_offset;
    out->original_header_offset=entry.original_header_offset;
    out->valid=1u;
    return 1;
}
static inline void XgbaR51InvalidateGeometry(struct XgbaR51NativeGeometry *g)
{
    if(g)g->valid=0u;
}
#endif
