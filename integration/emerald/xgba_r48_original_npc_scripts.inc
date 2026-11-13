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

#define XGBA_R48_WORLD_COUNT 3u
#define XGBA_R48_BYTES 256u
#define XGBA_R48_HEADER 32u
#define XGBA_R48_SCRIPT_LENGTH 9u
#define XGBA_R48_ORIGINAL_NPC_MAGIC 0x4E383458u
#define XGBA_R48_PROOF_MAGIC 0x5234384Eu

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
    for(i=0u;i<events->objectEventCount;i++){
        const struct ObjectEventTemplate *obj=&events->objectEvents[i];
        if(obj->localId==local_ids[source] &&
           obj->x==npc_x[source] && obj->y==npc_y[source]){
            original_object_present=TRUE;
            break;
        }
    }
    if(!original_object_present)
        return;
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
static bool8 XgbaR48VerifyPayload(u8 source)
{
    static const u8 map_groups[3]={0u,0u,0u};
    static const u8 map_numbers[3]={9u,9u,4u};
    static const u8 npc_local_ids[3]={2u,2u,7u};
    static const u16 sprite_ids[3]={17u,17u,406u};
    static const s16 x_coords[3]={12,14,39};
    static const s16 y_coords[3]={13,13,22};
    static const u32 script_origins[3]={0x1e8022u,0x215543u,0x390519u};
    static const u32 text_origins[3]={0x1e8acfu,0x1dc3364u,0x3908e6u};
    const u8 *p=sXgbaR48Payload[source];
    const u8 *script=p+XGBA_R48_HEADER;
    u16 text_length=XgbaR48Little16(p+25u);
    u32 original_text=XgbaR48Little32(p+19u);
    if(XgbaR48Little32(p)!=XGBA_R48_ORIGINAL_NPC_MAGIC ||
       p[4]!=1u || p[5]!=source ||
       p[6]!=map_groups[source] || p[7]!=map_numbers[source] ||
       p[8]!=npc_local_ids[source] ||
       (s16)XgbaR48Little16(p+9u)!=x_coords[source] ||
       (s16)XgbaR48Little16(p+11u)!=y_coords[source] ||
       XgbaR48Little16(p+13u)!=sprite_ids[source] ||
       XgbaR48Little32(p+15u)!=script_origins[source] ||
       original_text!=text_origins[source] ||
       XgbaR48Little16(p+23u)!=XGBA_R48_SCRIPT_LENGTH ||
       !text_length || text_length>210u ||
       (u32)XGBA_R48_HEADER+XGBA_R48_SCRIPT_LENGTH+text_length>XGBA_R48_BYTES)
        return FALSE;
    /* Require all original opcode bytes and original pointer to be intact.
     * Relocation happens ONLY after this original-script verification. */
    if(script[0]!=0x0fu || script[1]!=0u ||
       XgbaR48Little32(script+2u)!=0x08000000u+original_text ||
       script[6]!=0x09u || script[7]!=0x02u || script[8]!=0x02u ||
       p[XGBA_R48_HEADER+XGBA_R48_SCRIPT_LENGTH+text_length-1u]!=0xffu)
        return FALSE;
    return TRUE;
}
static bool8 XgbaR48LoadOriginalNpc(u8 source)
{
    static const char *const names[3]={
        "emerald.r48.npc","rocket.r48.npc","heart_soul.r48.npc"
    };
    u32 i;
    const char *src;
    u8 *script;
    u32 relocated;
    if(source>=3u)return FALSE;
    if(sXgbaR48Ready[source])return TRUE;
    src=names[source];
    for(i=0u;i<sizeof(sXgbaR48ResourceName);++i)
        sXgbaR48ResourceName[i]=0u;
    for(i=0u;src[i] && i<sizeof(sXgbaR48ResourceName)-1u;i++)
        sXgbaR48ResourceName[i]=src[i];
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
    return sXgbaR48Payload[source]+XGBA_R48_HEADER;
}
