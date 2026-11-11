/* R17: original Emerald Littleroot Town with original map grid/border AND
 * complete secondary tileset absent from the 32 MiB ROM. The native Emerald
 * GetMapLayout callback resolves an externally staged, SHA-verified pack.
 * The shared R7 mGBA guest MMIO provider is unchanged.
 */
#include "__XGBA_GUEST_HEADER__"
#include "__XGBA_R17_CONFIG__"
#define XGBA_R17_MAGIC 0x58474241u
#define XGBA_R17_PACK_MAGIC 0x52313450u
#define XGBA_R17_GROUP 0u
#define XGBA_R17_MAP 9u
#define gXgbaR17Arena (gHeap + HEAP_SIZE - XGBA_R17_RESERVE)

struct XgbaR17Proof {
    volatile u32 magic,state,group,num,ticks,reads,x,y,grid,stride,border;
    volatile u32 pack,tiles,palette,metatiles,attributes,callback,errors;
};
EWRAM_DATA volatile struct XgbaR17Proof gXgbaR17Proof = {0};
EWRAM_DATA char gXgbaR17Id[24] = {0};
static EWRAM_DATA struct MapLayout sXgbaR17Layout = {0};
static EWRAM_DATA struct Tileset sXgbaR17Secondary = {0};
static EWRAM_DATA bool8 sXgbaR17Active = FALSE;
static void XgbaR17Refuse(void)
{
    /* No dereference of blank stripped ROM asset on provider failure.
     * A user-facing failure screen is future product work. */
    gXgbaR17Proof.magic=XGBA_R17_MAGIC;
    gXgbaR17Proof.state=0xE17u;
    ++gXgbaR17Proof.errors;
    for(;;) {}
}
static const struct MapLayout *XgbaR17Resolve(const struct MapLayout *base)
{
    u16 group=gSaveBlock1Ptr->location.mapGroup;
    u16 map=gSaveBlock1Ptr->location.mapNum;
    const u32 *offsets;
    u32 i;
    const char name[]="emerald.littleroot";
    if(group!=XGBA_R17_GROUP||map!=XGBA_R17_MAP)
        return base;
    if(!sXgbaR17Active) {
        for(i=0;i<sizeof(name);++i)
            gXgbaR17Id[i]=name[i];
        if(XgbaGuestFetch(gXgbaR17Id,gXgbaR17Arena,XGBA_R17_PACK_SIZE)!=XGBA_R17_PACK_SIZE)
            XgbaR17Refuse();
        offsets=(const u32 *)gXgbaR17Arena;
        if(offsets[0]!=XGBA_R17_PACK_MAGIC || offsets[1]!=XGBA_R17_PACK_SIZE)
            XgbaR17Refuse();
        for(i=2;i<8;++i) {
            if(offsets[i]>=XGBA_R17_PACK_SIZE || (offsets[i]&3))
                XgbaR17Refuse();
        }
        sXgbaR17Layout=*base;
        sXgbaR17Secondary=*base->secondaryTileset;
        sXgbaR17Layout.map=(const u16 *)(gXgbaR17Arena+offsets[2]);
        sXgbaR17Layout.border=(const u16 *)(gXgbaR17Arena+offsets[3]);
        sXgbaR17Secondary.tiles=(const u32 *)(gXgbaR17Arena+offsets[4]);
        sXgbaR17Secondary.palettes=(const u16 (*)[16])(gXgbaR17Arena+offsets[5]);
        sXgbaR17Secondary.metatiles=(const u16 *)(gXgbaR17Arena+offsets[6]);
        sXgbaR17Secondary.metatileAttributes=(const u16 *)(gXgbaR17Arena+offsets[7]);
        sXgbaR17Layout.secondaryTileset=&sXgbaR17Secondary;
        sXgbaR17Active=TRUE;
        ++gXgbaR17Proof.reads;
    }
    return &sXgbaR17Layout;
}
#ifdef XGBA_R18_SAVE_TEST
#include "__XGBA_R18_SAVE__"
#endif
#ifdef XGBA_R19_CONNECTED_MAPS
#include "__XGBA_R19_MAPS__"
#endif
static void XgbaR17Tick(void)
{
    const struct Tileset *ts;
    if(!gSaveBlock1Ptr || !gMapHeader.mapLayout)
        return;
    ts=gMapHeader.mapLayout->secondaryTileset;
    gXgbaR17Proof.magic=XGBA_R17_MAGIC;
    gXgbaR17Proof.state=3u;
    gXgbaR17Proof.group=gSaveBlock1Ptr->location.mapGroup;
    gXgbaR17Proof.num=gSaveBlock1Ptr->location.mapNum;
    ++gXgbaR17Proof.ticks;
    gXgbaR17Proof.x=gSaveBlock1Ptr->pos.x;
    gXgbaR17Proof.y=gSaveBlock1Ptr->pos.y;
    gXgbaR17Proof.grid=(u32)gBackupMapLayout.map;
    gXgbaR17Proof.stride=gBackupMapLayout.width;
    gXgbaR17Proof.border=(u32)gMapHeader.mapLayout->border;
    gXgbaR17Proof.pack=(u32)gXgbaR17Arena;
    gXgbaR17Proof.tiles=(u32)ts->tiles;
    gXgbaR17Proof.palette=(u32)ts->palettes;
    gXgbaR17Proof.metatiles=(u32)ts->metatiles;
    gXgbaR17Proof.attributes=(u32)ts->metatileAttributes;
    gXgbaR17Proof.callback=(u32)gMain.callback2;
#ifdef XGBA_R18_SAVE_TEST
    XgbaR18Tick();
#endif
#ifdef XGBA_R19_CONNECTED_MAPS
    XgbaR19MapTick();
#endif
}
