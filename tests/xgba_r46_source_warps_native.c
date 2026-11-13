/* R46 actual native resolver/synthetic original-ID collision witnesses.
 * Compile with -Wall -Wextra -Werror -fsanitize=address,undefined on host,
 * and with arm-none-eabi-gcc to verify ARM7-safe header semantics.
 */
#include "../integration/common/xgba_r46_source_warps.h"
#include "../integration/common/xgba_r46_paged_warps.h"
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

struct MemoryIndexFixture {
    unsigned reads,deny;
};
static int fake_page(void *ctx,const char *id,uint8_t *dest,uint16_t exact)
{
    struct MemoryIndexFixture *f=(struct MemoryIndexFixture *)ctx;
    const uint8_t *blob;
    unsigned n;
    if(f->deny)return 0;
    if(strcmp(id,"r46.map.000")==0){blob=(const uint8_t *)maps;n=sizeof(maps);}
    else if(strcmp(id,"r46.warp.000")==0){blob=(const uint8_t *)warps;n=sizeof(warps);}
    else return 0;
    if(exact!=n)return 0;
    memcpy(dest,blob,n);
    f->reads++;
    return 1;
}
static void test_paged_guest_16k_source_warps(void)
{
    uint8_t scratch[XGBA_R46_PAGE_BYTES];
    struct MemoryIndexFixture fake={0,0};
    struct XgbaR46PagedIndex loader={
        .fetch=fake_page,.context=&fake,.scratch=scratch,
        .scratch_bytes=sizeof(scratch),.map_count=4,.warp_count=4
    };
    struct XgbaR46Location pos={XgbaR46MapKey(0,0,9),4,5,0,0};
    struct XgbaR46Map target={0};
    struct XgbaR46Portal portal={0x000009u,0x010009u,0,0,0};
    XgbaR46CacheReset(&loader);
    assert(XgbaR46FindMapPaged(&loader,0x000009u,&target)==0);
    assert(target.key==0x000009u);
    assert(XgbaR46FindMapPaged(&loader,0x010009u,&target)==1);
    assert(target.key==0x010009u);
    assert(XgbaR46FindMapPaged(&loader,0x020000u,&target)==3);
    assert(target.key==0x020000u);
    assert(XgbaR46FindMapPaged(&loader,0x020009u,&target)==-1);
    assert(loader.physical_reads==1u);
    assert(loader.cache_hits>=2u);
    assert(XgbaR46TravelPaged(&loader,&pos,0,NULL)==XGBA_R46_ROUTE_MAP_HOLE);
    assert(pos.key==0x000009u);
    assert(XgbaR46TravelPaged(&loader,&pos,0,&portal)==XGBA_R46_ROUTE_OK);
    assert(pos.key==0x010009u);
    assert(XgbaR46TravelPaged(&loader,&pos,0,NULL)==XGBA_R46_ROUTE_OK);
    assert(pos.key==0x01000au);
    assert(XgbaR46TravelPaged(&loader,&pos,0,NULL)==XGBA_R46_ROUTE_OK);
    assert(pos.key==0x010009u);
    assert(XgbaR46TravelPaged(&loader,&pos,7,NULL)==XGBA_R46_ROUTE_WARP_NOT_PRESENT);
    portal.source_key=0x010009u;portal.target_key=0x020000u;
    assert(XgbaR46TravelPaged(&loader,&pos,0,&portal)==XGBA_R46_ROUTE_OK);
    assert(pos.key==0x020000u && pos.x==11 && pos.y==7);
    assert(loader.physical_reads>=4u);
    XgbaR46CacheReset(&loader);
    fake.deny=1;
    assert(XgbaR46FindMapPaged(&loader,0x020000u,&target)==-1);
    assert(XgbaR46TravelPaged(&loader,&pos,0,NULL)==XGBA_R46_ROUTE_MAP_HOLE);
    assert(pos.key==0x020000u);
    puts("PASS_R46_16K_GBA_EWRAM_PAGED_SOURCE_LOOKUPS_AND_ROUTING_FAIL_CLOSED");
}

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
    test_paged_guest_16k_source_warps();
    puts("PASS_R46_NATIVE_SOURCE_AWARE_ORIGINAL_WARP_KEYS_3_WORLDS");
    puts("PASS_R46_NATIVE_EXPLICIT_CROSS_WORLD_PORTALS_AND_SAVE_TAMPER_REJECTION");
    return 0;
}
