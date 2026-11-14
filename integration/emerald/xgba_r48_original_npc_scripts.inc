/* R48: authentic original NPC script + original dialogue bridge for one
 * known original map object in EACH of three user-owned Pokémon ROMs.
 *
 * The supplied payloads contain UNMODIFIED bytes extracted from the user's
 * ROM and independently SHA-checked by the XGBA host. NEVER replace them
 * with generic "Rocket says..." dialogue or authored quest substitutes.
 *
 * This is the EVENT/OBJECT interpreter bridge needed by the actual Emerald
 * field interaction function. Foreign map layouts, object sprite graphics,
 * Fly landing and world transitions are separately required and MUST NOT be
 * claimed until native overworld tests prove them. This bridge deliberately
 * fails closed if no active verified imported source map is present.
 */
#ifndef XGBA_R48_ORIGINAL_NPC_BRIDGE
#error R48 original source NPC bridge requires explicit guest opt-in
#endif
#include "script.h"
#include "event_data.h"
#include "../common/xgba_r67_original_npc_witness.h"
#include "../common/xgba_r70_original_witness_binding.h"
#include "../common/xgba_r71_original_script_cache_integrity.h"

#define XGBA_R48_WORLD_COUNT 3u
#define XGBA_R48_BYTES 256u
#define XGBA_R48_HEADER 32u
#define XGBA_R48_SCRIPT_LENGTH 9u
#define XGBA_R48_ORIGINAL_NPC_MAGIC 0x4E383458u
#define XGBA_R48_PROOF_MAGIC 0x5234384Eu
#ifdef XGBA_R54_REAL_WARP_ADMISSION
extern const struct ObjectEventGraphicsInfo *
    XgbaR55GetVerifiedNativeOriginalObjectGraphics(u8 installed_slot);
extern bool8 XgbaR70ResolveAuthenticWitnessGraphics(u8 world,u8 group,
                                                       u8 map,u8 *slot);
#endif

#ifdef XGBA_R54_REAL_WARP_ADMISSION
/* R91: native ARM Fly acceptance counter is updated only after R48's
 * genuine FieldCallback_FlyIntoMap attests actual original source actors.
 * The function is defined after R54's native runtime proof declaration. */
static void XgbaR54CountVerifiedNativeFlyArrival(u8 world,u8 group,u8 map);
#endif
struct XgbaR48OriginalNpcProof {
    volatile u32 magic;
    volatile u32 source_map_loaded;
    volatile u32 current_world;
    volatile u32 original_script_fetches;
    volatile u32 script_context_launches;
    volatile u32 rejected_mismatch;
    volatile u32 original_script_last_offset;
    volatile u32 original_text_last_offset;
    volatile u32 real_npc_interactions;
    volatile u32 actual_cross_world_fly_warps;
    volatile u32 map_keys_verified;
};
EWRAM_DATA volatile struct XgbaR48OriginalNpcProof gXgbaR48OriginalNpcProof={0};
static EWRAM_DATA u8 sXgbaR48Payload[XGBA_R48_WORLD_COUNT][XGBA_R48_BYTES]={0};
static EWRAM_DATA u8 sXgbaR48Ready[XGBA_R48_WORLD_COUNT]={0};
static EWRAM_DATA u8 sXgbaR48ResourceName[32]={0};
static EWRAM_DATA u8 sXgbaR48ImportedWorld=0u;
static EWRAM_DATA u8 sXgbaR48ImportedGroup=0u;
static EWRAM_DATA u8 sXgbaR48ImportedMap=0u;
static EWRAM_DATA bool8 sXgbaR48SourceMapLoaded=FALSE;
/* Actual Fly route: Emerald -> Rocket -> Heart & Soul -> Emerald.
 * These are source-local ORIGINAL IDs, never rewritten into another
 * world's colliding (group,map). The engine Fly UI will call queue AFTER
 * the player picks the destination, not on synthetic R/L button probes. */
static EWRAM_DATA u8 sXgbaR48FlyLeg=0u;
static EWRAM_DATA u8 sXgbaR48PendingFlyWorld=0xffu;
static EWRAM_DATA u8 sXgbaR48PendingFlyGroup=0xffu;
static EWRAM_DATA u8 sXgbaR48PendingFlyMap=0xffu;
static EWRAM_DATA u8 sXgbaR48NpcTalkedMask=0u;

