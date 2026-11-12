/* XGBA R31: locate external map resources by the ORIGINAL game's identity.
 * The game still uses its (mapGroup, mapNum), map headers and layout pointers.
 * Only opt-in externally backed resources appear here. Everything else
 * remains on the unmodified original resolver path. No replacement map IDs.
 *
 * The sorted lookup array is held in ROM. No catalogue-sized EWRAM array,
 * map-number rewriting, per-map allocation or new physical cache slots.
 */
#ifndef XGBA_ORIGINAL_MAP_CATALOG_H
#define XGBA_ORIGINAL_MAP_CATALOG_H
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#define XGBA_CATALOG_NO_NEIGHBOR UINT16_MAX
struct XgbaOriginalMapResource {
    uint16_t group, map, width, height;
    uint32_t packed_bytes;
    const char *resource_id;
    uint16_t prefetch_index;
};
struct XgbaOriginalMapLocator {
    uint32_t original_identity;
    uint16_t resource_index;
};
static inline uint32_t XgbaOriginalMapIdentity(uint16_t group,uint16_t map)
{
    return ((uint32_t)group<<16)|(uint32_t)map;
}
static inline int XgbaOriginalMapCatalogFind(
    const struct XgbaOriginalMapLocator *ordered,size_t n,
    uint16_t group,uint16_t map)
{
    size_t lo=0u,hi=n;
    const uint32_t key=XgbaOriginalMapIdentity(group,map);
    if(!ordered)return -1;
    while(lo<hi) {
        size_t mid=lo+(hi-lo)/2u;
        if(ordered[mid].original_identity<key)lo=mid+1u;
        else hi=mid;
    }
    if(lo==n || ordered[lo].original_identity!=key)return -1;
    return (int)ordered[lo].resource_index;
}
static inline int XgbaOriginalMapCatalogValidate(
    const struct XgbaOriginalMapResource *items,
    const struct XgbaOriginalMapLocator *ordered,size_t n,
    uint32_t max_pack)
{
    size_t i;
    if(!items || !ordered || !n || n>=UINT16_MAX || !max_pack)
        return 0;
    for(i=0;i<n;++i) {
        const struct XgbaOriginalMapResource *r=&items[i];
        const char *p=r->resource_id;
        size_t chars=0u;
        uint64_t grid_bytes=(uint64_t)r->width*r->height*2u;
        if(!r->width || !r->height || !r->packed_bytes ||
           r->packed_bytes>max_pack || grid_bytes+40u>r->packed_bytes ||
           (r->prefetch_index!=XGBA_CATALOG_NO_NEIGHBOR &&
            (r->prefetch_index>=n || r->prefetch_index==i)) ||
           !p)return 0;
        while(p[chars] && chars<32u) {
            const unsigned char c=(unsigned char)p[chars];
            if(!((c>='a' && c<='z')||(c>='A' && c<='Z')||
                 (c>='0' && c<='9')||c=='.'||c=='_'||c=='-'))
                return 0;
            ++chars;
        }
        if(!chars || chars>31u || p[chars])return 0;
        if(ordered[i].resource_index>=n ||
           ordered[i].original_identity!=
             XgbaOriginalMapIdentity(items[ordered[i].resource_index].group,
                                     items[ordered[i].resource_index].map) ||
           (i && ordered[i].original_identity<=
                     ordered[i-1u].original_identity))
            return 0;
    }
    return 1;
}
#endif
