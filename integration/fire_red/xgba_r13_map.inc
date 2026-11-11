/* R13: external house floor plan + border, native FireRed map loader.
 * Game requests the entire map payload before a standard DoWarp transition.
 * ROM contains only zeroed placeholders for the actual layout block/border.
 */
#include "fieldmap.h"
#include "field_fadetransition.h"
#include "__XGBA_GUEST__"

#define R13_BYTES 268u
EWRAM_DATA ALIGNED(4) u16 gXgbaR13MapBytes[R13_BYTES / 2] = {0};
EWRAM_DATA char gXgbaR13Id[24] = {0};
static EWRAM_DATA struct MapLayout sR13Layout = {0};
static EWRAM_DATA bool8 sR13Ready = FALSE;
static EWRAM_DATA u8 sR13Pending = 0;
static const char sR13Name[] = "map.pallet.house";
struct XgbaR13Proof {
    volatile u32 magic, state, group, num, ticks, fetches, rejects;
    volatile u32 grid, stride, border, staged, transitions;
};
EWRAM_DATA volatile struct XgbaR13Proof gXgbaR13Proof = {0};
void XgbaR10MarkBoot(u32 stage)
{
    gXgbaR13Proof.magic = 0x58474241u;
    gXgbaR13Proof.state = stage;
}
static const struct MapLayout *XgbaR13Layout(const struct MapLayout *base)
{
    if (sR13Ready && gSaveBlock1Ptr->location.mapGroup ==
        MAP_GROUP(MAP_PALLET_TOWN_PLAYERS_HOUSE_1F) &&
        gSaveBlock1Ptr->location.mapNum ==
        MAP_NUM(MAP_PALLET_TOWN_PLAYERS_HOUSE_1F)) {
        sR13Layout = *base;
        sR13Layout.map = gXgbaR13MapBytes;
        sR13Layout.border = gXgbaR13MapBytes + 130;
        return &sR13Layout;
    }
    return base;
}
static void XgbaR10TickRealOverworld(void)
{
    u8 group = gSaveBlock1Ptr->location.mapGroup;
    u8 num = gSaveBlock1Ptr->location.mapNum;
    bool8 house = group == MAP_GROUP(MAP_PALLET_TOWN_PLAYERS_HOUSE_1F) &&
        num == MAP_NUM(MAP_PALLET_TOWN_PLAYERS_HOUSE_1F);
    bool8 pallet = group == MAP_GROUP(MAP_PALLET_TOWN) &&
        num == MAP_NUM(MAP_PALLET_TOWN);
    gXgbaR13Proof.magic = 0x58474241u;
    ++gXgbaR13Proof.ticks;
    gXgbaR13Proof.group = group;
    gXgbaR13Proof.num = num;
    if (sR13Pending) {
        if ((sR13Pending == 1 && house) || (sR13Pending == 2 && pallet)) {
            ++gXgbaR13Proof.transitions;
            if (pallet) {
                sR13Ready = FALSE;
                for (u32 i = 0; i < R13_BYTES / 2; ++i)
                    gXgbaR13MapBytes[i] = 0;
            }
            sR13Pending = 0;
        } else {
            gXgbaR13Proof.state = 2;
            return;
        }
    }
    gXgbaR13Proof.state = 3;
    gXgbaR13Proof.grid = (u32)VMap.map;
    gXgbaR13Proof.stride = VMap.Xsize;
    gXgbaR13Proof.border = (u32)gMapHeader.mapLayout->border;
    gXgbaR13Proof.staged = house && sR13Ready &&
        gMapHeader.mapLayout == &sR13Layout;
    if (!(gMain.newKeys & SELECT_BUTTON) || gPaletteFade.active)
        return;
    if (pallet) {
        for (u32 i = 0; i < sizeof(sR13Name); ++i)
            gXgbaR13Id[i] = sR13Name[i];
        if (XgbaGuestFetch(gXgbaR13Id, gXgbaR13MapBytes, R13_BYTES) != R13_BYTES) {
            ++gXgbaR13Proof.rejects;
            return; /* no zero-placeholder map entry on failure */
        }
        ++gXgbaR13Proof.fetches;
        sR13Ready = TRUE;
        sR13Pending = 1;
        SetWarpDestination(MAP_GROUP(MAP_PALLET_TOWN_PLAYERS_HOUSE_1F),
            MAP_NUM(MAP_PALLET_TOWN_PLAYERS_HOUSE_1F), -1, 5, 7);
    } else if (house) {
        sR13Pending = 2;
        SetWarpDestination(MAP_GROUP(MAP_PALLET_TOWN),
            MAP_NUM(MAP_PALLET_TOWN), -1, 6, 8);
    } else {
        return;
    }
    gXgbaR13Proof.state = 2;
    DoWarp(); /* genuine game fade/task/WarpIntoMap/CB2_LoadMap */
}