bool8 XgbaR48QueueOriginalFly(u8 destination_world,u8 group,u8 map)
{
    static const u8 next_source[3]={1u,2u,0u};
    static const u8 next_group[3]={0u,0u,0u};
    static const u8 next_map[3]={9u,4u,9u};
    if(sXgbaR48FlyLeg>=3u || sXgbaR48PendingFlyWorld!=0xffu ||
       !sXgbaR48SourceMapLoaded || sXgbaR48FlyLeg!=sXgbaR48ImportedWorld ||
       !(sXgbaR48NpcTalkedMask&(1u<<sXgbaR48FlyLeg)) ||
       destination_world!=next_source[sXgbaR48FlyLeg] ||
       group!=next_group[sXgbaR48FlyLeg] ||
       map!=next_map[sXgbaR48FlyLeg])
        return FALSE;
    /* This records the user's REAL Fly selection. It is not a warp or
     * game-engine transition until native original Fly callbacks finish. */
    sXgbaR48PendingFlyWorld=destination_world;
    sXgbaR48PendingFlyGroup=group;
    sXgbaR48PendingFlyMap=map;
    return TRUE;
}
void XgbaR48ConfirmActualFlyArrival(void)
{
    /* Hooked from original source-built Emerald FieldCallback_FlyIntoMap,
     * called by native FLDEFF_FLY_IN after original WarpIntoMap/CB2_LoadMap.
     * Reject unless original map/NPC/assets are already in the engine. */
    if(sXgbaR48PendingFlyWorld==0xffu)return;
    if(!sXgbaR48SourceMapLoaded ||
       sXgbaR48ImportedWorld!=sXgbaR48PendingFlyWorld ||
       sXgbaR48ImportedGroup!=sXgbaR48PendingFlyGroup ||
       sXgbaR48ImportedMap!=sXgbaR48PendingFlyMap){
        ++gXgbaR48OriginalNpcProof.rejected_mismatch;
        return;
    }
    ++gXgbaR48OriginalNpcProof.actual_cross_world_fly_warps;
#ifdef XGBA_R54_REAL_WARP_ADMISSION
    XgbaR54CountVerifiedNativeFlyArrival(sXgbaR48PendingFlyWorld,
          sXgbaR48PendingFlyGroup,sXgbaR48PendingFlyMap);
#endif
    ++sXgbaR48FlyLeg;
    sXgbaR48PendingFlyWorld=0xffu;
    sXgbaR48PendingFlyGroup=0xffu;
    sXgbaR48PendingFlyMap=0xffu;
}


/* Only the eventual real original-engine foreign map loader may declare
 * the imported map active. A source-labelled Fly menu selection alone
 * must NEVER set this flag or enable NPC script substitution. */
void XgbaR48SetSourceMapLoaded(u8 source,u8 group,u8 number,
                                  bool8 decoded_original_graphics_verified)
{
    /* A UI button or source ID alone is NOT proof of having flown into
     * another original map. The genuine overworld must already expose
     * the correct map dimensions and ACTUAL object-event placement. */
    static const u8 map_groups[3]={0u,0u,0u};
    static const u8 map_numbers[3]={9u,9u,4u};
    static const s16 widths[3]={20,24,58};
    static const s16 heights[3]={20,25,46};
    static const u8 local_ids[3]={2u,2u,7u};
    static const s16 npc_x[3]={12,14,39};
    static const s16 npc_y[3]={13,13,22};
    const struct MapEvents *events=gMapHeader.events;
    unsigned i;
    bool8 original_object_present=FALSE;
    bool8 physical_original_npc_spawned=FALSE;
    u8 expected_native_graphics=0xffu;
    sXgbaR48SourceMapLoaded=FALSE;
    gXgbaR48OriginalNpcProof.source_map_loaded=0u;
    if(source>=XGBA_R48_WORLD_COUNT ||
       !decoded_original_graphics_verified ||
       group!=map_groups[source] || number!=map_numbers[source] ||
       !gMapHeader.mapLayout || !events || !events->objectEvents ||
       gMapHeader.mapLayout->width!=widths[source] ||
       gMapHeader.mapLayout->height!=heights[source] ||
       !events->objectEventCount)
        return;
    /* Do not accept a different physical actor using the source NPC's
     * local ID. Bind the expected original u16 art to the actual native
     * R55 slot before either the template or the spawned sprite qualifies. */
#ifdef XGBA_R54_REAL_WARP_ADMISSION
    if(!XgbaR70ResolveAuthenticWitnessGraphics(
           source,group,number,&expected_native_graphics))return;
#else
    if(source!=0u)return;
    expected_native_graphics=17u;
#endif
    for(i=0u;i<events->objectEventCount;i++){
        const struct ObjectEventTemplate *obj=&events->objectEvents[i];
        if(obj->localId==local_ids[source] &&
           obj->x==npc_x[source] && obj->y==npc_y[source] &&
           obj->graphicsId==expected_native_graphics){
            original_object_present=TRUE;
            break;
        }
    }
    if(!original_object_present)
        return;
    /* A preserved R49 template is not a PHYSICAL original NPC spawn.
     * Original Emerald's event-object manager and sprite engine must have
     * instantiated the actual witness object before Fly/dialogue attests
     * that we visited it. Reject invisible, despawned or missing sprites. */
    for(i=0u;i<OBJECT_EVENTS_COUNT;i++){
        const struct ObjectEvent *event=&gObjectEvents[i];
        if(!event->active || event->localId!=local_ids[source] ||
           event->mapGroup!=group || event->mapNum!=number ||
           event->graphicsId!=expected_native_graphics ||
           event->spriteId>=MAX_SPRITES ||
           !gSprites[event->spriteId].inUse)
            continue;
#ifdef XGBA_R54_REAL_WARP_ADMISSION
        if(source!=0u &&
           !XgbaR55GetVerifiedNativeOriginalObjectGraphics(
                 event->graphicsId))
            continue;
#endif
        physical_original_npc_spawned=TRUE;
        break;
    }
    if(!physical_original_npc_spawned)return;
    sXgbaR48ImportedWorld=source;
    sXgbaR48ImportedGroup=group;
    sXgbaR48ImportedMap=number;
    sXgbaR48SourceMapLoaded=TRUE;
    gXgbaR48OriginalNpcProof.magic=XGBA_R48_PROOF_MAGIC;
    gXgbaR48OriginalNpcProof.current_world=source;
    gXgbaR48OriginalNpcProof.source_map_loaded=1u;
    ++gXgbaR48OriginalNpcProof.map_keys_verified;
}
static u32 XgbaR48Little32(const u8 *src)
{
    return (u32)src[0]|((u32)src[1]<<8)|((u32)src[2]<<16)|((u32)src[3]<<24);
}
static u16 XgbaR48Little16(const u8 *src)
{
    return (u16)src[0]|((u16)src[1]<<8);
}
/* Pure guest copy of the same 256-byte original source witness format
 * also checked by R64 host SHA validation. This is NOT generic ROM script
 * compatibility: exactly three known original NPCs are supported. */
