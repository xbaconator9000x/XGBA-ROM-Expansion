/* R19: both original Littleroot and Route 101 simultaneously resident.
 *
 * The native Emerald camera copies connected map rows before crossing the
 * border. These two real external source packs must remain live together;
 * sharing just one R17 staging buffer would corrupt incoming map data.
 *
 * This layer extends, never replaces, the R16 guest/mGBA resource ABI.
 */
/* Hook is source-included before these original Emerald externs. */
extern const struct MapLayout *const gMapLayouts[];
extern const struct MapHeader *const *const gMapGroups[];
#include "constants/vars.h"
#define XGBA_R19_GROUP 0u
#define XGBA_R19_LITTLEROOT 9u
#define XGBA_R19_ROUTE101 16u
#define XGBA_R19_MAP_MAGIC 0x52313450u
#define XGBA_R19_AREA (gHeap + HEAP_SIZE - XGBA_R19_RESERVE)
#define XGBA_R19_ARENA0 (XGBA_R19_AREA)
#define XGBA_R19_ARENA1 (XGBA_R19_AREA + XGBA_R19_ROUTE_OFFSET)
struct XgbaR19MapProof {
    volatile u32 magic,state,group,map,transitions,loads,active,arena;
    volatile u32 grid,stride,border,tiles,palette,metatiles,attributes;
    volatile u32 x,y,boot_ticks,route_visited,littleroot_revisited;
    volatile u32 errors,first_arena,second_arena,game_callback;
};
EWRAM_DATA volatile struct XgbaR19MapProof gXgbaR19MapProof = {0};
EWRAM_DATA char gXgbaR19MapResourceId[32] = {0};
static EWRAM_DATA struct MapHeader sXgbaR19Headers[2] = {0};
static EWRAM_DATA struct MapLayout sXgbaR19Layouts[2] = {0};
static EWRAM_DATA struct Tileset sXgbaR19Tilesets[2] = {0};
static EWRAM_DATA bool8 sXgbaR19Ready[2] = {FALSE,FALSE};
static EWRAM_DATA u8 sXgbaR19LastMap = 0xFF;
static void XgbaR19Reject(void)
{
    gXgbaR19MapProof.magic=XGBA_R17_MAGIC;
    gXgbaR19MapProof.state=0xE19u;
    ++gXgbaR19MapProof.errors;
    /* Fail closed instead of letting Emerald decompress zeroed ROM data. */
    for(;;) {}
}
static s32 XgbaR19Index(u16 group,u16 map)
{
    if(group!=XGBA_R19_GROUP)return -1;
    if(map==XGBA_R19_LITTLEROOT)return 0;
    if(map==XGBA_R19_ROUTE101)return 1;
    return -1;
}
static void XgbaR19Load(unsigned idx)
{
    const u8 *arena;
    const u32 *off;
    u32 length;
    const char *name=idx?"emerald.route101":"emerald.littleroot";
    u32 i;
    const struct MapHeader *source;
    if(idx>1)XgbaR19Reject();
    if(sXgbaR19Ready[idx])return;
    arena=idx?XGBA_R19_ARENA1:XGBA_R19_ARENA0;
    length=idx?XGBA_R19_ROUTE_BYTES:XGBA_R19_LITTLEROOT_BYTES;
    for(i=0;i<32;i++)gXgbaR19MapResourceId[i]=0;
    for(i=0;name[i] && i<31;i++)
        gXgbaR19MapResourceId[i]=name[i];
    if(XgbaGuestFetch(gXgbaR19MapResourceId,(void *)arena,length)!=length)
        XgbaR19Reject();
    off=(const u32 *)arena;
    if(off[0]!=XGBA_R19_MAP_MAGIC || off[1]!=length)
        XgbaR19Reject();
    for(i=2;i<8;i++)
        if(off[i]<32 || off[i]>=length || (off[i]&3u))
            XgbaR19Reject();
    if(off[2]+800u>off[3] || off[3]+8u>off[4] ||
       off[4]>=off[5] || off[5]+512u>off[6] ||
       off[6]>=off[7] || off[7]>=length)
        XgbaR19Reject();
    source=gMapGroups[XGBA_R19_GROUP][idx?XGBA_R19_ROUTE101:XGBA_R19_LITTLEROOT];
    sXgbaR19Headers[idx]=*source;
    sXgbaR19Layouts[idx]=*gMapLayouts[source->mapLayoutId-1];
    sXgbaR19Tilesets[idx]=*sXgbaR19Layouts[idx].secondaryTileset;
    sXgbaR19Layouts[idx].map=(const u16 *)(arena+off[2]);
    sXgbaR19Layouts[idx].border=(const u16 *)(arena+off[3]);
    sXgbaR19Tilesets[idx].tiles=(const u32 *)(arena+off[4]);
    sXgbaR19Tilesets[idx].palettes=(const u16 (*)[16])(arena+off[5]);
    sXgbaR19Tilesets[idx].metatiles=(const u16 *)(arena+off[6]);
    sXgbaR19Tilesets[idx].metatileAttributes=(const u16 *)(arena+off[7]);
    sXgbaR19Layouts[idx].secondaryTileset=&sXgbaR19Tilesets[idx];
    sXgbaR19Headers[idx].mapLayout=&sXgbaR19Layouts[idx];
    sXgbaR19Ready[idx]=TRUE;
    ++gXgbaR19MapProof.loads;
}
static const struct MapHeader *XgbaR19HeaderFor(u16 group,u16 map)
{
    s32 idx=XgbaR19Index(group,map);
    if(idx<0)return gMapGroups[group][map];
    /* BOTH external layouts are needed for seamless connected-map camera
     * rendering. Never evict one while the other is using border tiles. */
    XgbaR19Load(0);
    XgbaR19Load(1);
    return &sXgbaR19Headers[idx];
}
static const struct MapLayout *XgbaR19CurrentLayout(const struct MapLayout *fallback)
{
    s32 idx=XgbaR19Index(gSaveBlock1Ptr->location.mapGroup,
                         gSaveBlock1Ptr->location.mapNum);
    if(idx<0)return fallback;
    XgbaR19Load((unsigned)idx);
    return &sXgbaR19Layouts[idx];
}
static void XgbaR19MapTick(void)
{
    s32 idx;
    const struct Tileset *ts;
    if(!gMapHeader.mapLayout || !gSaveBlock1Ptr)return;
    idx=XgbaR19Index(gSaveBlock1Ptr->location.mapGroup,
                     gSaveBlock1Ptr->location.mapNum);
    if(idx<0)return;
    if(sXgbaR19LastMap!=(u8)idx){
        if(sXgbaR19LastMap!=0xFF)++gXgbaR19MapProof.transitions;
        sXgbaR19LastMap=(u8)idx;
    }
#ifdef XGBA_R19_NATIVE_TEST_OPEN_ROUTE
    /* The vanilla new-game story triggers Professor Birch's rescue when
     * returning south through Route 101. R19 tests actual field camera/
     * collision transitions, not the mandatory introductory cutscene.
     * This conditional test-only flag is NOT part of production XGBA. */
    if(idx && !gXgbaR19MapProof.route_visited)
        VarSet(VAR_ROUTE101_STATE,3);
#endif
    if(idx)gXgbaR19MapProof.route_visited=1;
    if(!idx && gXgbaR19MapProof.route_visited)
        gXgbaR19MapProof.littleroot_revisited=1;
    ts=gMapHeader.mapLayout->secondaryTileset;
    gXgbaR19MapProof.magic=XGBA_R17_MAGIC;
    gXgbaR19MapProof.state=3u;
    gXgbaR19MapProof.group=gSaveBlock1Ptr->location.mapGroup;
    gXgbaR19MapProof.map=gSaveBlock1Ptr->location.mapNum;
    gXgbaR19MapProof.active=idx;
    gXgbaR19MapProof.arena=(u32)(idx?XGBA_R19_ARENA1:XGBA_R19_ARENA0);
    gXgbaR19MapProof.grid=(u32)gBackupMapLayout.map;
    gXgbaR19MapProof.stride=gBackupMapLayout.width;
    gXgbaR19MapProof.border=(u32)gMapHeader.mapLayout->border;
    gXgbaR19MapProof.tiles=(u32)ts->tiles;
    gXgbaR19MapProof.palette=(u32)ts->palettes;
    gXgbaR19MapProof.metatiles=(u32)ts->metatiles;
    gXgbaR19MapProof.attributes=(u32)ts->metatileAttributes;
    gXgbaR19MapProof.x=gSaveBlock1Ptr->pos.x;
    gXgbaR19MapProof.y=gSaveBlock1Ptr->pos.y;
    ++gXgbaR19MapProof.boot_ticks;
    gXgbaR19MapProof.first_arena=(u32)XGBA_R19_ARENA0;
    gXgbaR19MapProof.second_arena=(u32)XGBA_R19_ARENA1;
    gXgbaR19MapProof.game_callback=(u32)gMain.callback2;
}
