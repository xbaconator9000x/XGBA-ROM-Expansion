/* R46: 16 KiB on-demand native GBA lookup of 2,856 original world map
 * identities and 7,146 warp records without placing their 103 KiB complete
 * index into 256 KiB guest EWRAM.
 *
 * Callback must fetch each r46.map.NNN or r46.warp.NNN immutable external
 * XGBA page via XgbaGuestFetch and independently SHA-check it in the patched
 * host provider. 16 KiB scratch buffer and verified lease belong to caller.
 * It MUST NOT be reused while another game/battle borrows the same arena.
 */
#ifndef XGBA_R46_PAGED_WARPS_H
#define XGBA_R46_PAGED_WARPS_H
#include "xgba_r46_source_warps.h"

#define XGBA_R46_PAGE_BYTES 16384u
#define XGBA_R46_MAP_RECORD_BYTES 16u
#define XGBA_R46_WARP_RECORD_BYTES 8u
#define XGBA_R46_MAP_KIND 0u
#define XGBA_R46_WARP_KIND 1u
#define XGBA_R46_CACHE_EMPTY 65535u

typedef int (*XgbaR46FetchPage)(void *ctx,const char *resource,
                                uint8_t *target,uint16_t exact_bytes);
struct XgbaR46PagedIndex {
    XgbaR46FetchPage fetch;
    void *context;
    uint8_t *scratch;
    uint16_t scratch_bytes;
    uint16_t map_count;
    uint16_t warp_count;
    uint16_t cached_page, cached_kind;
    uint16_t physical_reads;
    uint16_t cache_hits;
};
_Static_assert(sizeof(struct XgbaR46Map)==16,
               "R46 original source map ABI must stay packed 16 bytes");
_Static_assert(sizeof(struct XgbaR46Warp)==8,
               "R46 original warp ABI must stay 8 bytes");