static bool8 XgbaR48VerifyPayload(u8 source)
{
    return XgbaR71OriginalNpcPacketValid(
        source,sXgbaR48Payload[source],XGBA_R48_BYTES);
}
static const char *XgbaR48OriginalNpcResourceName(u8 source)
{
    static const char *const names[3]={
        "emerald.r48.npc","rocket.r48.npc","heart_soul.r48.npc"
    };
    return source<3u?names[source]:NULL;
}
/* MMIO R7 only accepts source name + destination in EWRAM. Reuse
 * the EXISTING 32-byte EWRAM ID and 3x256-byte R48 payload buffers;
 * neither ROM-backed const names nor IWRAM stack arrays are valid.
 * Original source payload verification must happen before relocation. */

/* R74: R49/R51/R52/R53 readers build IDs on the IWRAM stack. mGBA's
 * resource device accepts IDs only in EWRAM. Reuse the existing R48 ID
 * buffer for EVERY original-source page callback. GuestFetch is synchronous;
 * this buffer is not a permanent new EWRAM allocation or concurrent lease.
 * The source original NPC loader restages its ID independently when used.
 */
static bool8 XgbaR48StagePagedResourceName(const char *name)
{
    unsigned i=0u;
    if(!name)return FALSE;
    while(i+1u<sizeof(sXgbaR48ResourceName) && name[i]){
        const u8 c=(u8)name[i];
        if(!((c>='a' && c<='z') || (c>='0' && c<='9') ||
             c=='.' || c=='_' || c=='-'))
            return FALSE;
        sXgbaR48ResourceName[i]=c;
        ++i;
    }
    if(i==0u || name[i])return FALSE;
    sXgbaR48ResourceName[i]=0u;
    return TRUE;
}

static bool8 XgbaR48StageOriginalNpcResourceName(u8 source)
{
    const char *name=XgbaR48OriginalNpcResourceName(source);
    u32 i;
    if(!name)return FALSE;
    for(i=0u;i<sizeof(sXgbaR48ResourceName);i++)
        sXgbaR48ResourceName[i]=0u;
    for(i=0u;name[i] && i<sizeof(sXgbaR48ResourceName)-1u;i++)
        sXgbaR48ResourceName[i]=(u8)name[i];
    return TRUE;
}
/* R69: source-script Fly preflight does not change the pending destination,
 * NPC interaction evidence, loaded original script status or game save.
 *
 * For a not-yet-used source it borrows that world's existing EWRAM original
 * packet slot but intentionally leaves sXgbaR48Ready false, so actual
 * physical NPC interaction re-fetches and authenticates the payload.
 *
 * Already loaded scripts hold a verified relocated text pointer: they must
 * NEVER be overwritten with a raw source packet during return-to-Emerald.
 * Such an already-verified cached script is sufficient for this route.
 */
