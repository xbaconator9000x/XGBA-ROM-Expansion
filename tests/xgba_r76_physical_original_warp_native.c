#include "../integration/common/xgba_r76_physical_original_warp.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void v16(uint8_t *p,uint16_t x){p[0]=(uint8_t)x;p[1]=(uint8_t)(x>>8);}
int main(void)
{
    uint8_t original[24]={0},id=255u,old;
    v16(original,10u);v16(original+2,11u);original[4]=3u;
    v16(original+8,5u);v16(original+10,4u);original[12]=0u;
    v16(original+16,12u);v16(original+18,8u);original[20]=1u;
    assert(XgbaR76FindOriginalWarpOnTile(original,3,24,25,10,11,3,&id) && id==0u);
    old=id;
    assert(!XgbaR76FindOriginalWarpOnTile(original,3,24,25,10,11,2,&id));
    assert(id==old);
    assert(XgbaR76FindOriginalWarpOnTile(original,3,24,25,5,4,7,&id) && id==1u);
    assert(XgbaR76FindOriginalWarpOnTile(original,3,24,25,12,8,1,&id) && id==2u);
    assert(!XgbaR76FindOriginalWarpOnTile(original,3,24,25,25,8,1,&id));
    assert(!XgbaR76FindOriginalWarpOnTile(original,3,24,25,12,8,1,NULL));
    assert(!XgbaR76FindOriginalWarpOnTile(original,0,24,25,12,8,1,&id));
    assert(!XgbaR76FindOriginalWarpOnTile(original,3,0,25,12,8,1,&id));
    puts("PASS_R76_PHYSICAL_STEP_WARP_TILES_ELEVATION_AND_FAIL_CLOSED");
    return 0;
}