static inline void XgbaR46CacheReset(struct XgbaR46PagedIndex *index)
{
    if(index){
        index->cached_page=XGBA_R46_CACHE_EMPTY;
        index->cached_kind=XGBA_R46_CACHE_EMPTY;
    }
}
static inline int XgbaR46LoadRecord(struct XgbaR46PagedIndex *index,
                                    unsigned kind,unsigned record,void *output)
{
    unsigned size,records,offset,page,inside,total,wanted;
    char id[16];
    const char *prefix=kind==XGBA_R46_MAP_KIND?"r46.map.":"r46.warp.";
    unsigned i=0u;
    uint8_t *dst=(uint8_t *)output;
    if(!index || !index->fetch || !index->scratch || !output ||
       index->scratch_bytes<XGBA_R46_PAGE_BYTES || kind>1u ||
       index->map_count==0u || index->cached_kind==XGBA_R46_CACHE_EMPTY-1u)
        return 0;
    size=kind==XGBA_R46_MAP_KIND?XGBA_R46_MAP_RECORD_BYTES:XGBA_R46_WARP_RECORD_BYTES;
    records=kind==XGBA_R46_MAP_KIND?index->map_count:index->warp_count;
    if(record>=records)return 0;
    offset=record*size;
    total=records*size;
    page=offset/XGBA_R46_PAGE_BYTES;
    inside=offset%XGBA_R46_PAGE_BYTES;
    wanted=total-page*XGBA_R46_PAGE_BYTES;
    if(wanted>XGBA_R46_PAGE_BYTES)wanted=XGBA_R46_PAGE_BYTES;
    if(inside+size>wanted || page>999u)return 0;
    if(index->cached_page!=page || index->cached_kind!=kind){
        for(i=0u;prefix[i] && i<11u;i++)id[i]=prefix[i];
        if(prefix[i])return 0;
        id[i++]=(char)('0'+(page/100u)%10u);
        id[i++]=(char)('0'+(page/10u)%10u);
        id[i++]=(char)('0'+page%10u);
        id[i]=0;
        /* Treat loading as a destructive operation and explicitly
         * invalidate cache identity BEFORE invoking the guest MMIO fetch. */
        XgbaR46CacheReset(index);
        if(index->fetch(index->context,id,index->scratch,(uint16_t)wanted)!=1)
            return 0;
        index->cached_page=(uint16_t)page;
        index->cached_kind=(uint16_t)kind;
        index->physical_reads++;
    }else index->cache_hits++;
    for(i=0u;i<size;i++)dst[i]=index->scratch[inside+i];
    return 1;
}
static inline int XgbaR46FindMapPaged(struct XgbaR46PagedIndex *reader,
                                      uint32_t key,struct XgbaR46Map *output)
{
    unsigned lo=0u,hi,mid;
    struct XgbaR46Map item;
    if(!reader || !reader->map_count || XgbaR46Source(key)>=XGBA_R46_WORLDS ||
       (key&UINT32_C(0xff000000)))return -1;
    hi=reader->map_count;
    while(lo<hi){
        mid=lo+(hi-lo)/2u;
        if(!XgbaR46LoadRecord(reader,XGBA_R46_MAP_KIND,mid,&item))
            return -1;
        if(item.key<key)lo=mid+1u;else hi=mid;
    }
    if(lo>=reader->map_count ||
       !XgbaR46LoadRecord(reader,XGBA_R46_MAP_KIND,lo,&item) ||
       item.key!=key || !item.width || !item.height)return -1;
    if(output)*output=item;
    return (int)lo;
}
static inline enum XgbaR46RouteStatus XgbaR46TravelPaged(
    struct XgbaR46PagedIndex *reader,struct XgbaR46Location *position,
    unsigned original_warp_index,const struct XgbaR46Portal *portal)
{
    struct XgbaR46Map source,destination;
    struct XgbaR46Warp from,to;
    uint32_t target_key;
    unsigned destination_warp;
    if(!reader || !position || XgbaR46Source(position->key)>=XGBA_R46_WORLDS)
        return XGBA_R46_ROUTE_MISSING_SOURCE;
    if(XgbaR46FindMapPaged(reader,position->key,&source)<0)
        return XGBA_R46_ROUTE_MAP_HOLE;
    if(original_warp_index>=source.warp_count ||
       (unsigned)source.first_warp+original_warp_index>=reader->warp_count ||
       !XgbaR46LoadRecord(reader,XGBA_R46_WARP_KIND,
                          (unsigned)source.first_warp+original_warp_index,&from))
        return XGBA_R46_ROUTE_WARP_NOT_PRESENT;
    if(from.x<0 || from.y<0 || from.x>=source.width || from.y>=source.height)
        return XGBA_R46_ROUTE_OUT_OF_RANGE;
    if(portal){
        if(portal->source_key!=position->key ||
           portal->source_warp_index!=original_warp_index ||
           XgbaR46Source(portal->target_key)>=XGBA_R46_WORLDS ||
           portal->reserved)return XGBA_R46_ROUTE_BAD_PORTAL;
        target_key=portal->target_key;
        destination_warp=portal->target_warp_index;
    }else{
        if(from.destination_group==127u && from.destination_map==127u)
            return XGBA_R46_ROUTE_DYNAMIC_WARP;
        target_key=XgbaR46MapKey((uint8_t)XgbaR46Source(position->key),
                                 from.destination_group,from.destination_map);
        destination_warp=from.destination_warp;
    }
    if(XgbaR46FindMapPaged(reader,target_key,&destination)<0)
        return XGBA_R46_ROUTE_MAP_HOLE;
    if(destination_warp>=destination.warp_count ||
       (unsigned)destination.first_warp+destination_warp>=reader->warp_count ||
       !XgbaR46LoadRecord(reader,XGBA_R46_WARP_KIND,
                         (unsigned)destination.first_warp+destination_warp,&to))
        return XGBA_R46_ROUTE_TARGET_WARP_INVALID;
    if(to.x<0 || to.y<0 || to.x>=destination.width ||
       to.y>=destination.height)return XGBA_R46_ROUTE_OUT_OF_RANGE;
    position->key=target_key;
    position->x=(uint16_t)to.x;
    position->y=(uint16_t)to.y;
    position->elevation=to.elevation;
    position->warp_index=(uint8_t)destination_warp;
    return XGBA_R46_ROUTE_OK;
}
#endif
