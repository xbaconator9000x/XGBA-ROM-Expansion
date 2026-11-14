/* R80 completely authored physical-first-hop world/native-slot contract. */
#include "../integration/common/xgba_r80_foreign_map_slot.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static void route(struct XgbaR73SourceWarpRoute *r,
                  uint32_t from,uint32_t to,unsigned x,unsigned y)
{
    memset(r,0,sizeof(*r));r->source_key=from;r->target_key=to;
    r->target_x=(uint16_t)x;r->target_y=(uint16_t)y;
}
int main(void)
{
    struct XgbaR73SourceWarpRoute r={0};
    struct XgbaR80DoorPlan p={0},saved;
    route(&r,0x010009u,0x012302u,2,8);
    assert(XgbaR80PlanFirstHop(&r,&p));
    assert(p.original_to==0x012302u && p.source_group==35u);
    assert(p.native_group==0u && p.native_map==9u &&
           p.original_x==2u && p.original_y==8u);
    saved=p;
    route(&r,0x012302u,0x010009u,16,8);
    assert(XgbaR80PlanFirstHop(&r,&p) && p.source_group==0u &&
           p.source_map==9u);
    p=saved;
    route(&r,0x010009u,0x002302u,2,8);
    assert(!XgbaR80PlanFirstHop(&r,&p) && !memcmp(&p,&saved,sizeof(p)));
    route(&r,0x010009u,0x012303u,2,8);
    assert(!XgbaR80PlanFirstHop(&r,&p));
    route(&r,0x010009u,0x012302u,128,8);
    assert(!XgbaR80PlanFirstHop(&r,&p));
    route(&r,0x010009u,0x012304u,6,12);
    assert(XgbaR80PlanFirstHop(&r,&p));
    assert(XgbaR80NpcVisibleAtSourceArrival(13,14,6,12,8,9));
    assert(!XgbaR80NpcVisibleAtSourceArrival(13,14,6,12,9,2));
    puts("PASS_R80_SOURCE_MAP_KEY_DISTINCT_FROM_REAL_NATIVE_EMERALD_SLOT");
    return 0;
}
