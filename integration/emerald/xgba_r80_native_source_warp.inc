/* R80: genuine original Rocket first-hop world-qualified field route.
 * Never commit source group 35 as gMapGroups[35] in the Emerald engine.
 * Source location is transient, and not yet a Flash save namespace.
 */
#include "../common/xgba_r80_foreign_map_slot.h"
struct XgbaR80RuntimeRoute {
    u32 from,to;
    u16 x,y;
    u8 phase; /* 0 inactive, 1 native fade/source preloading, 2 real arrival */
    u8 reserved[3];
};
static EWRAM_DATA struct XgbaR80RuntimeRoute sXgbaR80Route={0};
struct XgbaR80SourceRoomProof {
    volatile u32 real_player_queued,original_room_loaded,refused_art;
    volatile u32 route_revoked,actual_original_target_key,native_slot;
};
EWRAM_DATA volatile struct XgbaR80SourceRoomProof gXgbaR80SourceRoomProof={0};
static int XgbaR80SameSource(unsigned world,unsigned group,unsigned map)
{
    return sXgbaR80Route.phase!=0u &&
       sXgbaR80Route.to==XgbaR73ScopedKey(world,group,map);
}
int XgbaR80HasSourceWarpPending(void){return sXgbaR80Route.phase==1u;}
int XgbaR80ForeignInteriorActive(void){return sXgbaR80Route.phase==2u;}
unsigned XgbaR80DestinationWorld(void)
{
    return XgbaR80HasSourceWarpPending()?(sXgbaR80Route.to>>16u)&255u:255u;
}
unsigned XgbaR80DestinationGroup(void)
{
    return XgbaR80HasSourceWarpPending()?(sXgbaR80Route.to>>8u)&255u:255u;
}
unsigned XgbaR80DestinationMap(void)
{
    return XgbaR80HasSourceWarpPending()?sXgbaR80Route.to&255u:255u;
}
int XgbaR80SourceTargetAuthorized(unsigned world,unsigned group,unsigned map)
{
    return XgbaR80HasSourceWarpPending() &&
       XgbaR80SupportedFirstHopMap(sXgbaR80Route.to) &&
       XgbaR80SameSource(world,group,map);
}
int XgbaR80SourceLocationMatchesNative(unsigned world,unsigned group,unsigned map)
{
    if(!gSaveBlock1Ptr)return 0;
    if(XgbaR80SameSource(world,group,map))
        return gSaveBlock1Ptr->location.mapGroup==XGBA_R80_NATIVE_GROUP &&
               gSaveBlock1Ptr->location.mapNum==XGBA_R80_NATIVE_MAP;
    return gSaveBlock1Ptr->location.mapGroup==group &&
           gSaveBlock1Ptr->location.mapNum==map;
}
int XgbaR80PendingNativeMapMatches(void)
{
    return XgbaR80HasSourceWarpPending() &&
       XgbaR80SourceLocationMatchesNative(XgbaR80DestinationWorld(),
                XgbaR80DestinationGroup(),XgbaR80DestinationMap());
}
int XgbaR80SpriteVisibleInSourceMap(unsigned world,unsigned group,unsigned map,
                                    unsigned width,unsigned height,int x,int y)
{
    if(XgbaR80SameSource(world,group,map))
        return XgbaR80NpcVisibleAtSourceArrival(width,height,
                  sXgbaR80Route.x,sXgbaR80Route.y,x,y);
    return XgbaR60OriginalNpcIsInLandingView(
                  world,group,map,width,height,x,y);
}
void XgbaR80OnSourceRendererReleased(void)
{
    if(sXgbaR80Route.phase==2u)sXgbaR80Route.phase=0u;
}
void XgbaR80InvalidateSourceWarp(void)
{
    if(sXgbaR80Route.phase)
        ++gXgbaR80SourceRoomProof.route_revoked;
    sXgbaR80Route.phase=0u;
    sXgbaR80Route.from=0u;
    sXgbaR80Route.to=0u;
}
void XgbaR80ConfirmRealSourceMapArrival(void)
{
    if(!XgbaR80PendingNativeMapMatches() || !sXgbaR50Ready ||
       !sXgbaR51NativeTerrain.valid || !sXgbaR53SourceActive ||
       !sXgbaR54SourceMapPreparedInWarp ||
       IsDma3ManagerBusyWithBgCopy() ||
       gMapHeader.events!=&sXgbaR50LiveEvents ||
       gMapHeader.mapLayout!=&sXgbaR50LiveLayout ||
       !sXgbaR55RosterHasSourceAssets ||
       sXgbaR50OriginalEvents.active_source_key!=sXgbaR80Route.to ||
       gXgbaR53GraphicsProof.source_key!=sXgbaR80Route.to ||
       gXgbaR54NativeWarpProof.last_source_key!=sXgbaR80Route.to)
        return;
    sXgbaR80Route.phase=2u;
    ++gXgbaR80SourceRoomProof.original_room_loaded;
    gXgbaR80SourceRoomProof.actual_original_target_key=sXgbaR80Route.to;
    gXgbaR80SourceRoomProof.native_slot=0x0009u;
}
static bool8 XgbaR80QueueVerifiedPhysicalOriginalDoor(
    const struct XgbaR80DoorPlan *plan)
{
    if(!plan || !gSaveBlock1Ptr || sXgbaR80Route.phase==1u ||
       sXgbaR48PendingFlyWorld!=0xffu ||
       !sXgbaR50Ready || !sXgbaR51NativeTerrain.valid ||
       !sXgbaR53SourceActive ||
       plan->original_from!=sXgbaR50OriginalEvents.active_source_key ||
       plan->native_group!=0u || plan->native_map!=9u ||
       !XgbaR80SupportedFirstHopMap(plan->original_to) ||
       (sXgbaR80Route.phase==2u &&
        sXgbaR80Route.to!=plan->original_from))
        return FALSE;
    sXgbaR80Route.from=plan->original_from;
    sXgbaR80Route.to=plan->original_to;
    sXgbaR80Route.x=plan->original_x;
    sXgbaR80Route.y=plan->original_y;
    sXgbaR80Route.phase=1u;
    ++gXgbaR80SourceRoomProof.real_player_queued;
    return TRUE;
}
