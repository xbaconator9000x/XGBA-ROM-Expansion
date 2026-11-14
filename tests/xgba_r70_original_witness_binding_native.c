/* R70 author-owned NPC fixtures: no ROM dialogue, graphics or saves. */
#include "../integration/common/xgba_r70_original_witness_binding.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void le16(uint8_t *p,uint16_t v)
{
    p[0]=(uint8_t)v;p[1]=(uint8_t)(v>>8);
}
static void record(uint8_t *p,unsigned local,uint16_t gfx,int16_t x,int16_t y)
{
    memset(p,0,XGBA_R70_ORIGINAL_OBJECT_BYTES);
    p[0]=(uint8_t)local;le16(p+1u,gfx);
    le16(p+4u,(uint16_t)x);le16(p+6u,(uint16_t)y);
}
static int authentic_install(void *ctx,uint8_t world,uint16_t gfx,
                            uint8_t slot,uint32_t *pal,uint32_t *frame)
{
    (void)ctx;
    if(world==0u || world>=3u || slot<XGBA_R55_SPRITE_FIRST ||
       (world==1u?gfx!=17u:gfx!=406u))return 0;
    *pal=0x10203040u;*frame=0xabcdef01u;
    return 1;
}
int main(void)
{
    uint8_t originals[2*XGBA_R70_ORIGINAL_OBJECT_BYTES]={0};
    struct XgbaR55SourceSpriteRoster roster={0};
    unsigned world,local;
    uint16_t gfx;
    int16_t x,y;
    uint8_t slot=0xffu;
    for(world=0u;world<3u;world++){
        const unsigned map=world==2u?4u:9u;
        assert(XgbaR70ExpectedWitness(world,0u,map,&local,&gfx,&x,&y));
        record(originals,local,gfx,x,y);
        record(originals+XGBA_R70_ORIGINAL_OBJECT_BYTES,88u,999u,1,1);
        assert(XgbaR70OriginalWitnessRecordPresent(world,0u,map,originals,2u));
        assert(!XgbaR70OriginalWitnessRecordPresent(world,0u,map,originals,0u));
        assert(!XgbaR70OriginalWitnessRecordPresent(world,0u,map,originals,256u));
        assert(!XgbaR70OriginalWitnessRecordPresent(world,0u,map,NULL,2u));
        assert(!XgbaR70OriginalWitnessRecordPresent(world,1u,map,originals,2u));
        assert(!XgbaR70OriginalWitnessRecordPresent(world,0u,map^1u,originals,2u));
        originals[1]^=1u;
        assert(!XgbaR70OriginalWitnessRecordPresent(world,0u,map,originals,2u));
        originals[1]^=1u;
        originals[4]^=1u;
        assert(!XgbaR70OriginalWitnessRecordPresent(world,0u,map,originals,2u));
        originals[4]^=1u;
        originals[XGBA_R70_ORIGINAL_OBJECT_BYTES]=local;
        assert(!XgbaR70OriginalWitnessRecordPresent(world,0u,map,originals,2u));
        originals[XGBA_R70_ORIGINAL_OBJECT_BYTES]=88u;
        if(world==0u){
            assert(XgbaR70VerifiedWitnessNativeSlot(NULL,0u,0u,9u,&slot));
            assert(slot==17u);
        }else{
            assert(!XgbaR70VerifiedWitnessNativeSlot(NULL,world,0u,map,&slot));
            assert(XgbaR55ResetSourceRoster(&roster,world,0u,map));
            assert(XgbaR55AcquireVerifiedSourceSprite(&roster,world,gfx,
                authentic_install,NULL,&slot));
            assert(XgbaR70VerifiedWitnessNativeSlot(&roster,world,0u,map,&slot));
            assert(slot==XGBA_R55_SPRITE_FIRST);
            assert(!XgbaR70VerifiedWitnessNativeSlot(&roster,world,0u,map^1u,&slot));
            roster.records[0].verified_original_frames_crc=0u;
            assert(!XgbaR70VerifiedWitnessNativeSlot(&roster,world,0u,map,&slot));
            roster.records[0].verified_original_frames_crc=0xabcdef01u;
        }
    }
    assert(!XgbaR70ExpectedWitness(3u,0u,9u,&local,&gfx,&x,&y));
    assert(!XgbaR70VerifiedWitnessNativeSlot(NULL,3u,0u,9u,&slot));
    assert(!XgbaR70VerifiedWitnessNativeSlot(NULL,0u,0u,9u,NULL));
    puts("PASS_R70_THREE_WORLD_ORIGINAL_NPC_RECORD_SOURCE_GFX_AND_NATIVE_ROSTER_BINDING");
    return 0;
}
