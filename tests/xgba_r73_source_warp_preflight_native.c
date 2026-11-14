#include "../integration/common/xgba_r73_source_warp_preflight.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void put16(uint8_t *p,uint16_t n){p[0]=(uint8_t)n;p[1]=(uint8_t)(n>>8);}
static void warp(uint8_t *p,int16_t x,int16_t y,unsigned elev,
                 unsigned dest_index,unsigned dest_map,unsigned dest_group)
{
    put16(p,(uint16_t)x);put16(p+2,(uint16_t)y);
    p[4]=(uint8_t)elev;p[5]=(uint8_t)dest_index;
    p[6]=(uint8_t)dest_map;p[7]=(uint8_t)dest_group;
}
int main(void)
{
    uint8_t src[8]={0},target[16]={0};
    struct XgbaR73SourceWarpRoute result={0},saved={0};
    warp(src,16,8,0,1,2,35);
    warp(target,6,2,0,0,9,0);
    warp(target+8,11,5,1,0,9,0);
    assert(XgbaR73ProveOriginalWarp(0x010009u,24,25,src,1,0,
        0x012302u,26,20,target,2,&result)==XGBA_R73_OK);
    assert(result.target_key==0x012302u && result.target_x==11u &&
           result.target_y==5u && result.target_index==1u);
    saved=result;
    assert(XgbaR73ProveOriginalWarp(0x010009u,24,25,src,1,0,
        0x002302u,26,20,target,2,&result)==XGBA_R73_WORLD_OR_MAP_COLLISION);
    assert(!memcmp(&result,&saved,sizeof(result)));
    src[5]=2u;
    assert(XgbaR73ProveOriginalWarp(0x010009u,24,25,src,1,0,
        0x012302u,26,20,target,2,&result)==XGBA_R73_TARGET_WARP_NOT_PRESENT);
    warp(src,16,8,0,127,127,127);
    assert(XgbaR73ProveOriginalWarp(0x010009u,24,25,src,1,0,
        0x017f7fu,26,20,target,2,&result)==XGBA_R73_DYNAMIC_WARP);
    warp(src,25,8,0,1,2,35);
    assert(XgbaR73ProveOriginalWarp(0x010009u,24,25,src,1,0,
        0x012302u,26,20,target,2,&result)==XGBA_R73_BAD_SOURCE_COORD);
    warp(src,16,8,0,1,2,35);
    warp(target+8,27,5,1,0,9,0);
    assert(XgbaR73ProveOriginalWarp(0x010009u,24,25,src,1,0,
        0x012302u,26,20,target,2,&result)==XGBA_R73_BAD_TARGET_COORD);
    assert(!memcmp(&result,&saved,sizeof(result)));
    assert(XgbaR73ProveOriginalWarp(0x010009u,24,25,src,1,1,
        0x012302u,26,20,target,2,&result)==XGBA_R73_BAD_ARGUMENT);
    assert(XgbaR73ProveOriginalWarp(0x030009u,24,25,src,1,0,
        0x032302u,26,20,target,2,&result)==XGBA_R73_BAD_ARGUMENT);
    puts("PASS_R73_WORLD_QUALIFIED_WARP_PROOF_AND_FAIL_CLOSED_REFUSALS");
    return 0;
}
