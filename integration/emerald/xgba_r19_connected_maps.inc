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
#include "../common/xgba_ewram_lease.h"
#ifdef XGBA_R28_THREE_MAPS
#include "../common/xgba_map_cache.h"
#define XGBA_R19_MAP_COUNT 3u
#define XGBA_R28_OLDALE 10u
/* Test-only: physical connected-map traversal must not be interrupted by
 * random wild battle while no starter/party is set up in the native fixture. */
extern void DisableWildEncounters(bool8 disabled);
#else
#define XGBA_R19_MAP_COUNT 2u
#endif
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
    /* R20: appended only; original R19 native proof ABI is unchanged. */
    volatile u32 arena_owner,arena_epoch,world_claims,battle_claims;
    /* R26 appended, all historical probe offsets retained. */
    volatile u32 r26_busy_refusals,r26_map_borrows,r26_epoch,r26_live,r26_errors;
#ifdef XGBA_R28_THREE_MAPS
    volatile u32 r28_hits,r28_misses,r28_evictions,r28_refusals,r28_loads;
    volatile u32 r28_active_slot,r28_slot0_key,r28_slot1_key,r28_generation;
#endif
};
EWRAM_DATA volatile struct XgbaR19MapProof gXgbaR19MapProof = {0};
EWRAM_DATA char gXgbaR19MapResourceId[32] = {0};
static EWRAM_DATA struct MapHeader sXgbaR19Headers[XGBA_R19_MAP_COUNT] = {0};
static EWRAM_DATA struct MapLayout sXgbaR19Layouts[XGBA_R19_MAP_COUNT] = {0};
static EWRAM_DATA struct Tileset sXgbaR19Tilesets[XGBA_R19_MAP_COUNT] = {0};
static EWRAM_DATA bool8 sXgbaR19Ready[XGBA_R19_MAP_COUNT] = {0};
#ifdef XGBA_R28_THREE_MAPS
static EWRAM_DATA struct XgbaMapCache sXgbaR28MapCache;
#endif
static EWRAM_DATA u8 sXgbaR19LastMap = 0xFF;

/* R20 tracks the OWNERSHIP of the shared protected 16 KiB region.
 * A valid cache identity is tied to an owning phase, not just a boolean.
 * Nothing here returns the tail to Emerald's allocator: that would require
 * changing InitHeap's actual bounds, with an independently audited lifetime.
 */
#define XGBA_R20_ARENA_WORLD 1u
#define XGBA_R20_ARENA_BATTLE 2u
static EWRAM_DATA u32 sXgbaR20ArenaOwner;
static EWRAM_DATA u32 sXgbaR20ArenaEpoch;
static EWRAM_DATA u32 sXgbaR20WorldClaims;
static EWRAM_DATA u32 sXgbaR20BattleClaims;
static EWRAM_DATA struct XgbaArenaLease sXgbaR26ArenaLease;
static void XgbaR19Reject(void);

static void XgbaR20ClaimWorldArena(void)
{
    if (XgbaLeaseSwitch(&sXgbaR26ArenaLease,XGBA_R20_ARENA_WORLD)
        != XGBA_LEASE_OK)
        XgbaR19Reject();
    if (sXgbaR20ArenaOwner == XGBA_R20_ARENA_WORLD)
        return;
    /* A previous battle left compressed sprite pointers into the arena.
     * Each sprite accessor must revalidate ownership before trusting them. */
    sXgbaR19Ready[0] = FALSE;
    sXgbaR19Ready[1] = FALSE;
#ifdef XGBA_R28_THREE_MAPS
    sXgbaR19Ready[2] = FALSE;
    if(XgbaCacheInvalidate(&sXgbaR28MapCache)!=XGBA_CACHE_HIT)
        XgbaR19Reject();
#endif
    sXgbaR20ArenaOwner = XGBA_R20_ARENA_WORLD;
    sXgbaR20ArenaEpoch = sXgbaR26ArenaLease.generation;
    ++sXgbaR20WorldClaims;
}

static void XgbaR20ClaimBattleArena(void)
{
    if (XgbaLeaseSwitch(&sXgbaR26ArenaLease,XGBA_R20_ARENA_BATTLE)
        != XGBA_LEASE_OK)
        XgbaR19Reject();
    if (sXgbaR20ArenaOwner == XGBA_R20_ARENA_BATTLE)
        return;
    /* Maps must not be considered resident after sprites claim their bytes. */
    sXgbaR19Ready[0] = FALSE;
    sXgbaR19Ready[1] = FALSE;
#ifdef XGBA_R28_THREE_MAPS
    sXgbaR19Ready[2] = FALSE;
    if(XgbaCacheInvalidate(&sXgbaR28MapCache)!=XGBA_CACHE_HIT)
        XgbaR19Reject();
#endif
    sXgbaR20ArenaOwner = XGBA_R20_ARENA_BATTLE;
    sXgbaR20ArenaEpoch = sXgbaR26ArenaLease.generation;
    ++sXgbaR20BattleClaims;
}
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
#ifdef XGBA_R28_THREE_MAPS
    if(map==XGBA_R28_OLDALE)return 2;
