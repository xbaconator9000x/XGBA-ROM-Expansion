#include "../integration/common/xgba_r55_source_qualified_sprite_slots.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
static unsigned installed,fail_next;
static int source_verified(void *ctx,uint8_t world,uint16_t orig,
    uint8_t slot,uint32_t *palette,uint32_t *frames)
{
    (void)ctx;
    if(fail_next){fail_next=0;return 0;}
    if(world!=2u && world!=1u)return 0;
    if(slot<XGBA_R55_SPRITE_FIRST || slot>XGBA_R55_SPRITE_LAST)return 0;
    *palette=UINT32_C(0xabcdef00)+(uint32_t)orig+1u;
    *frames=UINT32_C(0x34560000)+(uint32_t)world+1u+
            (uint32_t)orig;
    ++installed;
    return 1;
}
int main(void)
{
    struct XgbaR55SourceSpriteRoster table={0};
    uint8_t slot=0xffu,before;
    unsigned i;
    assert(XgbaR55ResetSourceRoster(&table,2u,0u,4u));
    /* Original HnS can have up to 57 distinct sprites in a single map.
     * All remain distinct even if 16-bit IDs wrap to the same low byte. */
    for(i=0;i<57u;i++){
        uint16_t id=(uint16_t)(0x4000u+i*19u);
        assert(XgbaR55AcquireVerifiedSourceSprite(&table,2,id,
                 source_verified,0,&slot));
        assert(slot==180u+i);
        assert(XgbaR55FindVerifiedSprite(&table,2,id,&before));
        assert(before==slot);
    }
    assert(table.count==57u && installed==57u);
    assert(XgbaR55AcquireVerifiedSourceSprite(&table,2,
            0x4000u,source_verified,0,&slot));
    assert(installed==57u && slot==180u);
    assert(XgbaR55AcquireVerifiedSourceSprite(&table,2,
            0x0200u,source_verified,0,&slot));
    assert(slot==237u);
    assert(XgbaR55AcquireVerifiedSourceSprite(&table,2,
            0x0100u,source_verified,0,&slot));
    assert(slot==238u && table.count==59u);
    assert(!XgbaR55AcquireVerifiedSourceSprite(&table,2,
             0x9999u,source_verified,0,&slot));
    assert(!XgbaR55FindVerifiedSprite(&table,1,0x4000u,&slot));
    assert(!XgbaR55ResetSourceRoster(&table,3u,0u,4u));
    assert(XgbaR55ResetSourceRoster(&table,1u,0u,9u));
    assert(table.count==0u);
    assert(!XgbaR55FindVerifiedSprite(&table,2,0x4000u,&slot));
    assert(!XgbaR55AcquireVerifiedSourceSprite(&table,2,
             607u,source_verified,0,&slot));
    before=slot;fail_next=1u;
    assert(!XgbaR55AcquireVerifiedSourceSprite(&table,1,
             607u,source_verified,0,&slot));
    assert(table.count==0u && slot==before);
    assert(XgbaR55AcquireVerifiedSourceSprite(&table,1,
             607u,source_verified,0,&slot));
    assert(table.count==1u && slot==180u);
    assert(XgbaR55FindVerifiedSprite(&table,1,607u,&before) && before==180u);
    printf("PASS_R55_FULL_16BIT_ORIGINAL_SOURCE_GFX_IDS "
           "HNS_57_DISTINCT=1 ROCKET_607=1 NATIVE_SLOTS_180_238=1 "
           "PER_WORLD_NO_TRUNCATION=1 FULL_FAIL_CLOSED=1\n");
    return 0;
}
