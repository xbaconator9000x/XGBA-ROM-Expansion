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

def patch_emerald_littleroot_sources(emerald:Path,config:Path,*,r18_save:bool=False,r19_connected:bool=False,r19_battle:bool=False,r26_leases:bool=False)->dict[Path,str]:
    e=Path(emerald)
    originals=r16.make_emerald_boot_sources(e)
    world=e/"src/overworld.c"
    newgame=e/"src/new_game.c"
    original_world=world.read_text()
    original_newgame=newgame.read_text()
    originals.update({world:original_world,newgame:original_newgame})
    if r26_leases and not (r19_connected and r19_battle):
        raise r16.AdapterDrift("R26 phase lease proof requires real map and battle integration")
    hook=(ROOT/"integration/emerald/xgba_r17_external_littleroot.inc").read_text()
    if r26_leases:
        hook="#define XGBA_R26_LEASE_PROOF 1\n"+hook
    hook=hook.replace("__XGBA_GUEST_HEADER__",
                      (ROOT/"integration/fire_red/xgba_guest.h").resolve().as_posix())
    hook=hook.replace("__XGBA_R17_CONFIG__",str(Path(config).resolve()))
    hook=hook.replace("__XGBA_R18_SAVE__",
                      (ROOT/"integration/emerald/xgba_r18_save.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R40_SCRIPT__",
                      (ROOT/"integration/emerald/xgba_r40_external_script.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R42_EVENT__",
                      (ROOT/"integration/emerald/xgba_r42_two_source_events.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R48_NPC_BRIDGE__",
                      (ROOT/"integration/emerald/xgba_r48_original_npc_scripts.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R19_MAPS__",
                      (ROOT/"integration/emerald/xgba_r19_connected_maps.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R19_BATTLE__",
                      (ROOT/"integration/emerald/xgba_r19_battle_assets.inc").resolve().as_posix())
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
        if r18_save:
            s=r16.one(s,
                "    SetSaveBlocksPointers(0);\n"
                "    gSaveBlock2Ptr->playerName[0] = 0xFF;\n"
                "    SetMainCallback2(CB2_NewGame);",
                "    SetSaveBlocksPointers(0);\n"
                "    if (XgbaR18TryContinue())\n"
                "        SetMainCallback2(CB2_ContinueSavedGame);\n"
                "    else {\n"
                "        gSaveBlock2Ptr->playerName[0] = 0xFF;\n"
                "        SetMainCallback2(CB2_NewGame);\n"
                "    }",
                "original Emerald save/continue boot selection")
            s=r16.one(s,"void AgbMain(void)\n{",
                "extern bool8 XgbaR18TryContinue(void);\n"
                "void AgbMain(void)\n{",
                "original Emerald Flash loading declaration")
        main.write_text(s)
        s=r16.one(original_newgame,
          "    SetWarpDestination(MAP_GROUP(MAP_INSIDE_OF_TRUCK), MAP_NUM(MAP_INSIDE_OF_TRUCK), WARP_ID_NONE, -1, -1);",
          "    SetWarpDestination(MAP_GROUP(MAP_LITTLEROOT_TOWN), MAP_NUM(MAP_LITTLEROOT_TOWN), WARP_ID_NONE, 10, 10);",
          "original Emerald new game destination")
        if r19_connected:
            # Start directly near the original north connection in this
            # *test fixture*. Ordinary Emerald camera, map boundaries and
            # direction input are not mocked or changed.
            s=r16.one(s,
                "WARP_ID_NONE, 10, 10);",
                "WARP_ID_NONE, 10, 1);",
                "start close to original Littleroot-Route101 boundary")
        newgame.write_text(s)
        s=r16.one(original_world,
          "#define PLAYER_LINK_STATE_IDLE 0x80",
          hook+"\n#define PLAYER_LINK_STATE_IDLE 0x80",
          "source-level native overworld hook")
        if r19_connected:
            s=r16.one(s,
              "        ResetMirageTowerAndSaveBlockPtrs();\n"
              "        ResetScreenForMapLoad();\n"
              "        ResumeMap(FALSE);",
              "        ResetMirageTowerAndSaveBlockPtrs();\n"
              "        /* R20: stale external map sources must be restored before\n"
              "         * the original game's field graphics use their pointers. */\n"
              "        XgbaR20PrepareReturnToField();\n"
              "        ResetScreenForMapLoad();\n"
              "        ResumeMap(FALSE);",
              "original Emerald battle-to-field early external map recovery")
            s=r16.one(s,
              "        return gMapLayouts[mapLayoutId - 1];",
              "        return XgbaR19CurrentLayout(gMapLayouts[mapLayoutId - 1]);",
              "native Emerald dual-map layout resolver")
            s=r16.one(s,
              "    return gMapGroups[mapGroup][mapNum];",
              "    return XgbaR19HeaderFor(mapGroup,mapNum);",
              "connected-map header lookup used by original field camera")
        else:
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
        if "#define XGBA_R48_ORIGINAL_NPC_BRIDGE" in Path(config).read_text():
            # Hook the ACTUAL Emerald A-button object-event/script resolver.
            # No virtual NPC interaction is counted if the player's current
            # foreign-source map/NPC was never instantiated by the map loader.
            interaction=e/"src/field_control_avatar.c"
            original_interaction=interaction.read_text()
            originals[interaction]=original_interaction
            source=original_interaction
            source=r16.one(source,
                "static const u8 *GetInteractedObjectEventScript(struct MapPosition *position, u8 metatileBehavior, u8 direction)\n{",
                "extern const u8 *XgbaR48ResolveActualOriginalNpcScript(u8 group,u8 map,u8 npc,const u8 *ordinary);\n"
                "static const u8 *GetInteractedObjectEventScript(struct MapPosition *position, u8 metatileBehavior, u8 direction)\n{",
                "R48 real original Emerald physical A-button NPC interaction resolver declaration")
            source=r16.one(source,
                "    script = GetRamScript(gSpecialVar_LastTalked, script);\n    return script;\n}",
                "    script = GetRamScript(gSpecialVar_LastTalked, script);\n"
                "    script = XgbaR48ResolveActualOriginalNpcScript(\n"
                "        gObjectEvents[objectEventId].mapGroup,\n"
                "        gObjectEvents[objectEventId].mapNum,\n"
                "        gObjectEvents[objectEventId].localId,script);\n"
                "    return script;\n}",
                "R48 original Pokémon object event A-button scripting")
            interaction.write_text(source)
        world.write_text(s)
        if r19_battle:
            # Instrument original Emerald battle sprite decompression, NOT a
            # hand-drawn host sprite or ad-hoc memcpy into emulator VRAM.
            battle=e/"src/battle_gfx_sfx_util.c"
            original_battle=battle.read_text()
            originals[battle]=original_battle
            b=r16.one(original_battle,
                '#include "constants/battle_palace.h"',
                '#include "constants/battle_palace.h"\n'
                'extern const struct CompressedSpriteSheet *XgbaR19BattleFrontSheet('
                'u16 species,const struct CompressedSpriteSheet *original);\n'
                'extern void XgbaR19BattleOpponentRendered(u16 species,const void *destination);\n'
                'extern void XgbaR19BattleLocalRendered(u16 species,const void *destination);',
                "R19 original Emerald battle source insertion")
            b=r16.one(b,
                'HandleLoadSpecialPokePic_DontHandleDeoxys(&gMonFrontPicTable[species],',
                'HandleLoadSpecialPokePic_DontHandleDeoxys('
                'XgbaR19BattleFrontSheet(species,&gMonFrontPicTable[species]),',
                "R19 original opponent battle sprite source selection")
            b=r16.one(b,
                "                                              species, currentPersonality);\n\n"
                "    paletteOffset = OBJ_PLTT_ID(battler);",
                "                                              species, currentPersonality);\n"
                "    XgbaR19BattleOpponentRendered(species,"
                " gMonSpritesGfxPtr->sprites.ptr[position]);\n\n"
                "    paletteOffset = OBJ_PLTT_ID(battler);",
                "R19 actual opponent sprite decompressed by Emerald game")
            mark="void BattleLoadPlayerMonSpriteGfx(struct Pokemon *mon, u8 battler)\n{"
            if b.count(mark)!=1:raise r16.AdapterDrift("Original player battle graphic loader drift")
            before,after=b.split(mark,1)
            after=r16.one(after,
                "    }\n\n    paletteOffset = OBJ_PLTT_ID(battler);",
                "    }\n"
                "    XgbaR19BattleLocalRendered(species,"
                " gMonSpritesGfxPtr->sprites.ptr[position]);\n\n"
                "    paletteOffset = OBJ_PLTT_ID(battler);",
                "R19 original-ROM player sprite decompression")
            battle.write_text(before+mark+after)
        return originals
    except:
        r16.restore_sources(originals)
        raise
