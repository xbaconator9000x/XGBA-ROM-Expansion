/* R73 read-only original SHA-backed R49 warp admission; source-owned.
 * Never interpret one game's group/map as another game's map identifier.
 * Both event pages and grid profiles must have been verified by caller.
 * No guest state changes or new permanent EWRAM.
 */
#ifndef XGBA_R73_SOURCE_WARP_PREFLIGHT_H
#define XGBA_R73_SOURCE_WARP_PREFLIGHT_H
#include <stdint.h>
#include <stddef.h>
#define XGBA_R73_WARP_BYTES 8u
enum XgbaR73WarpStatus {
    XGBA_R73_OK=0,
    XGBA_R73_BAD_ARGUMENT,
    XGBA_R73_BAD_SOURCE_COORD,
    XGBA_R73_DYNAMIC_WARP,
    XGBA_R73_WORLD_OR_MAP_COLLISION,
    XGBA_R73_TARGET_WARP_NOT_PRESENT,
    XGBA_R73_BAD_TARGET_COORD
};
struct XgbaR73SourceWarpRoute {
    uint32_t source_key,target_key;
    uint16_t source_x,source_y,target_x,target_y;
    uint8_t source_index,target_index,source_elevation,target_elevation;
};
static inline uint16_t XgbaR73Le16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0]|((uint16_t)p[1]<<8));
}
static inline uint32_t XgbaR73ScopedKey(unsigned world,unsigned group,unsigned map)
{
    return ((uint32_t)world<<16u)|((uint32_t)group<<8u)|map;
}
static inline enum XgbaR73WarpStatus XgbaR73ProveOriginalWarp(
    uint32_t source_key,unsigned sw,unsigned sh,
    const uint8_t *source_warps,unsigned source_count,unsigned source_index,
    uint32_t target_key,unsigned tw,unsigned th,
    const uint8_t *target_warps,unsigned target_count,
    struct XgbaR73SourceWarpRoute *out)
{
    const uint8_t *source,*target;
    uint32_t expected_target;
    int16_t sx,sy,tx,ty;
    unsigned world=(source_key>>16u)&255u;
    struct XgbaR73SourceWarpRoute next={0};
    if(!out || !source_warps || !target_warps ||
       (source_key&UINT32_C(0xff000000)) ||
       (target_key&UINT32_C(0xff000000)) || world>=3u ||
       !sw || !sh || !tw || !th || sw>2048u || sh>2048u ||
       tw>2048u || th>2048u ||
       !source_count || !target_count ||
       source_count>255u || target_count>255u ||
       source_index>=source_count)
        return XGBA_R73_BAD_ARGUMENT;
    source=source_warps+source_index*XGBA_R73_WARP_BYTES;
    sx=(int16_t)XgbaR73Le16(source);
    sy=(int16_t)XgbaR73Le16(source+2u);
    if(sx<0 || sy<0 || (unsigned)sx>=sw || (unsigned)sy>=sh)
        return XGBA_R73_BAD_SOURCE_COORD;
    if(source[6]==127u && source[7]==127u)
        return XGBA_R73_DYNAMIC_WARP;
    expected_target=XgbaR73ScopedKey(world,source[7],source[6]);
    if(expected_target!=target_key)
        return XGBA_R73_WORLD_OR_MAP_COLLISION;
    if(source[5]>=target_count)
        return XGBA_R73_TARGET_WARP_NOT_PRESENT;
    target=target_warps+(unsigned)source[5]*XGBA_R73_WARP_BYTES;
    tx=(int16_t)XgbaR73Le16(target);
    ty=(int16_t)XgbaR73Le16(target+2u);
    if(tx<0 || ty<0 || (unsigned)tx>=tw || (unsigned)ty>=th)
        return XGBA_R73_BAD_TARGET_COORD;
    next.source_key=source_key;next.target_key=target_key;
    next.source_x=(uint16_t)sx;next.source_y=(uint16_t)sy;
    next.target_x=(uint16_t)tx;next.target_y=(uint16_t)ty;
    next.source_index=(uint8_t)source_index;
    next.target_index=source[5];
    next.source_elevation=source[4];
    next.target_elevation=target[4];
    *out=next; /* atomic publication ONLY after all source validation */
    return XGBA_R73_OK;
}
#endif
