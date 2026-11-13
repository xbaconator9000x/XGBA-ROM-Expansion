/* R46 actual native resolver/synthetic original-ID collision witnesses.
 * Compile with -Wall -Wextra -Werror -fsanitize=address,undefined on host,
 * and with arm-none-eabi-gcc to verify ARM7-safe header semantics.
 */
#include "../integration/common/xgba_r46_source_warps.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>
static const struct XgbaR46Map maps[] = {
    {0x000009u,20,20,0,1,0x220u}, /* Emerald original map 0:9 */
    {0x010009u,24,25,1,1,0x340u}, /* Rocket original map 0:9 */
    {0x01000au,24,22,2,1,0x390u},
    {0x020000u,30,39,3,1,0x410u}  /* HnS original map 0:0 */
};
static const struct XgbaR46Warp warps[] = {
    {4,5,0,0,10,0},   /* Emerald 0:9 -> Emerald 0:10 (not present) */
    {6,9,0,0,10,0},   /* Rocket 0:9 -> Rocket 0:10 */
    {8,12,0,0,9,0},   /* Rocket 0:10 -> Rocket 0:9 */
    {11,7,1,0,0,0}   /* HeartSoul New Bark self-entry */
};
int main(void)
{
    struct XgbaR46Location pos={0x000009u,4,5,0,0},saved_before;
    struct XgbaR46SaveLocation saved={0};
    struct XgbaR46Portal bridge={0x000009u,0x010009u,0,0,0};
    assert(XgbaR46ValidMap(maps,4,warps,4));
    assert(XgbaR46FindMap(maps,4,0x000009u)==0);
    assert(XgbaR46FindMap(maps,4,0x010009u)==1);
    assert(XgbaR46FindMap(maps,4,0x020000u)==3);
    assert(XgbaR46FindMap(maps,4,0x020009u)==-1);
    assert(XgbaR46FindMap(maps,4,0xff000009u)==-1);
    assert(XgbaR46Source(maps[2].key)==XGBA_R46_WORLD_ROCKET);
    assert(XgbaR46Group(maps[2].key)==0 && XgbaR46MapNumber(maps[2].key)==10);
    saved_before=pos;
    /* The vanilla Emerald warp must not silently land in Rocket 0:9 or
     * Rocket 0:10 just because those original numeric keys collide. */
    assert(XgbaR46Target(maps,4,warps,4,&pos,0,NULL)==XGBA_R46_ROUTE_MAP_HOLE);
    assert(memcmp(&saved_before,&pos,sizeof(pos))==0);
    assert(XgbaR46Target(maps,4,warps,4,&pos,10,NULL)==XGBA_R46_ROUTE_WARP_NOT_PRESENT);
    assert(memcmp(&saved_before,&pos,sizeof(pos))==0);
    /* Only an explicitly authored portal may change the source dimension. */
    assert(XgbaR46Target(maps,4,warps,4,&pos,0,&bridge)==XGBA_R46_ROUTE_OK);
    assert(pos.key==0x010009u && pos.x==6 && pos.y==9);
    assert(XgbaR46Target(maps,4,warps,4,&pos,0,NULL)==XGBA_R46_ROUTE_OK);
    assert(pos.key==0x01000au && pos.x==8 && pos.y==12);
    assert(XgbaR46Target(maps,4,warps,4,&pos,0,NULL)==XGBA_R46_ROUTE_OK);
    assert(pos.key==0x010009u && pos.x==6);
    assert(XgbaR46EncodeLocation(maps,4,&pos,&saved));
    memset(&pos,0,sizeof(pos));
    assert(XgbaR46DecodeLocation(maps,4,&saved,&pos));
    assert(pos.key==0x010009u && pos.x==6);
    saved.key=0x000009u; /* a wrong-world save token must fail checksum */
    assert(!XgbaR46DecodeLocation(maps,4,&saved,&pos));
    saved.key=0x010009u;
    saved.checksum=XgbaR46SaveChecksum(&saved);
    saved.x=900; /* out of range even with recalculated checksum */
    saved.checksum=XgbaR46SaveChecksum(&saved);
    assert(!XgbaR46DecodeLocation(maps,4,&saved,&pos));
    /* Valid explicit HnS portal, never an implicit numeric alias. */
    bridge.source_key=0x010009u;
    bridge.target_key=0x020000u;
    assert(XgbaR46Target(maps,4,warps,4,&pos,0,&bridge)==XGBA_R46_ROUTE_OK);
    assert(pos.key==0x020000u && pos.x==11 && pos.y==7);
    bridge.reserved=1; /* malformed portal rejected without state change */
    assert(XgbaR46Target(maps,4,warps,4,&pos,0,&bridge)==XGBA_R46_ROUTE_BAD_PORTAL);
    assert(pos.key==0x020000u);
    puts("PASS_R46_NATIVE_SOURCE_AWARE_ORIGINAL_WARP_KEYS_3_WORLDS");
    puts("PASS_R46_NATIVE_EXPLICIT_CROSS_WORLD_PORTALS_AND_SAVE_TAMPER_REJECTION");
    return 0;
}
