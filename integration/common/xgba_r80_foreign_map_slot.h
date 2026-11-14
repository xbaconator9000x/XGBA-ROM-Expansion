/* R80 original Rocket source key -> actual native Emerald rendering slot.
 * Original (world/group/map) NEVER indexes gMapGroups as if Emerald owned it.
 * The internal slot is 0:9; actual original source identity is retained.
 */
#ifndef XGBA_R80_FOREIGN_MAP_SLOT_H
#define XGBA_R80_FOREIGN_MAP_SLOT_H
#include <stdint.h>
#include "xgba_r73_source_warp_preflight.h"
#define XGBA_R80_NATIVE_GROUP 0u
#define XGBA_R80_NATIVE_MAP 9u
struct XgbaR80DoorPlan {
    uint32_t original_from,original_to;
    uint16_t original_x,original_y;
    uint8_t native_group,native_map;
    uint8_t source_world,source_group,source_map;
};
static inline int XgbaR80SupportedFirstHopMap(uint32_t key)
{
    unsigned world=(key>>16u)&255u,group=(key>>8u)&255u,map=key&255u;
    return !(key>>24u) && world==1u &&
        ((group==0u && map==9u) ||
         (group==35u && (map==0u || map==2u || map==4u)));
}
static inline int XgbaR80PlanFirstHop(
    const struct XgbaR73SourceWarpRoute *route,struct XgbaR80DoorPlan *out)
{
    struct XgbaR80DoorPlan p={0};
    if(!out || !route || !XgbaR80SupportedFirstHopMap(route->source_key) ||
       !XgbaR80SupportedFirstHopMap(route->target_key) ||
       route->source_key==route->target_key ||
       route->target_x>127u || route->target_y>127u ||
       ((route->source_key>>16u)&255u)!=((route->target_key>>16u)&255u))
        return 0;
    p.original_from=route->source_key;
    p.original_to=route->target_key;
    p.original_x=route->target_x;p.original_y=route->target_y;
    p.native_group=XGBA_R80_NATIVE_GROUP;p.native_map=XGBA_R80_NATIVE_MAP;
    p.source_world=(uint8_t)((route->target_key>>16u)&255u);
    p.source_group=(uint8_t)((route->target_key>>8u)&255u);
    p.source_map=(uint8_t)(route->target_key&255u);
    *out=p;return 1;
}
static inline int XgbaR80NpcVisibleAtSourceArrival(unsigned width,unsigned height,
    int center_x,int center_y,int x,int y)
{
    return x>=0 && y>=0 && center_x>=0 && center_y>=0 &&
        (unsigned)x<width && (unsigned)y<height &&
        (unsigned)center_x<width && (unsigned)center_y<height &&
        x>=center_x-7 && x<=center_x+7 &&
        y>=center_y-5 && y<=center_y+5;
}
#ifdef XGBA_R80_FOREIGN_SOURCE_ACTIVATION
int XgbaR80SpriteVisibleInSourceMap(unsigned world,unsigned group,unsigned map,
                                    unsigned width,unsigned height,int x,int y);
int XgbaR80SourceTargetAuthorized(unsigned world,unsigned group,unsigned map);
int XgbaR80SourceLocationMatchesNative(unsigned world,unsigned group,unsigned map);
int XgbaR80PendingNativeMapMatches(void);
int XgbaR80HasSourceWarpPending(void);
int XgbaR80ForeignInteriorActive(void);
unsigned XgbaR80DestinationWorld(void);
unsigned XgbaR80DestinationGroup(void);
unsigned XgbaR80DestinationMap(void);
void XgbaR80OnSourceRendererReleased(void);
void XgbaR80ConfirmRealSourceMapArrival(void);
void XgbaR80InvalidateSourceWarp(void);
#endif
#endif
