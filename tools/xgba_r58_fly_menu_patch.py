#!/usr/bin/env python3
"""R58 patch the ACTUAL pinned Emerald region-map Fly UI.

The player presses SELECT on the native Fly map to choose the next original
source world, then A to confirm. No D-pad debug source switching, no
substitute dialogue. R58's native read-only resource preflight refuses missing
original sprite/tileset bytes before any destination or pending world is set.
"""
from __future__ import annotations
from pathlib import Path
import xgba_r16_emerald_decomp_patch as r16

def patch_native_original_fly_region_map(emerald:Path)->dict[Path,str]:
    path=Path(emerald)/"src/region_map.c"
    original=path.read_text()
    s=original
    s=r16.one(s,
      "static bool32 sDrawFlyDestTextWindow;",
      """static bool32 sDrawFlyDestTextWindow;
/* R58 real Fly UI/selector, not a frame-probe or debug-only shortcut. */
extern u8 XgbaR58GetOfferedOriginalFlyWorld(void);
extern bool8 XgbaR58QueuePlayerSelectedOriginalFly(void);
static bool8 sXgbaR58ForeignChoice = FALSE;
static bool8 sXgbaR58SourceUnavailable = FALSE;
static const u8 sXgbaR58RocketName[] = _("ROCKET KANTO");
static const u8 sXgbaR58JohtoName[] = _("JOHTO GOLDENROD");
static const u8 sXgbaR58EmeraldName[] = _("RETURN TO HOENN");
static const u8 sXgbaR58SourceMissing[] = _("SOURCE NOT READY");""",
      "R58 user-visible foreign source Fly labels")
    s=r16.one(s,
      "        sFlyMap = Alloc(sizeof(*sFlyMap));",
      "        sXgbaR58ForeignChoice = FALSE;\n"
      "        sXgbaR58SourceUnavailable = FALSE;\n"
      "        sFlyMap = Alloc(sizeof(*sFlyMap));",
      "R58 reset Fly choice before actual native Fly map opens")
    s=r16.one(s,
      "static void DrawFlyDestTextWindow(void)\n{",
      """static void XgbaR58DrawOriginalSourceFlyName(void)
{
    const u8 *title;
    u8 world = XgbaR58GetOfferedOriginalFlyWorld();
    if (sXgbaR58SourceUnavailable)
        title = sXgbaR58SourceMissing;
    else if (world == 1)
        title = sXgbaR58RocketName;
    else if (world == 2)
        title = sXgbaR58JohtoName;
    else
        title = sXgbaR58EmeraldName;
    ClearStdWindowAndFrameToTransparent(WIN_MAPSEC_NAME_TALL, FALSE);
    DrawStdFrameWithCustomTileAndPalette(WIN_MAPSEC_NAME, FALSE, 101, 13);
    FillWindowPixelBuffer(WIN_MAPSEC_NAME, PIXEL_FILL(1));
    AddTextPrinterParameterized(WIN_MAPSEC_NAME, FONT_NORMAL,
                                title, 0, 1, 0, NULL);
    ScheduleBgCopyTilemapToVram(0);
    sDrawFlyDestTextWindow = FALSE;
}
static void DrawFlyDestTextWindow(void)
{
    if (sXgbaR58ForeignChoice)
    {
        XgbaR58DrawOriginalSourceFlyName();
        return;
    }""",
      "R58 real native Fly UI original-source name panel")
    s=r16.one(s,
      "static void CB_HandleFlyMapInput(void)\n{\n    if (sFlyMap->state == 0)\n    {\n",
      """static void CB_HandleFlyMapInput(void)
{
    if (sFlyMap->state == 0)
    {
        if (gMain.newKeys & SELECT_BUTTON)
        {
            if (XgbaR58GetOfferedOriginalFlyWorld() < 3)
            {
                sXgbaR58ForeignChoice = !sXgbaR58ForeignChoice;
                sXgbaR58SourceUnavailable = FALSE;
                m4aSongNumStart(SE_SELECT);
                DrawFlyDestTextWindow();
                return;
            }
        }
""",
      "R58 actual SELECT key inside original Fly map")
    s=r16.one(s,
      "        case MAP_INPUT_A_BUTTON:\n            if (sFlyMap->regionMap.mapSecType == MAPSECTYPE_CITY_CANFLY",
      """        case MAP_INPUT_A_BUTTON:
            if (sXgbaR58ForeignChoice)
            {
                /* Commit only on the player's ACTUAL A selection and after
                 * native SHA/CRC-backed source preflight. Refuse bad art
                 * without quitting the map or mutating the destination. */
                if (XgbaR58QueuePlayerSelectedOriginalFly())
                {
                    m4aSongNumStart(SE_SELECT);
                    sFlyMap->choseFlyLocation = TRUE;
                    SetFlyMapCallback(CB_ExitFlyMap);
                }
                else
                {
                    sXgbaR58SourceUnavailable = TRUE;
                    DrawFlyDestTextWindow();
                }
                break;
            }
            if (sFlyMap->regionMap.mapSecType == MAPSECTYPE_CITY_CANFLY""",
      "R58 source Fly A confirms only with original page preflight")
    s=r16.one(s,
      "                switch (sFlyMap->regionMap.mapSecId)\n                {",
      "                if (!sXgbaR58ForeignChoice)\n"
      "                switch (sFlyMap->regionMap.mapSecId)\n                {",
      "R58 do not overwrite source-qualified selected warp with Hoenn HealLocation")
    path.write_text(s)
    return {path:original}
