/* R49: native GBA-safe, bounded, complete three-source original map-event
 * importer. Per-map original object/NPC (24 bytes), warp (8), coord (16)
 * and background (12) event bytes are NOT interpreted or rewritten here.
 *
 * Every page is externally fetched via the existing patched XGBA provider:
 * caller supplies a verified callback (SHA-256 in host), one 16KiB arena
 * scratch buffer and a lease covering this read. Failures never expose
 * partial map event arrays or dereference foreign source-ROM script pointers.
 *
 * Caution: preservation != execution. NPC graphics, foreign script pointer
 * relocation, real map layout, collision and Fly are separate engine tasks.
 */
#ifndef XGBA_R49_FULL_ORIGINAL_MAP_EVENTS_H
#define XGBA_R49_FULL_ORIGINAL_MAP_EVENTS_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#define XGBA_R49_PAGE_BYTES 16384u
#define XGBA_R49_ALL_MAPS 2856u
#define XGBA_R49_INDEX_RECORD_BYTES 16u
#define XGBA_R49_EVENT_HEADER_BYTES 32u
#define XGBA_R49_MAX_MAP_EVENT_BYTES XGBA_R49_PAGE_BYTES
#define XGBA_R49_KIND_INDEX 0u
#define XGBA_R49_KIND_EVENTS 1u
#define XGBA_R49_INVALID_PAGE UINT16_MAX

typedef int (*XgbaR49Fetch)(void *context,const char *resource_id,
                             uint8_t *target,uint16_t length);
struct XgbaR49IndexEntry {
    uint32_t source_key;
    uint16_t page;
    uint16_t byte_offset;
    uint32_t byte_length;
    uint32_t original_header_offset;
};
struct XgbaR49OriginalEventHeader {
    char magic[4];
    uint32_t source_key;
    uint8_t objects,warps,coordinates,background;
    uint32_t original_header_offset;
    uint32_t original_events_offset;
    uint32_t crc32_original_bytes;
    uint32_t original_bytes;
    uint32_t original_map_script_offset;
};
struct XgbaR49OriginalEvents {
    uint32_t source_key;
    uint32_t original_header_offset;
    uint32_t original_events_offset;
    uint32_t original_map_script_offset;
    uint8_t object_count, warp_count,coordinate_count,background_count;
    uint32_t bytes_total;
    /* Pointers into leased buffer: stable ONLY while arena stays owned. */
    const uint8_t *objects,*warps,*coordinates,*background;
};
struct XgbaR49Reader {
    XgbaR49Fetch fetch;
    void *ctx;
    uint8_t *scratch; /* caller-owned single 16KiB EWRAM arena, not extra */
    uint32_t indexed_maps;
    uint16_t cached_index_page;
    uint16_t verified_fetches;
    uint16_t index_cache_hits;
};
_Static_assert(sizeof(struct XgbaR49IndexEntry)==16,"R49 index ABI");
_Static_assert(sizeof(struct XgbaR49OriginalEventHeader)==32,"R49 event provenance ABI");

