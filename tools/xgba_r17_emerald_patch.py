#!/usr/bin/env python3
"""R17 decomp-first native Emerald map/tileset externalization.

Source-only patching. The build fixture recompiles a pinned original Emerald,
zeroes exactly the compiled Littleroot map+Petalburg tileset symbol ranges,
and loads the game-owned data from the shared XGBA MMIO provider. No generic
FireRed hardcoded offsets. All sources must be restored in finally blocks.
"""
from __future__ import annotations
from pathlib import Path
import xgba_r16_emerald_decomp_patch as r16

ROOT=Path(__file__).resolve().parents[1]

def patch_emerald_littleroot_sources(emerald:Path,config:Path)->dict[Path,str]:
    e=Path(emerald)
    originals=r16.make_emerald_boot_sources(e)
    world=e/"src/overworld.c"
    newgame=e/"src/new_game.c"
    original_world=world.read_text()
    original_newgame=newgame.read_text()
    originals.update({world:original_world,newgame:original_newgame})
    hook=(ROOT/"integration/emerald/xgba_r17_external_littleroot.inc").read_text()
    hook=hook.replace("__XGBA_GUEST_HEADER__",
                      (ROOT/"integration/fire_red/xgba_guest.h").resolve().as_posix())
    hook=hook.replace("__XGBA_R17_CONFIG__",str(Path(config).resolve()))
    if "__XGBA_" in hook:
        raise r16.AdapterDrift("unresolved Emerald R17 native resource header")
    try:
        main=e/"src/main.c"
        s=main.read_text()
        s=r16.one(s,
          "    XgbaEmeraldProbeRun();\n\n    gSoftResetDisabled = FALSE;",
          "    XgbaEmeraldProbeRun();\n"
          "    /* Bypass only the title/introduction, retain all genuine Emerald\n"
          "     * NewGameInitData, map loading, callbacks, objects and drawing. */\n"
          "    SetSaveBlocksPointers(0);\n"
          "    gSaveBlock2Ptr->playerName[0] = 0xFF;\n"
          "    SetMainCallback2(CB2_NewGame);\n\n    gSoftResetDisabled = FALSE;",
          "actual Emerald direct new-game fixture")
        main.write_text(s)
        s=r16.one(original_newgame,
          "    SetWarpDestination(MAP_GROUP(MAP_INSIDE_OF_TRUCK), MAP_NUM(MAP_INSIDE_OF_TRUCK), WARP_ID_NONE, -1, -1);",
          "    SetWarpDestination(MAP_GROUP(MAP_LITTLEROOT_TOWN), MAP_NUM(MAP_LITTLEROOT_TOWN), WARP_ID_NONE, 10, 10);",
          "original Emerald new game destination")
        newgame.write_text(s)
        s=r16.one(original_world,
          "#define PLAYER_LINK_STATE_IDLE 0x80",
          hook+"\n#define PLAYER_LINK_STATE_IDLE 0x80",
          "source-level native overworld hook")
        s=r16.one(s,
          "        return gMapLayouts[mapLayoutId - 1];",
          "        return XgbaR17Resolve(gMapLayouts[mapLayoutId - 1]);",
          "native Emerald map layout resolver")
        s=r16.one(s,
          "    OverworldBasic();\n    if (fading)\n        SetFieldVBlankCallback();",
          "    OverworldBasic();\n    XgbaR17Tick();\n    if (fading)\n        SetFieldVBlankCallback();",
          "native CB2_Overworld engine frame callback")
        s=r16.one(s,
          "    ResetSafariZoneFlag_();\n    NewGameInitData();",
          "    ResetSafariZoneFlag_();\n"
          "    /* Title/menu ordinarily prepares this before starting new game. */\n"
          "    ScriptContext_Init();\n    NewGameInitData();",
          "native Emerald title-init script prerequisites")
        s=r16.one(s,
          "    gFieldCallback = ExecuteTruckSequence;",
          "    gFieldCallback = FieldCB_DefaultWarpExit;",
          "normal native field loading rather than truck introduction")
        world.write_text(s)
        return originals
    except:
        r16.restore_sources(originals)
        raise