#endif
    return -1;
}
static void XgbaR19Load(unsigned idx)
{
    const u8 *arena;
    const u32 *off;
    u32 length;
    const char *name=idx?"emerald.route101":"emerald.littleroot";
    u32 slot=idx;
#ifdef XGBA_R28_THREE_MAPS
    u32 evicted=XGBA_MAP_CACHE_NONE;
    u32 protected_key=XGBA_MAP_CACHE_NONE;
    enum XgbaMapCacheResult choice;
    s32 active;
#endif
    u32 i;
    const struct MapHeader *source;
    struct XgbaLeaseToken lease;
    if(idx>=XGBA_R19_MAP_COUNT)XgbaR19Reject();
    XgbaR20ClaimWorldArena();
#ifdef XGBA_R28_THREE_MAPS
    active=gSaveBlock1Ptr?
        XgbaR19Index(gSaveBlock1Ptr->location.mapGroup,
                     gSaveBlock1Ptr->location.mapNum):-1;
    if(active>=0)protected_key=(u32)active;
    choice=XgbaCacheBegin(&sXgbaR28MapCache,idx,protected_key,
                          &slot,&evicted);
    if(choice==XGBA_CACHE_HIT) {
        if(!sXgbaR19Ready[idx])XgbaR19Reject();
        return;
    }
    if(choice!=XGBA_CACHE_MISS)XgbaR19Reject();
    if(evicted!=XGBA_MAP_CACHE_NONE) {
        if(evicted>=XGBA_R19_MAP_COUNT)XgbaR19Reject();
        sXgbaR19Ready[evicted]=FALSE;
        /* Source descriptors of evicted maps are stale. Never evict active. */
        sXgbaR19Layouts[evicted].map=0;
        sXgbaR19Layouts[evicted].border=0;
    }
    if(idx==2)name="emerald.oldale";
#else
    if(sXgbaR19Ready[idx])return;
#endif
    if(XgbaLeaseBorrow(&sXgbaR26ArenaLease,XGBA_R20_ARENA_WORLD,&lease)
       != XGBA_LEASE_OK) XgbaR19Reject();
#ifdef XGBA_R26_LEASE_PROOF
    /* Actual original-game asset load attempts a forbidden phase switch
     * while its source bytes are borrowed; ownership/epoch cannot change. */
    if(XgbaLeaseSwitch(&sXgbaR26ArenaLease,XGBA_R20_ARENA_BATTLE)
       != XGBA_LEASE_BUSY) XgbaR19Reject();
    ++gXgbaR19MapProof.r26_busy_refusals;
#endif
    arena=slot?XGBA_R19_ARENA1:XGBA_R19_ARENA0;
    length=idx?XGBA_R19_ROUTE_BYTES:XGBA_R19_LITTLEROOT_BYTES;
#ifdef XGBA_R28_THREE_MAPS
    if(idx==2)length=XGBA_R28_OLDALE_BYTES;
    if(length>(slot?XGBA_R19_RESERVE-XGBA_R19_ROUTE_OFFSET:
                         XGBA_R19_ROUTE_OFFSET))XgbaR19Reject();
#endif
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
#ifdef XGBA_R28_THREE_MAPS
    source=gMapGroups[XGBA_R19_GROUP][idx==2?XGBA_R28_OLDALE:
           (idx==1?XGBA_R19_ROUTE101:XGBA_R19_LITTLEROOT)];
#else
    source=gMapGroups[XGBA_R19_GROUP][idx?XGBA_R19_ROUTE101:XGBA_R19_LITTLEROOT];
#endif
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
    if(XgbaLeaseValidate(&sXgbaR26ArenaLease,&lease)!=XGBA_LEASE_OK ||
       XgbaLeaseRelease(&sXgbaR26ArenaLease,&lease)!=XGBA_LEASE_OK)
        XgbaR19Reject();
#ifdef XGBA_R26_LEASE_PROOF
    ++gXgbaR19MapProof.r26_map_borrows;
    gXgbaR19MapProof.r26_epoch=sXgbaR26ArenaLease.generation;
    gXgbaR19MapProof.r26_live=sXgbaR26ArenaLease.borrowed;
#endif
#ifdef XGBA_R28_THREE_MAPS
    if(XgbaCacheCommit(&sXgbaR28MapCache,slot,idx)!=XGBA_CACHE_HIT)
        XgbaR19Reject();
#endif
    sXgbaR19Ready[idx]=TRUE;
    ++gXgbaR19MapProof.loads;
}
/* Returning from battle bypasses a full map warp: the old map descriptors
 * can still point into an arena overwritten by compressed battle sprites.
 * Reacquire BOTH connected packs BEFORE Emerald's ReturnToFieldLocal calls
 * ResetScreenForMapLoad / ResumeMap / InitMapView, not after CB2_Overworld.
 */
