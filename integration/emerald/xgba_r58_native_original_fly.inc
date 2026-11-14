/* R58 — REAL native Emerald Fly-menu source-route admission.
 *
 * The region-map UI invokes these functions only from the player's SELECT
 * and A presses, never from a debug source switch. Before queueing an actual
 * Fly destination, inspect authenticated R49 NPCs, R51 map geometry, R52
 * version traits, R53 original 4bpp/tileset palettes and R56 ORIGINAL OBJ
 * source frames/palettes/OAM/animation. Use the ONE existing 16KiB scratch.
 *
 * No fake first sprite, substituted guest dialogue or nonoriginal map
 * identity is allowed. Preflight is read-only and cannot commit a map;
 * original Emerald's faded loader remains the actual commit boundary.
 * Normal original Fly UI and vanilla Emerald remain unchanged if unavailable.
 */
#include "../common/xgba_r70_original_witness_binding.h"
#ifndef XGBA_R54_REAL_WARP_ADMISSION
#error R58 requires the native R54 real original Fly/warp path
#endif
struct XgbaR58NativeFlyProof {
    volatile u32 original_destinations_offered,actual_player_selections;
    volatile u32 all_resource_preflights,source_art_crc_checks;
    volatile u32 source_palette_checks,rejected_resources;
    volatile u32 original_fly_queued; /* NOT arrival proof */
    volatile u32 original_witness_preflights,rejected_original_witness;
};
EWRAM_DATA volatile struct XgbaR58NativeFlyProof gXgbaR58NativeFlyProof={0};

static const u8 sXgbaR58NextWorld[]={1u,2u,0u};
static const u8 sXgbaR58NextMap[]={9u,4u,9u};
static const s8 sXgbaR58LandingX[]={14,39,12};
static const s8 sXgbaR58LandingY[]={14,23,14};

