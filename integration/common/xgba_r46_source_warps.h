/* R46: source-aware ORIGINAL Pokémon map/warp routing, engine-facing ABI.
 *
 * This is a native GBA-compatible resolver for the Emerald-family overworld;
 * it DOES NOT pretend the user has already navigated cross-world maps.
 *
 * The same numeric 0:9 in original Emerald and Team Rocket 3.06 is NOT the
 * same location; never key either map or save location by (group, map) alone.
 * Explicit portal transitions are separate from original in-source warps.
 *
 * All route tables are immutable ROM/sidecar-index metadata. Nothing
 * allocates RAM or writes into Emerald Flash/saveblocks on its own.
 */
#ifndef XGBA_R46_SOURCE_WARPS_H
#define XGBA_R46_SOURCE_WARPS_H
#include <stdint.h>
#include <stddef.h>
#include <limits.h>

#define XGBA_R46_WORLD_EMERALD 0u
#define XGBA_R46_WORLD_ROCKET 1u
#define XGBA_R46_WORLD_HEART_SOUL 2u
#define XGBA_R46_WORLDS 3u
#define XGBA_R46_NO_WARP 255u
#define XGBA_R46_BAD_INDEX UINT16_MAX
#define XGBA_R46_SAVE_MAGIC UINT32_C(0x58473634)

enum XgbaR46RouteStatus {
    XGBA_R46_ROUTE_OK = 0,
    XGBA_R46_ROUTE_MISSING_SOURCE = 1,
    XGBA_R46_ROUTE_MAP_HOLE = 2,
    XGBA_R46_ROUTE_WARP_NOT_PRESENT = 3,
    XGBA_R46_ROUTE_TARGET_WARP_INVALID = 4,
    XGBA_R46_ROUTE_OUT_OF_RANGE = 5,
    XGBA_R46_ROUTE_DYNAMIC_WARP = 6,
    XGBA_R46_ROUTE_BAD_PORTAL = 7
};

struct XgbaR46Map {
    uint32_t key;              /* (source<<16) | (group<<8) | map */
    uint16_t width, height;
    uint16_t first_warp, warp_count;
    uint32_t original_header_offset; /* source-local, not global GBA addr */
};
struct XgbaR46Warp {
    int16_t x, y;
    uint8_t elevation, destination_warp;
    uint8_t destination_map, destination_group;
};
struct XgbaR46Location {
    uint32_t key;
    uint16_t x, y;
    uint8_t elevation, warp_index;
};
struct XgbaR46Portal {
    uint32_t source_key, target_key;
    uint8_t source_warp_index, target_warp_index;
    uint16_t reserved;
};
struct XgbaR46SaveLocation {
    uint32_t magic;
    uint32_t key;
    uint16_t x, y;
    uint8_t elevation, warp_index;
    uint16_t checksum;
};

static inline uint32_t XgbaR46MapKey(uint8_t source,uint8_t group,uint8_t map)
{
    return ((uint32_t)source<<16u)|((uint32_t)group<<8u)|map;
}
static inline unsigned XgbaR46Source(uint32_t key){return (key>>16u)&255u;}
static inline unsigned XgbaR46Group(uint32_t key){return (key>>8u)&255u;}
static inline unsigned XgbaR46MapNumber(uint32_t key){return key&255u;}