static void XgbaR20PrepareReturnToField(void)
{
    if (!gSaveBlock1Ptr)
        return;
    if (XgbaR19Index(gSaveBlock1Ptr->location.mapGroup,
                      gSaveBlock1Ptr->location.mapNum) < 0)
        return;
#ifdef XGBA_R28_THREE_MAPS
    {
        s32 index=XgbaR19Index(gSaveBlock1Ptr->location.mapGroup,
                               gSaveBlock1Ptr->location.mapNum);
        if(index==2) { XgbaR19Load(1); XgbaR19Load(2); }
        else { XgbaR19Load(0); XgbaR19Load(1); }
    }
#else
    XgbaR19Load(0);
    XgbaR19Load(1);
#endif
}
static const struct MapHeader *XgbaR19HeaderFor(u16 group,u16 map)
{
    s32 idx=XgbaR19Index(group,map);
    if(idx<0)return gMapGroups[group][map];
    /* BOTH external layouts are needed for seamless connected-map camera
     * rendering. Never evict one while the other is using border tiles. */
#ifdef XGBA_R28_THREE_MAPS
    /* Original connected-map camera owns and copies neighbour data. Keep
     * the current source protected, while fetching the requested neighbour. */
    if(idx==0) { XgbaR19Load(0); XgbaR19Load(1); }
    else if(idx==2) { XgbaR19Load(1); XgbaR19Load(2); }
    else XgbaR19Load(1);
#else
    XgbaR19Load(0);
    XgbaR19Load(1);
#endif
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
#ifdef XGBA_R28_THREE_MAPS
    /* Original Emerald pathfinding/collision stay untouched; only its
     * random-encounter battle trigger is suppressed for the map-only proof. */
    DisableWildEncounters(TRUE);
#endif
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
    if(idx==1 && !gXgbaR19MapProof.route_visited)
        VarSet(VAR_ROUTE101_STATE,3);
#endif
    if(idx==1)gXgbaR19MapProof.route_visited=1;
    if(!idx && gXgbaR19MapProof.route_visited)
        gXgbaR19MapProof.littleroot_revisited=1;
    ts=gMapHeader.mapLayout->secondaryTileset;
    gXgbaR19MapProof.magic=XGBA_R17_MAGIC;
    gXgbaR19MapProof.state=3u;
    gXgbaR19MapProof.group=gSaveBlock1Ptr->location.mapGroup;
    gXgbaR19MapProof.map=gSaveBlock1Ptr->location.mapNum;
    gXgbaR19MapProof.active=idx;
#ifdef XGBA_R28_THREE_MAPS
    {
        s32 slot=XgbaCacheFind(&sXgbaR28MapCache,(u32)idx);
        if(slot<0)XgbaR19Reject();
        gXgbaR19MapProof.arena=(u32)(slot?XGBA_R19_ARENA1:XGBA_R19_ARENA0);
        gXgbaR19MapProof.r28_active_slot=(u32)slot;
        gXgbaR19MapProof.r28_hits=sXgbaR28MapCache.hits;
        gXgbaR19MapProof.r28_misses=sXgbaR28MapCache.misses;
        gXgbaR19MapProof.r28_evictions=sXgbaR28MapCache.evictions;
        gXgbaR19MapProof.r28_refusals=sXgbaR28MapCache.refusals;
        gXgbaR19MapProof.r28_loads=sXgbaR28MapCache.loads;
        gXgbaR19MapProof.r28_slot0_key=sXgbaR28MapCache.slots[0].key;
        gXgbaR19MapProof.r28_slot1_key=sXgbaR28MapCache.slots[1].key;
        gXgbaR19MapProof.r28_generation=sXgbaR28MapCache.generation;
    }
#else
    gXgbaR19MapProof.arena=(u32)(idx?XGBA_R19_ARENA1:XGBA_R19_ARENA0);
#endif
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
    gXgbaR19MapProof.arena_owner=sXgbaR20ArenaOwner;
    gXgbaR19MapProof.arena_epoch=sXgbaR20ArenaEpoch;
    gXgbaR19MapProof.world_claims=sXgbaR20WorldClaims;
    gXgbaR19MapProof.battle_claims=sXgbaR20BattleClaims;
}