u8 XgbaR58GetOfferedOriginalFlyWorld(void)
{
    u8 step=sXgbaR48FlyLeg;
    if(step>=3u || sXgbaR48PendingFlyWorld!=0xffu ||
       !sXgbaR48SourceMapLoaded ||
       sXgbaR48ImportedWorld!=step ||
       !(sXgbaR48NpcTalkedMask&(1u<<step)))
        return 0xffu;
    return sXgbaR58NextWorld[step];
}
static int XgbaR58CopySourcePalette(void *ctx,unsigned section,
                    const u8 *src,u32 offset,u32 bytes)
{
    if(!ctx || !src || section!=1u || offset!=0u || bytes!=32u)
        return 0;
    memcpy(ctx,src,32u);
    return 1;
}
static bool8 XgbaR58PreflightOriginalDestination(u8 world,u8 group,u8 map,
                                                 s8 x,s8 y,
                                                 bool8 fly_witness_required)
{
    struct XgbaR51Reader grid={0};
    struct XgbaR51IndexRow location={0};
    struct XgbaR52Reader traits={0};
    struct XgbaR52MapProfile profile={0};
    struct XgbaR53Reader tiles={0};
    struct XgbaR53Tileset source_tiles[2]={0};
    struct XgbaR49Reader events={0};
    struct XgbaR49OriginalEvents original={0};
    u16 ids[XGBA_R50_MAX_OBJECTS]={0};
    u8 palettes[4][32]={0},current[32]={0};
    u32 key=((u32)world<<16)|((u32)group<<8)|map;
    unsigned i,j,count=0u,palette_count=0u,side,part;
    if(world>=3u || x<0 || y<0 ||
       (fly_witness_required &&
          (group!=0u || (world==2u?map!=4u:map!=9u))) ||
       (!fly_witness_required && !XgbaR80SupportedFirstHopMap(key)))
        return FALSE;
    ++gXgbaR58NativeFlyProof.all_resource_preflights;
    /* All three legs, including return to native Emerald, require their
     * genuine original NPC script/text witness before the Fly UI queues
     * any map change. No source art, save state or R48 cache is altered. */
    if(fly_witness_required)++gXgbaR58NativeFlyProof.original_witness_preflights;
    if(fly_witness_required && !XgbaR48PreflightOriginalNpcResource(world)){
        ++gXgbaR58NativeFlyProof.rejected_original_witness;
        goto refuse;
    }
    /* World0 return uses the ORIGINAL Emerald ROM-linked map and native
     * object assets. No R51/R53/R56 sidecar for Emerald is needed; see
     * the native header / original witness guard shared with R54. */
    if(world==XGBA_R63_NATIVE_WORLD){
        if(XgbaR63VerifyNativeReturnHeader(world,group,map,
              XGBA_R63_NATIVE_WIDTH,XGBA_R63_NATIVE_HEIGHT,1u,x,y) &&
           XgbaR63NativeEmeraldReturnHeaderPresent())
            return TRUE;
        goto refuse;
    }
    grid.fetch=XgbaR51FetchRealPage;grid.scratch=(u8 *)gXgbaR17Arena;
    grid.indexed_maps=XGBA_R51_ALL_SOURCE_MAPS;
    grid.cached_index_page=XGBA_R51_INVALID_PAGE;
    if(!XgbaR51FindSourceMap(&grid,key,&location) ||
       location.width<=(u16)x || location.height<=(u16)y ||
       location.grid_bytes+XGBA_R51_GRID_BORDER_BYTES>XGBA_R51_MAX_GUEST_GRID ||
       (u32)(location.width+15u)*(location.height+14u)>0x2800u)
        goto refuse;
    traits.fetch=XgbaR52FetchRealLayoutPage;
    traits.scratch=(u8 *)gXgbaR17Arena;
    traits.indexed_maps=XGBA_R52_MAPS;
    traits.cached_page=XGBA_R52_PAGE_INVALID;
    if(!XgbaR52LoadProfile(&traits,key,&profile))
        goto refuse;
    tiles.fetch=XgbaR53FetchNativePage;
    tiles.scratch=(u8 *)gXgbaR17Arena;
    for(side=0u;side<2u;side++){
        u32 descriptor=side?profile.secondary_tileset_offset:
                             profile.primary_tileset_offset;
        if(!XgbaR53MetaLoad(&tiles,world,profile.version,
                            descriptor,side,&source_tiles[side]))
            goto refuse;
        for(part=0u;part<4u;part++)
            if(!XgbaR53VisitSection(&tiles,&source_tiles[side],
                                    part,NULL,NULL))goto refuse;
    }
    /* Authentic source object records are read before the R56 page reader
     * overwrites shared scratch; preserve full 16-bit identities only. */
    events.fetch=XgbaR50FetchOriginalPage;
    events.scratch=(u8 *)gXgbaR17Arena;
    events.indexed_maps=XGBA_R49_ALL_MAPS;
    events.cached_index_page=XGBA_R49_INVALID_PAGE;
    if(!XgbaR49LoadOriginalMapEvents(&events,key,&original) ||
       original.object_count>XGBA_R50_MAX_OBJECTS ||
       (fly_witness_required &&
        !XgbaR70OriginalWitnessRecordPresent(world,group,map,
                          original.objects,original.object_count)))
        goto refuse;
    for(i=0u;i<original.object_count;i++){
        const u8 *npc=original.objects+i*24u;
        u16 source_id=XgbaR49Le16(npc+1u);
        s16 nx=(s16)XgbaR49Le16(npc+4u);
        s16 ny=(s16)XgbaR49Le16(npc+6u);
        if(world!=0u &&
           (fly_witness_required?
             !XgbaR60OriginalNpcIsInLandingView(
                world,group,map,location.width,location.height,nx,ny):
             !XgbaR80NpcVisibleAtSourceArrival(
                location.width,location.height,x,y,nx,ny)))
            continue;
        for(j=0u;j<count;j++)if(ids[j]==source_id)break;
        if(j==count){
            if(count>=XGBA_R55_SPRITE_SLOTS)goto refuse;
            ids[count++]=source_id;
        }
    }
    if(world!=0u){
        struct XgbaR56Reader r={0};
        r.fetch=XgbaR53FetchNativePage;
        r.scratch=(u8 *)gXgbaR17Arena;
        for(i=0u;i<count;i++){
            struct XgbaR56SourceObject obj={0};
            if(!XgbaR56ReadMeta(&r,world,ids[i],&obj))
                goto refuse;
            if(!XgbaR56VisitSection(&r,&obj,0u,NULL,NULL) ||
               !XgbaR56VisitSection(&r,&obj,1u,
                                     XgbaR58CopySourcePalette,current) ||
               !XgbaR56VisitSection(&r,&obj,2u,NULL,NULL) ||
               !XgbaR56VisitSection(&r,&obj,3u,NULL,NULL))
                goto refuse;
            gXgbaR58NativeFlyProof.source_art_crc_checks+=4u;
            for(j=0u;j<palette_count;j++)
                if(memcmp(current,palettes[j],32u)==0)break;
            if(j==palette_count){
                if(palette_count>=4u)goto refuse;
                memcpy(palettes[palette_count++],current,32u);
            }
        }
        gXgbaR58NativeFlyProof.source_palette_checks+=palette_count;
    }
    return TRUE;
refuse:
    ++gXgbaR58NativeFlyProof.rejected_resources;
    return FALSE;
}
/* The only path to pending R48 Fly is the real player's A-button confirmation
 * from the source-aware Emerald Fly map after full original resource preflight.
 * An actual verified arrival is counted separately by original field_effect.c.
 * If unavailable, NEVER set the warp or pending guest world. */
bool8 XgbaR58QueuePlayerSelectedOriginalFly(void)
{
    u8 world=XgbaR58GetOfferedOriginalFlyWorld();
    u8 step=sXgbaR48FlyLeg;
    u8 group=0u,map;
    s8 x,y;
    if(world>=3u || step>=3u)return FALSE;
    map=sXgbaR58NextMap[step];
    x=sXgbaR58LandingX[step];y=sXgbaR58LandingY[step];
    ++gXgbaR58NativeFlyProof.actual_player_selections;
    if(!XgbaR58PreflightOriginalDestination(world,group,map,x,y,TRUE))
        return FALSE;
    if(!XgbaR48QueueOriginalFly(world,group,map))
        return FALSE;
    SetWarpDestination(group,map,WARP_ID_NONE,x,y);
    ++gXgbaR58NativeFlyProof.original_fly_queued;
    return TRUE;
}