static inline int XgbaR46FindMap(const struct XgbaR46Map *maps,
                                  size_t count,uint32_t key)
{
    size_t low=0,high=count;
    if(!maps || XgbaR46Source(key)>=XGBA_R46_WORLDS ||
       (key&UINT32_C(0xff000000)))return -1;
    while(low<high){
        size_t mid=low+(high-low)/2u;
        if(maps[mid].key<key)low=mid+1u;
        else high=mid;
    }
    if(low==count || maps[low].key!=key || low>INT_MAX)return -1;
    return (int)low;
}
static inline int XgbaR46ValidMap(const struct XgbaR46Map *maps,size_t count,
                                   const struct XgbaR46Warp *warps,size_t warp_count)
{
    size_t i;
    if(!maps || (!warps && warp_count) || count>UINT16_MAX ||
       warp_count>UINT16_MAX)return 0;
    for(i=0;i<count;i++){
        const struct XgbaR46Map *m=&maps[i];
        if(XgbaR46Source(m->key)>=XGBA_R46_WORLDS ||
           (m->key&UINT32_C(0xff000000)) ||
           (i && m->key<=maps[i-1].key) ||
           !m->width || !m->height ||
           m->first_warp>warp_count ||
           m->warp_count>warp_count-m->first_warp)
            return 0;
    }
    return 1;
}
static inline enum XgbaR46RouteStatus XgbaR46Target(
    const struct XgbaR46Map *maps,size_t count,
    const struct XgbaR46Warp *warps,size_t warp_count,
    struct XgbaR46Location *position,
    unsigned warp_index,const struct XgbaR46Portal *explicit_portal)
{
    int source, dest;
    const struct XgbaR46Map *m,*t;
    const struct XgbaR46Warp *w,*arrival;
    uint32_t destination_key;
    unsigned arrival_index;
    if(!position || XgbaR46Source(position->key)>=XGBA_R46_WORLDS)
        return XGBA_R46_ROUTE_MISSING_SOURCE;
    source=XgbaR46FindMap(maps,count,position->key);
    if(source<0)return XGBA_R46_ROUTE_MAP_HOLE;
    m=&maps[source];
    if(warp_index>=m->warp_count ||
       (size_t)m->first_warp+warp_index>=warp_count)
        return XGBA_R46_ROUTE_WARP_NOT_PRESENT;
    w=&warps[(size_t)m->first_warp+warp_index];
    if(w->x<0 || w->y<0 || w->x>=m->width || w->y>=m->height)
        return XGBA_R46_ROUTE_OUT_OF_RANGE;
    if(explicit_portal){
        /* Portal is an explicit game-authored bridge. Native source warps
         * are NEVER auto-reinterpreted as cross-world shortcuts. */
        if(explicit_portal->source_key!=m->key ||
           explicit_portal->source_warp_index!=warp_index ||
           XgbaR46Source(explicit_portal->target_key)>=XGBA_R46_WORLDS ||
           explicit_portal->reserved)
            return XGBA_R46_ROUTE_BAD_PORTAL;
        destination_key=explicit_portal->target_key;
        arrival_index=explicit_portal->target_warp_index;
    }else{
        if(w->destination_group==127u && w->destination_map==127u)
            return XGBA_R46_ROUTE_DYNAMIC_WARP;
        destination_key=XgbaR46MapKey((uint8_t)XgbaR46Source(m->key),
                    w->destination_group,w->destination_map);
        arrival_index=w->destination_warp;
    }
    dest=XgbaR46FindMap(maps,count,destination_key);
    if(dest<0)return XGBA_R46_ROUTE_MAP_HOLE;
    t=&maps[dest];
    if(arrival_index>=t->warp_count ||
       (size_t)t->first_warp+arrival_index>=warp_count)
        return XGBA_R46_ROUTE_TARGET_WARP_INVALID;
    arrival=&warps[(size_t)t->first_warp+arrival_index];
    if(arrival->x<0 || arrival->y<0 ||
       arrival->x>=t->width || arrival->y>=t->height)
        return XGBA_R46_ROUTE_OUT_OF_RANGE;
    /* Commit atomically ONLY after all map keys, source identity, indices,
     * source-local original ROM destination and bounds are verified. */
    position->key=destination_key;
    position->x=(uint16_t)arrival->x;
    position->y=(uint16_t)arrival->y;
    position->elevation=arrival->elevation;
    position->warp_index=(uint8_t)arrival_index;
    return XGBA_R46_ROUTE_OK;
}
static inline uint16_t XgbaR46SaveChecksum(const struct XgbaR46SaveLocation *s)
{
    uint32_t x;
    if(!s)return 0;
    x=UINT32_C(0xa453bc71);
    x^=s->magic;
    x^=s->key*UINT32_C(0x9e3779b1);
    x^=((uint32_t)s->x<<16)|s->y;
    x^=((uint32_t)s->elevation<<8)|s->warp_index;
    return (uint16_t)((x>>16)^x);
}
static inline int XgbaR46EncodeLocation(
    const struct XgbaR46Map *maps,size_t count,
    const struct XgbaR46Location *pos,struct XgbaR46SaveLocation *dest)
{
    int index;
    if(!pos||!dest)return 0;
    index=XgbaR46FindMap(maps,count,pos->key);
    if(index<0 || pos->x>=maps[index].width ||
       pos->y>=maps[index].height)return 0;
    dest->magic=XGBA_R46_SAVE_MAGIC;
    dest->key=pos->key;
    dest->x=pos->x;
    dest->y=pos->y;
    dest->elevation=pos->elevation;
    dest->warp_index=pos->warp_index;
    dest->checksum=XgbaR46SaveChecksum(dest);
    return 1;
}
static inline int XgbaR46DecodeLocation(
    const struct XgbaR46Map *maps,size_t count,
    const struct XgbaR46SaveLocation *saved,struct XgbaR46Location *pos)
{
    int index;
    if(!saved||!pos||saved->magic!=XGBA_R46_SAVE_MAGIC ||
       saved->checksum!=XgbaR46SaveChecksum(saved))return 0;
    index=XgbaR46FindMap(maps,count,saved->key);
    if(index<0 || saved->x>=maps[index].width ||
       saved->y>=maps[index].height)return 0;
    pos->key=saved->key;
    pos->x=saved->x;pos->y=saved->y;
    pos->elevation=saved->elevation;
    pos->warp_index=saved->warp_index;
    return 1;
}
#endif
