/* R55 original source-qualified 16-bit NPC identity to bounded original
 * Emerald 8-bit OBJ gfx slot allocator.
 *
 * Source map count is 2,856 / 17,089 original NPC objects. Authenticated
 * R49 inventory finds max 57 DISTINCT source sprites in any HnS map,
 * 27 in Rocket, 24 in original Emerald. The native original Emerald
 * OBJ gfx byte only holds 256 values and IDs 240..255 are dynamic vars;
 * a source sprite ID like 0x4050 may NOT be silently narrowed to u8.
 *
 * Reserve 59 candidate per-map slots 180..238, subject to the future
 * original sprite renderer guaranteeing these ids aren't used by native
 * player/field effects, and supplying SHA-verified private original sprite
 * sheets. Allocation is identity-only and is NOT proof that OBJ sprites
 * are installed. If a map has >59 distinct original sprites, FAIL CLOSED.
 */
#ifndef XGBA_R55_SOURCE_QUALIFIED_SPRITE_SLOTS_H
#define XGBA_R55_SOURCE_QUALIFIED_SPRITE_SLOTS_H
#include <stdint.h>
#include <stddef.h>

#define XGBA_R55_SPRITE_FIRST 180u
#define XGBA_R55_SPRITE_LAST 238u
#define XGBA_R55_SPRITE_SLOTS (XGBA_R55_SPRITE_LAST-XGBA_R55_SPRITE_FIRST+1u)

struct XgbaR55OriginalSpriteId {
    uint16_t original_gfx_id;
    uint8_t native_slot,source_world;
    uint32_t verified_original_palette_crc,verified_original_frames_crc;
};
struct XgbaR55SourceSpriteRoster {
    uint8_t world,count;
    uint16_t source_group,source_map;
    struct XgbaR55OriginalSpriteId records[XGBA_R55_SPRITE_SLOTS];
};
typedef int (*XgbaR55GraphicVerified)(
    void *context,uint8_t world,uint16_t source_graphics_id,
    uint8_t allocated_native_slot,uint32_t *palette_crc,
    uint32_t *frames_crc);

static inline int XgbaR55ResetSourceRoster(
    struct XgbaR55SourceSpriteRoster *r,unsigned world,
    unsigned group,unsigned map)
{
    if(!r || world>2u || group>255u || map>255u)return 0;
    r->world=(uint8_t)world;
    r->source_group=(uint16_t)group;
    r->source_map=(uint16_t)map;
    r->count=0u;
    return 1;
}
/* Original palette and frame CRCs must come from the independently SHA-
 * verified source byte ranges, not an arbitrary shared Emerald frame. For
 * every new source ID, installer receives its actual WORLD and 16-bit ID
 * and must verify source graphics BEFORE the slot becomes discoverable.
 * Duplicate entries cannot remap a verified already-bound source ID. */
static inline int XgbaR55AcquireVerifiedSourceSprite(
    struct XgbaR55SourceSpriteRoster *r,unsigned world,
    uint16_t original_id,XgbaR55GraphicVerified install,
    void *context,uint8_t *out_slot)
{
    unsigned i;
    uint32_t pal=0u,frames=0u;
    uint8_t slot;
    if(!r || !out_slot || !install || world>=3u || r->world!=world)
        return 0;
    for(i=0;i<r->count;i++){
        if(r->records[i].original_gfx_id==original_id){
            if(r->records[i].source_world!=world ||
               !r->records[i].verified_original_frames_crc ||
               !r->records[i].verified_original_palette_crc)
                return 0;
            *out_slot=r->records[i].native_slot;
            return 1;
        }
    }
    if(r->count>=XGBA_R55_SPRITE_SLOTS)return 0;
    slot=(uint8_t)(XGBA_R55_SPRITE_FIRST+r->count);
    if(!install(context,(uint8_t)world,original_id,slot,&pal,&frames)
       || !pal || !frames)
        return 0;
    r->records[r->count].source_world=(uint8_t)world;
    r->records[r->count].original_gfx_id=original_id;
    r->records[r->count].native_slot=slot;
    r->records[r->count].verified_original_palette_crc=pal;
    r->records[r->count].verified_original_frames_crc=frames;
    ++r->count;
    *out_slot=slot;
    return 1;
}
static inline int XgbaR55FindVerifiedSprite(const struct XgbaR55SourceSpriteRoster *r,
    unsigned world,uint16_t original_id,uint8_t *out_slot)
{
    unsigned i;
    if(!r || !out_slot || world>2u || r->world!=world)return 0;
    for(i=0;i<r->count;i++){
        if(r->records[i].original_gfx_id==original_id &&
           r->records[i].source_world==world &&
           r->records[i].verified_original_frames_crc &&
           r->records[i].verified_original_palette_crc){
            *out_slot=r->records[i].native_slot;
            return 1;
        }
    }
    return 0;
}
#endif
