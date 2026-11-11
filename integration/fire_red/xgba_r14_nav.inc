/* R14: native connected maps + externally backed secondary tilesets. */
#include "fieldmap.h"
#include "constants/flags.h"
#include "constants/vars.h"
#include "__XGBA_GUEST__"
#include "__R14_CONFIG__"
#define R14_MAGIC 0x58474241u
#define R14_PACK_MAGIC 0x52313450u
EWRAM_DATA ALIGNED(4) u8 gXgbaR14Route[R14_ROUTE_SIZE] = {0};
EWRAM_DATA ALIGNED(4) u8 gXgbaR14House[R14_HOUSE_SIZE] = {0};
EWRAM_DATA char gXgbaR14Id[24] = {0};
static EWRAM_DATA struct MapLayout sR14PalletLayout = {0};
static EWRAM_DATA struct MapLayout sR14RouteLayout = {0};
static EWRAM_DATA struct MapLayout sR14HouseLayout = {0};
static EWRAM_DATA struct Tileset sR14Outdoor = {0};
static EWRAM_DATA struct Tileset sR14Indoor = {0};
static EWRAM_DATA struct MapHeader sR14RouteHeader = {0};
static EWRAM_DATA bool8 sR14RouteReady = FALSE;
static EWRAM_DATA bool8 sR14HouseReady = FALSE;
struct XgbaR14Proof {
    volatile u32 magic,state,group,num,ticks,reads,x,y,grid,stride,border;
    volatile u32 pack,tiles,palette,metatiles,attributes;
};
EWRAM_DATA volatile struct XgbaR14Proof gXgbaR14Proof = {0};
void XgbaR10MarkBoot(u32 stage) {
    gXgbaR14Proof.magic=R14_MAGIC;
    gXgbaR14Proof.state=stage;
}
static void R14Fetch(const char *name,u8 *dst,u32 size)
{
    u32 i;
    for(i=0;name[i] && i+1<sizeof(gXgbaR14Id);++i)
        gXgbaR14Id[i]=name[i];
    gXgbaR14Id[i]=0;
    if(XgbaGuestFetch(gXgbaR14Id,dst,size)!=size ||
       ((u32*)dst)[0]!=R14_PACK_MAGIC || ((u32*)dst)[1]!=size) {
        /* Integration fixture fails closed before dereferencing stripped data. */
        gXgbaR14Proof.state=0xE14;
        for(;;) {}
    }
    ++gXgbaR14Proof.reads;
}
static void R14Tileset(struct Tileset *out,const struct Tileset *base,u8 *pack)
{
    const u32 *h=(const u32*)pack;
    *out=*base;
    out->tiles=(const u32*)(pack+h[4]);
    out->palettes=(const u16(*)[16])(pack+h[5]);
    out->metatiles=(const u16*)(pack+h[6]);
    out->metatileAttributes=(const u32*)(pack+h[7]);
}
static const struct MapLayout *R14Resolve(const struct MapLayout *base,u16 group,u16 num)
{
    bool8 pallet=group==MAP_GROUP(MAP_PALLET_TOWN) && num==MAP_NUM(MAP_PALLET_TOWN);
    bool8 route=group==MAP_GROUP(MAP_ROUTE1) && num==MAP_NUM(MAP_ROUTE1);
    bool8 house=group==MAP_GROUP(MAP_PALLET_TOWN_PLAYERS_HOUSE_1F) &&
        num==MAP_NUM(MAP_PALLET_TOWN_PLAYERS_HOUSE_1F);
    if(pallet||route) {
        if(!sR14RouteReady) {
            R14Fetch("map.route1.tiles",gXgbaR14Route,R14_ROUTE_SIZE);
            R14Tileset(&sR14Outdoor,base->secondaryTileset,gXgbaR14Route);
            sR14RouteReady=TRUE;
        }
        struct MapLayout *out=route?&sR14RouteLayout:&sR14PalletLayout;
        *out=*base;
        out->secondaryTileset=&sR14Outdoor;
        if(route) {
            const u32 *h=(const u32*)gXgbaR14Route;
            out->map=(const u16*)(gXgbaR14Route+h[2]);
            out->border=(const u16*)(gXgbaR14Route+h[3]);
        }
        return out;
    }
    if(house) {
        if(!sR14HouseReady) {
            R14Fetch("map.house.tiles",gXgbaR14House,R14_HOUSE_SIZE);
            R14Tileset(&sR14Indoor,base->secondaryTileset,gXgbaR14House);
            sR14HouseReady=TRUE;
        }
        const u32 *h=(const u32*)gXgbaR14House;
        sR14HouseLayout=*base;
        sR14HouseLayout.map=(const u16*)(gXgbaR14House+h[2]);
        sR14HouseLayout.border=(const u16*)(gXgbaR14House+h[3]);
        sR14HouseLayout.secondaryTileset=&sR14Indoor;
        return &sR14HouseLayout;
    }
    return base;
}
static const struct MapHeader *R14Header(const struct MapHeader *base,u16 group,u16 num)
{
    /* The native connected-map renderer reads neighboring Route 1's layout
     * before crossing the boundary; it must see the staged layout too. */
    if(group==MAP_GROUP(MAP_ROUTE1) && num==MAP_NUM(MAP_ROUTE1)) {
        sR14RouteHeader=*base;
        sR14RouteHeader.mapLayout=R14Resolve(base->mapLayout,group,num);
        return &sR14RouteHeader;
    }
    return base;
}
static void XgbaR10TickRealOverworld(void)
{
    u16 group=gSaveBlock1Ptr->location.mapGroup;
    u16 num=gSaveBlock1Ptr->location.mapNum;
    const struct Tileset *ts=gMapHeader.mapLayout->secondaryTileset;
    gXgbaR14Proof.magic=R14_MAGIC;
    gXgbaR14Proof.state=3;
    gXgbaR14Proof.group=group;
    gXgbaR14Proof.num=num;
    ++gXgbaR14Proof.ticks;
    gXgbaR14Proof.x=gSaveBlock1Ptr->pos.x;
    gXgbaR14Proof.y=gSaveBlock1Ptr->pos.y;
    gXgbaR14Proof.grid=(u32)VMap.map;
    gXgbaR14Proof.stride=VMap.Xsize;
    gXgbaR14Proof.border=(u32)gMapHeader.mapLayout->border;
    gXgbaR14Proof.pack=(u32)(group==4 && num==0 ? gXgbaR14House:gXgbaR14Route);
    gXgbaR14Proof.tiles=(u32)ts->tiles;
    gXgbaR14Proof.palette=(u32)ts->palettes;
    gXgbaR14Proof.metatiles=(u32)ts->metatiles;
    gXgbaR14Proof.attributes=(u32)ts->metatileAttributes;
}
