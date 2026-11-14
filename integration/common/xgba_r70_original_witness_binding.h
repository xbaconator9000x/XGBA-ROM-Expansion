/* R70: bind the actual NPC witness to its ORIGINAL source graphics ID.
 *
 * Source-aware map admission requires a unique, source-authenticated R49
 * object record (local ID, full 16-bit gfx, x/y), not merely a matching
 * local ID plus an unrelated installed OBJ sprite. The native field verifies
 * the same identity after R55 maps the source gfx ID to an Emerald u8 slot.
 * This is an identity/placement check, NOT proof that Fly or scripts ran.
 * No persistent GBA EWRAM is allocated by this adapter.
 */
#ifndef XGBA_R70_ORIGINAL_WITNESS_BINDING_H
#define XGBA_R70_ORIGINAL_WITNESS_BINDING_H
#include <stdint.h>
#include "xgba_r55_source_qualified_sprite_slots.h"
#define XGBA_R70_ORIGINAL_OBJECT_BYTES 24u

static inline uint16_t XgbaR70Le16(const uint8_t *p)
{
    return (uint16_t)((uint16_t)p[0]|((uint16_t)p[1]<<8));
}
static inline int XgbaR70ExpectedWitness(unsigned world,unsigned group,
    unsigned map,unsigned *local_id,uint16_t *original_gfx,
    int16_t *x,int16_t *y)
{
    static const uint8_t map_id[3]={9u,9u,4u};
    static const uint8_t npc_id[3]={2u,2u,7u};
    static const uint16_t source_gfx[3]={17u,17u,406u};
    static const int16_t source_x[3]={12,14,39};
    static const int16_t source_y[3]={13,13,22};
    if(world>=3u || group!=0u || map!=map_id[world] ||
       !local_id || !original_gfx || !x || !y)return 0;
    *local_id=npc_id[world];*original_gfx=source_gfx[world];
    *x=source_x[world];*y=source_y[world];
    return 1;
}
/* The R49 reader has already bounded and CRC-verified its 24-byte records.
 * Reject duplicate local IDs even when one copy appears to match. */
static inline int XgbaR70OriginalWitnessRecordPresent(unsigned world,
    unsigned group,unsigned map,const uint8_t *records,unsigned count)
{
    unsigned expected_local,i,found=0u;
    uint16_t expected_gfx;
    int16_t expected_x,expected_y;
    if(!records || !count || count>255u ||
       !XgbaR70ExpectedWitness(world,group,map,&expected_local,
                               &expected_gfx,&expected_x,&expected_y))
        return 0;
    for(i=0u;i<count;i++){
        const uint8_t *p=records+i*XGBA_R70_ORIGINAL_OBJECT_BYTES;
        if(p[0]!=expected_local)continue;
        if(found || XgbaR70Le16(p+1u)!=expected_gfx ||
           (int16_t)XgbaR70Le16(p+4u)!=expected_x ||
           (int16_t)XgbaR70Le16(p+6u)!=expected_y)return 0;
        found=1u;
    }
    return (int)found;
}
/* Foreign IDs must retain full u16 identity through the verified R55 roster.
 * Native source0 uses its genuine original Emerald byte ID directly. */
static inline int XgbaR70VerifiedWitnessNativeSlot(
    const struct XgbaR55SourceSpriteRoster *roster,
    unsigned world,unsigned group,unsigned map,uint8_t *slot)
{
    unsigned local;
    uint16_t gfx;
    int16_t x,y;
    if(!slot || !XgbaR70ExpectedWitness(world,group,map,
                                        &local,&gfx,&x,&y))return 0;
    if(world==0u){
        if(gfx>255u)return 0;
        *slot=(uint8_t)gfx;
        return 1;
    }
    if(!roster || roster->world!=world ||
       roster->source_group!=group || roster->source_map!=map)
        return 0;
    return XgbaR55FindVerifiedSprite(roster,world,gfx,slot);
}
#endif