static inline uint32_t XgbaR49Le32(const uint8_t *p)
{
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 |
          (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static inline uint16_t XgbaR49Le16(const uint8_t *p)
{
    return (uint16_t)p[0] | (uint16_t)p[1]<<8;
}
static inline uint32_t XgbaR49Crc32(const uint8_t *data,size_t length)
{
    uint32_t crc=UINT32_C(0xffffffff);
    size_t i;
    for(i=0;i<length;i++){
        unsigned bit;
        crc^=data[i];
        for(bit=0;bit<8u;bit++)
            crc=(crc>>1) ^ ((crc&1u)?UINT32_C(0xedb88320):0u);
    }
    return ~crc;
}
static inline void XgbaR49Invalidate(struct XgbaR49Reader *r)
{
    if(r)r->cached_index_page=XGBA_R49_INVALID_PAGE;
}
static inline int XgbaR49ReadPage(struct XgbaR49Reader *r,
                                  unsigned kind,unsigned page)
{
    const char *prefix=kind==XGBA_R49_KIND_INDEX?
                      "r49.index.":"r49.events.";
    unsigned i=0;
    char id[22];
    if(!r || !r->fetch || !r->scratch || kind>1u || page>999u)
        return 0;
    if(kind==XGBA_R49_KIND_INDEX &&
       r->cached_index_page==page){
        ++r->index_cache_hits;
        return 1;
    }
    /* Once an events page is fetched, a previous index-page reference
     * MUST be invalidated so binary search never reads stale event bytes. */
    XgbaR49Invalidate(r);
    while(prefix[i] && i<sizeof(id)-5u){id[i]=prefix[i];i++;}
    if(prefix[i])return 0;
    id[i++]=(char)('0'+(page/100u)%10u);
    id[i++]=(char)('0'+(page/10u)%10u);
    id[i++]=(char)('0'+page%10u);
    id[i]=0;
    if(r->fetch(r->ctx,id,r->scratch,XGBA_R49_PAGE_BYTES)!=1)
        return 0;
    if(kind==XGBA_R49_KIND_INDEX)
        r->cached_index_page=(uint16_t)page;
    ++r->verified_fetches;
    return 1;
}
static inline int XgbaR49FindSourceMap(
    struct XgbaR49Reader *r,uint32_t source_key,
    struct XgbaR49IndexEntry *result)
{
    uint32_t lo=0,hi;
    if(!r||!result||r->indexed_maps==0 ||
       r->indexed_maps>65535u ||
       source_key>>24 || ((source_key>>16)&255u)>=3u)
        return 0;
    hi=r->indexed_maps;
    while(lo<hi){
        uint32_t mid=lo+(hi-lo)/2u;
        unsigned page=(mid*XGBA_R49_INDEX_RECORD_BYTES)/XGBA_R49_PAGE_BYTES;
        unsigned pos=(mid*XGBA_R49_INDEX_RECORD_BYTES)%XGBA_R49_PAGE_BYTES;
        uint32_t candidate;
        if(!XgbaR49ReadPage(r,XGBA_R49_KIND_INDEX,page))
            return 0;
        candidate=XgbaR49Le32(r->scratch+pos);
        if(candidate<source_key)lo=mid+1u;else hi=mid;
    }
    if(lo==r->indexed_maps)return 0;
    if(!XgbaR49ReadPage(r,XGBA_R49_KIND_INDEX,
                        (lo*XGBA_R49_INDEX_RECORD_BYTES)/XGBA_R49_PAGE_BYTES))
        return 0;
    {
        const uint8_t *p=r->scratch+
            (lo*XGBA_R49_INDEX_RECORD_BYTES)%XGBA_R49_PAGE_BYTES;
        if(XgbaR49Le32(p)!=source_key)return 0;
        result->source_key=source_key;
        result->page=XgbaR49Le16(p+4);
        result->byte_offset=XgbaR49Le16(p+6);
        result->byte_length=XgbaR49Le32(p+8);
        result->original_header_offset=XgbaR49Le32(p+12);
        if(!result->byte_length ||
           result->byte_length>XGBA_R49_MAX_MAP_EVENT_BYTES ||
           result->byte_offset>XGBA_R49_PAGE_BYTES-result->byte_length)
            return 0;
    }
    return 1;
}
static inline int XgbaR49LoadOriginalMapEvents(
    struct XgbaR49Reader *r,uint32_t source_key,
    struct XgbaR49OriginalEvents *result)
{
    struct XgbaR49IndexEntry e={0};
    const uint8_t *record,*raw;
    const uint8_t lengths[4]={24u,8u,16u,12u};
    unsigned counts[4],i,offset=0u;
    uint32_t n=0u,crc;
    struct XgbaR49OriginalEvents next={0};
    if(!r||!result)return 0;
    /* Never mutate the output until all source bytes are checked. */
    if(!XgbaR49FindSourceMap(r,source_key,&e))return 0;
    if(!XgbaR49ReadPage(r,XGBA_R49_KIND_EVENTS,e.page))return 0;
    record=r->scratch+e.byte_offset;
    if(e.byte_length<XGBA_R49_EVENT_HEADER_BYTES ||
       memcmp(record,"X49E",4) ||
       XgbaR49Le32(record+4)!=source_key ||
       XgbaR49Le32(record+12)!=e.original_header_offset)
        return 0;
    for(i=0;i<4u;i++){
        counts[i]=record[8+i];
        n+=counts[i]*lengths[i];
    }
    if(n+XGBA_R49_EVENT_HEADER_BYTES!=e.byte_length ||
       XgbaR49Le32(record+24)!=n)
        return 0;
    raw=record+XGBA_R49_EVENT_HEADER_BYTES;
    crc=XgbaR49Le32(record+20);
    if(crc!=XgbaR49Crc32(raw,n))return 0;
    next.source_key=source_key;
    next.original_header_offset=e.original_header_offset;
    next.original_events_offset=XgbaR49Le32(record+16);
    next.original_map_script_offset=XgbaR49Le32(record+28);
    next.object_count=(uint8_t)counts[0];
    next.warp_count=(uint8_t)counts[1];
    next.coordinate_count=(uint8_t)counts[2];
    next.background_count=(uint8_t)counts[3];
    next.bytes_total=n;
    next.objects=raw;
    offset=counts[0]*24u;next.warps=raw+offset;
    offset+=counts[1]*8u;next.coordinates=raw+offset;
    offset+=counts[2]*16u;next.background=raw+offset;
    *result=next;
    return 1;
}
#endif
