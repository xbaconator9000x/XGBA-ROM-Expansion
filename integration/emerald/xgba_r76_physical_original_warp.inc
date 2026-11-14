/* R76 ACTUAL original Emerald physical step-warp hook.
 * TryStartWarpEventScript calls only when the original game's tile
 * behaviour says this physical step WOULD be a warp. R50 deliberately
 * registers zero native foreign warp events, so this cannot misroute the
 * player through a colliding Emerald map. It validates an original R49
 * route by R73 and records authentic physical interaction evidence only.
 * Loading target original-world graphics and committing it remains TODO.
 */
#include "../common/xgba_r76_physical_original_warp.h"
extern void DoWarp(void);
struct XgbaR76PhysicalWarpProof {
    volatile u32 physical_source_warp_hits;
    volatile u32 original_r73_route_verified;
    volatile u32 original_r73_route_rejected;
    volatile u32 last_source_key,last_target_key;
};
static struct XgbaR76PhysicalWarpProof sXgbaR76PhysicalProof={0};
/* This is deliberately a non-consuming observer; original Emerald can still
 * process its ordinary warp tiles and no foreign destination is forged. */
bool8 XgbaR76NotePhysicalOriginalStepWarp(u16 x,u16 y,u8 elevation)
{
    const u8 *warps;
    struct XgbaR73SourceWarpRoute route={0};
    u8 idx;
    if(!gSaveBlock1Ptr || !sXgbaR50Ready || !sXgbaR51NativeTerrain.valid ||
       (!sXgbaR48SourceMapLoaded && !XgbaR80ForeignInteriorActive()) ||
       sXgbaR50World==0u ||
       sXgbaR50World>=3u || !gMapHeader.mapLayout ||
       gMapHeader.events!=&sXgbaR50LiveEvents ||
       gMapHeader.mapLayout!=&sXgbaR50LiveLayout ||
       !XgbaR80SourceLocationMatchesNative(
          sXgbaR50World,sXgbaR50Group,sXgbaR50Number) ||
       x<MAP_OFFSET || y<MAP_OFFSET ||
       IsDma3ManagerBusyWithBgCopy())
        return FALSE;
    warps=XgbaR50EventBytes(&sXgbaR50OriginalEvents)+
          sXgbaR50OriginalEvents.object_bytes;
    if(!XgbaR76FindOriginalWarpOnTile(
           warps,sXgbaR50OriginalEvents.original_warp_count,
           sXgbaR51NativeTerrain.width,sXgbaR51NativeTerrain.height,
           (u32)x-MAP_OFFSET,(u32)y-MAP_OFFSET,elevation,&idx))
        return FALSE;
    ++sXgbaR76PhysicalProof.physical_source_warp_hits;
    if(!XgbaR73PreflightLoadedForeignWarp(idx,&route)){
        ++sXgbaR76PhysicalProof.original_r73_route_rejected;
        return FALSE;
    }
    sXgbaR76PhysicalProof.last_source_key=route.source_key;
    sXgbaR76PhysicalProof.last_target_key=route.target_key;
    ++sXgbaR76PhysicalProof.original_r73_route_verified;
    {
        struct XgbaR80DoorPlan plan={0};
        if(!XgbaR80PlanFirstHop(&route,&plan))return FALSE;
        if(!XgbaR58PreflightOriginalDestination(
               plan.source_world,plan.source_group,plan.source_map,
               (s8)plan.original_x,(s8)plan.original_y,FALSE)){
            ++gXgbaR80SourceRoomProof.refused_art;
            return FALSE;
        }
        if(!XgbaR80QueueVerifiedPhysicalOriginalDoor(&plan))return FALSE;
        SetWarpDestination(plan.native_group,plan.native_map,WARP_ID_NONE,
                           (s8)plan.original_x,(s8)plan.original_y);
        DoWarp(); /* genuine native original Emerald fade and field load */
        return TRUE;
    }
}