bool8 XgbaR48PreflightOriginalNpcResource(u8 source)
{
    if(source>=XGBA_R48_WORLD_COUNT)
        goto rejected;
    if(sXgbaR48Ready[source]){
        if(XgbaR71CachedOriginalNpcValid(
               source,sXgbaR48Payload[source],XGBA_R48_BYTES))
            return TRUE;
        goto rejected;
    }
    if(!XgbaR48StageOriginalNpcResourceName(source) ||
       XgbaGuestFetch((const char *)sXgbaR48ResourceName,
                      sXgbaR48Payload[source],XGBA_R48_BYTES)
          !=XGBA_R48_BYTES ||
       !XgbaR48VerifyPayload(source))
        goto rejected;
    return TRUE;
rejected:
    ++gXgbaR48OriginalNpcProof.rejected_mismatch;
    return FALSE;
}
static bool8 XgbaR48LoadOriginalNpc(u8 source)
{
    u8 *script;
    u32 relocated;
    if(source>=3u)return FALSE;
    if(sXgbaR48Ready[source]){
        if(XgbaR71CachedOriginalNpcValid(
               source,sXgbaR48Payload[source],XGBA_R48_BYTES))
            return TRUE;
        ++gXgbaR48OriginalNpcProof.rejected_mismatch;
        return FALSE;
    }
    if(!XgbaR48StageOriginalNpcResourceName(source)){
        ++gXgbaR48OriginalNpcProof.rejected_mismatch;
        return FALSE;
    }
    if(XgbaGuestFetch((const char *)sXgbaR48ResourceName,
                      sXgbaR48Payload[source],XGBA_R48_BYTES)
       !=XGBA_R48_BYTES ||
       !XgbaR48VerifyPayload(source)){
        ++gXgbaR48OriginalNpcProof.rejected_mismatch;
        return FALSE;
    }
    /* Preserve every original opcode, but relocate its one source-local
     * raw ROM pointer to the same original text now in guest EWRAM. */
    script=sXgbaR48Payload[source]+XGBA_R48_HEADER;
    relocated=(u32)(script+XGBA_R48_SCRIPT_LENGTH);
    script[2]=(u8)relocated;
    script[3]=(u8)(relocated>>8u);
    script[4]=(u8)(relocated>>16u);
    script[5]=(u8)(relocated>>24u);
    if(!XgbaR71CachedOriginalNpcValid(source,sXgbaR48Payload[source],
                                      XGBA_R48_BYTES)){
        ++gXgbaR48OriginalNpcProof.rejected_mismatch;
        return FALSE;
    }
    sXgbaR48Ready[source]=TRUE;
    ++gXgbaR48OriginalNpcProof.original_script_fetches;
    return TRUE;
}

/* Called from the ORIGINAL GetInteractedObjectEventScript/A-button route,
 * after its real object/collision/position lookup. Maps and sprites must
 * already have been instantiated from THIS source, not a viewer overlay. */
const u8 *XgbaR48ResolveActualOriginalNpcScript(
    u8 original_group,u8 original_map,u8 original_npc_id,
    const u8 *ordinary_emerald_script)
{
    u8 source;
    static const u8 groups[3]={0u,0u,0u};
    static const u8 maps[3]={9u,9u,4u};
    static const u8 npc_ids[3]={2u,2u,7u};
    if(!sXgbaR48SourceMapLoaded)
        return ordinary_emerald_script;
    source=sXgbaR48ImportedWorld;
    if(source>=XGBA_R48_WORLD_COUNT ||
       original_group!=groups[source] ||
       original_map!=maps[source] ||
       original_npc_id!=npc_ids[source] ||
       original_group!=sXgbaR48ImportedGroup ||
       original_map!=sXgbaR48ImportedMap)
        return ordinary_emerald_script;
    if(!XgbaR48LoadOriginalNpc(source))
        return NULL; /* Fail closed, not generic authored replacement. */
    gXgbaR48OriginalNpcProof.original_script_last_offset=
        XgbaR48Little32(sXgbaR48Payload[source]+15u);
    gXgbaR48OriginalNpcProof.original_text_last_offset=
        XgbaR48Little32(sXgbaR48Payload[source]+19u);
    ++gXgbaR48OriginalNpcProof.real_npc_interactions;
    sXgbaR48NpcTalkedMask|=(1u<<source);
    return sXgbaR48Payload[source]+XGBA_R48_HEADER;
}
