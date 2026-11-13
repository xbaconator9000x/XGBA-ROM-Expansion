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
    r50_enabled = "#define XGBA_R50_ENGINE_EVENTS" in Path(config).read_text()
    r48_enabled = "#define XGBA_R48_ORIGINAL_NPC_BRIDGE" in Path(config).read_text()
    if r50_enabled and (not r48_enabled or r19_connected):
        raise r16.AdapterDrift("R50 guest event bridge requires R48 and an exclusive owned map arena")
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
    hook=hook.replace("__XGBA_R50_ENGINE_BRIDGE__",
                      (ROOT/"integration/emerald/xgba_r50_original_engine_events.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R51_TERRAIN_BRIDGE__",
                      (ROOT/"integration/emerald/xgba_r51_original_terrain.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R52_LAYOUT_BRIDGE__",
                      (ROOT/"integration/emerald/xgba_r52_native_source_layout.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R53_GRAPHICS_BRIDGE__",
                      (ROOT/"integration/emerald/xgba_r53_original_graphics.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R54_REAL_WARP_BRIDGE__",
                      (ROOT/"integration/emerald/xgba_r54_native_fly_warp_admission.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R57_NATIVE_SPRITE_BRIDGE__",
                      (ROOT/"integration/emerald/xgba_r57_native_source_sprite_installer.inc").resolve().as_posix())
    hook=hook.replace("__XGBA_R58_NATIVE_FLY_BRIDGE__",
                      (ROOT/"integration/emerald/xgba_r58_native_original_fly.inc").resolve().as_posix())
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
        if r50_enabled:
            s=r16.one(s,
              "        return XgbaR17Resolve(gMapLayouts[mapLayoutId - 1]);",
              "        return XgbaR50LayoutFor(gMapLayouts[mapLayoutId - 1]);",
              "R50 real Emerald map-layout resolver with source-owned graphics gate")
            s=r16.one(s,
              "    return gMapGroups[mapGroup][mapNum];",
              "    return XgbaR50HeaderFor(mapGroup,mapNum,gMapGroups[mapGroup][mapNum]);",
              "R50 real Emerald MapHeader events resolver")
        if "#define XGBA_R54_REAL_WARP_ADMISSION" in Path(config).read_text():
            if "#define XGBA_R53_ORIGINAL_GRAPHICS" not in Path(config).read_text():
                raise r16.AdapterDrift("R54 original warp admission needs R53 original graphics")
            # This is the ACTUAL original Emerald local map-load state machine,
            # not a made-up Fly debug action or frame callback. Source memory
            # must be staged before LoadMapFromWarp reads MapHeader and
            # before InitObjectEventsLocal/fieldmap BG DMA/camera.
            # Original MoveSaveBlocks_ResetHeap from case 1 must not erase
            # R53's map-owned verified graphics allocated in case 0.
            s=r16.one(s,
              "    case 0:\n        FieldClearVBlankHBlankCallbacks();\n"
              "        LoadMapFromWarp(a2);\n        (*state)++;\n        break;",
              "    case 0:\n        FieldClearVBlankHBlankCallbacks();\n"
              "        {\n"
              "            u8 originalSourceWarp = XgbaR54InspectFadedOriginalMapLoad();\n"
              "            if (originalSourceWarp >= 2u)\n"
              "                XgbaR54FailClosedBeforeForeignHeader();\n"
              "            /* Retire old source while its original heap is intact. */\n"
              "            if (!XgbaR54ReleaseOldSourceBeforeNativeHeapReset())\n"
              "                XgbaR54FailClosedBeforeForeignHeader();\n"
              "            if (originalSourceWarp == 1u) {\n"
              "                ResetMirageTowerAndSaveBlockPtrs();\n"
              "                XgbaR54MarkNativePreloadHeapReset();\n"
              "                if (!XgbaR54InstallPendingOriginalSourceAtNativeWarp())\n"
              "                    XgbaR54FailClosedBeforeForeignHeader();\n"
              "            }\n"
              "        }\n"
              "        LoadMapFromWarp(a2);\n        (*state)++;\n        break;",
              "R54 original field fade/source map admission before actual MapHeader/objects")
            s=r16.one(s,
              "    case 1:\n        ResetMirageTowerAndSaveBlockPtrs();\n"
              "        ResetScreenForMapLoad();",
              "    case 1:\n"
              "        if (!XgbaR54ShouldSkipOriginalCaseOneHeapReset())\n"
              "            ResetMirageTowerAndSaveBlockPtrs();\n"
              "        ResetScreenForMapLoad();",
              "R54 single original heap reset preserves queued source BG DMA")
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
            # Link the ACTUAL Fly field-effect arrival callback, not a
            # surrogate keypress or map-viewer source switch. This only
            # increments proof when the genuine foreign map/object is active.
            flying=e/"src/field_effect.c"
            original_flying=flying.read_text()
            originals[flying]=original_flying
            fly_source=r16.one(original_flying,
                "static void FieldCallback_FlyIntoMap(void)\n{\n    Overworld_PlaySpecialMapMusic();",
                "extern void XgbaR48ConfirmActualFlyArrival(void);\n"
                "static void FieldCallback_FlyIntoMap(void)\n{\n"
                "    XgbaR48ConfirmActualFlyArrival();\n"
                "    Overworld_PlaySpecialMapMusic();",
                "R48 genuine original FldEff_FlyIn callback and loaded-map acceptance")
            if r50_enabled:
                # The original FieldCallback_FlyIntoMap is the real arrival.
                # Verify the loaded source map and original object BEFORE
                # the R48 Fly acceptance counter evaluates the arrival.
                fly_source=r16.one(fly_source,
                    "extern void XgbaR48ConfirmActualFlyArrival(void);\n",
                    "extern void XgbaR50VerifyLoadedEngineMap(void);\n"
                    "extern void XgbaR48ConfirmActualFlyArrival(void);\n",
                    "R50 native verified original map attestation declaration")
                fly_source=r16.one(fly_source,
                    "    XgbaR48ConfirmActualFlyArrival();\n"
                    "    Overworld_PlaySpecialMapMusic();",
                    "    XgbaR50VerifyLoadedEngineMap();\n"
                    "    XgbaR48ConfirmActualFlyArrival();\n"
                    "    Overworld_PlaySpecialMapMusic();",
                    "R50 confirm actual Fly only after real loaded original source map")
            flying.write_text(fly_source)
        if "#define XGBA_R52_SOURCE_LAYOUT" in Path(config).read_text():
            # Original Emerald hardcodes 512 primary metatiles everywhere.
            # Rocket/HnS versioned layouts use 640. Patch the real original
            # field camera AND collision/behavior lookup, not an image viewer.
            camera=e/"src/field_camera.c"
            original_camera=camera.read_text()
            originals[camera]=original_camera
            cc=r16.one(original_camera,
                "static void DrawMetatileAt(const struct MapLayout *mapLayout, u16 offset, int x, int y)",
                "extern u16 XgbaR52PrimaryMetatileCount(void);\n"
                "static void DrawMetatileAt(const struct MapLayout *mapLayout, u16 offset, int x, int y)",
                "R52 dynamic original Emerald field camera declaration")
            cc=r16.one(cc,
                "if (metatileId < NUM_METATILES_IN_PRIMARY)",
                "if (metatileId < XgbaR52PrimaryMetatileCount())",
                "R52 original Emerald primary metatile camera routing")
            cc=r16.one(cc,
                "metatileId -= NUM_METATILES_IN_PRIMARY;",
                "metatileId -= XgbaR52PrimaryMetatileCount();",
                "R52 original Emerald secondary metatile camera offset")
            camera.write_text(cc)
            fm=e/"src/fieldmap.c"
            original_fm=fm.read_text()
            originals[fm]=original_fm
            fs=r16.one(original_fm,
                "u16 GetMetatileAttributesById(u16 metatile)\n{",
                "extern u16 XgbaR52PrimaryMetatileCount(void);\n"
                "u16 GetMetatileAttributesById(u16 metatile)\n{",
                "R52 native original Emerald collision behavior resolver")
            fs=r16.one(fs,
                "if (metatile < NUM_METATILES_IN_PRIMARY)",
                "if (metatile < XgbaR52PrimaryMetatileCount())",
                "R52 source-qualified map collision primary split")
            fs=r16.one(fs,
                "metatile - NUM_METATILES_IN_PRIMARY];",
                "metatile - XgbaR52PrimaryMetatileCount()];",
                "R52 source-qualified map collision secondary offset")
            # A genuine version-2 foreign map needs the *same* 640/384
            # tile split (and 7/6 palette split) in the actual original
            # Emerald BG DMA and palette-copy paths, not just field camera.
            # Scope these source-wide replacements to audited exact counts.
            if fs.count("NUM_TILES_IN_PRIMARY")!=8 or fs.count("NUM_PALS_IN_PRIMARY")!=4:
                raise r16.AdapterDrift("Pinned Emerald BG tile/palette split callsite drift")
            fs=fs.replace("NUM_TILES_IN_PRIMARY","XgbaR52PrimaryTilesCount()")
            fs=fs.replace("NUM_PALS_IN_PRIMARY","XgbaR52PrimaryPaletteCount()")
            fs=r16.one(fs,
                "extern u16 XgbaR52PrimaryMetatileCount(void);\n",
                "extern u16 XgbaR52PrimaryMetatileCount(void);\n"
                "extern u16 XgbaR52PrimaryTilesCount(void);\n"
                "extern u16 XgbaR52PrimaryPaletteCount(void);\n",
                "R52 original Emerald BG graphics and palette split declarations")
            fm.write_text(fs)
        if "#define XGBA_R53_ORIGINAL_GRAPHICS" in Path(config).read_text():
            if "#define XGBA_R52_SOURCE_LAYOUT" not in Path(config).read_text():
                raise r16.AdapterDrift("R53 native tileset requires exact R52 source profile")
            # Unlike a demonstration map viewer, this rewires the genuine
            # Emerald BG tile-copy functions, including the heap variant.
            # The source installer returns 0 for vanilla, +1 on verified
            # original source VRAM DMA, and -1 on corruption/stale pointers.
            fm=e/"src/fieldmap.c"
            code=fm.read_text()
            code=r16.one(code,
                "static void CopyTilesetToVram(struct Tileset const *tileset, u16 numTiles, u16 offset)\n{\n    if (tileset)",
                "extern s16 XgbaR53TryLoadOriginalTileset(const struct Tileset *tileset);\n"
                "extern void XgbaR53RefuseCorruptedSourceGraphics(void);\n"
                "static void CopyTilesetToVram(struct Tileset const *tileset, u16 numTiles, u16 offset)\n"
                "{\n"
                "    s16 xgbaResult=XgbaR53TryLoadOriginalTileset(tileset);\n"
                "    if(xgbaResult){if(xgbaResult<0) XgbaR53RefuseCorruptedSourceGraphics();return;}\n"
                "    if (tileset)",
                "R53 real native Emerald background source tile copy")
            code=r16.one(code,
                "static void CopyTilesetToVramUsingHeap(struct Tileset const *tileset, u16 numTiles, u16 offset)\n{\n    if (tileset)",
                "static void CopyTilesetToVramUsingHeap(struct Tileset const *tileset, u16 numTiles, u16 offset)\n"
                "{\n"
                "    s16 xgbaResult=XgbaR53TryLoadOriginalTileset(tileset);\n"
                "    if(xgbaResult){if(xgbaResult<0) XgbaR53RefuseCorruptedSourceGraphics();return;}\n"
                "    if (tileset)",
                "R53 real original Emerald BG decompress-heap source tile copy")
            fm.write_text(code)
        if "#define XGBA_R54_REAL_WARP_ADMISSION" in Path(config).read_text():
            # Original Emerald's GetObjectEventGraphicsInfo is the ACTUAL
            # object/NPC sprite frame/OAM/animation/palette dispatch used
            # during InitObjectEventsLocal. Only override source-qualified
            # per-map private graphics registered and verified by R55.
            objects=e/"src/event_object_movement.c"
            original_objects=objects.read_text()
            originals[objects]=original_objects
            sprite_src=r16.one(original_objects,
                "const struct ObjectEventGraphicsInfo *GetObjectEventGraphicsInfo(u8 graphicsId)\n{",
                "extern const struct ObjectEventGraphicsInfo *"
                "XgbaR55GetVerifiedNativeOriginalObjectGraphics(u8 installed_slot);\n"
                "const struct ObjectEventGraphicsInfo *GetObjectEventGraphicsInfo(u8 graphicsId)\n{",
                "R55 real original Emerald OBJ graphics info resolver declaration")
            sprite_src=r16.one(sprite_src,
                "    if (graphicsId == OBJ_EVENT_GFX_BARD)\n    {",
                "    {\n"
                "        const struct ObjectEventGraphicsInfo *verifiedOriginal =\n"
                "            XgbaR55GetVerifiedNativeOriginalObjectGraphics(graphicsId);\n"
                "        if (verifiedOriginal != NULL)\n"
                "            return verifiedOriginal;\n"
                "    }\n"
                "    if (graphicsId == OBJ_EVENT_GFX_BARD)\n    {",
                "R55 native source-authenticated original NPC sprite image/palette dispatch")
            sprite_src=r16.one(sprite_src,
                "static void LoadObjectEventPalette(u16);",
                "extern bool8 XgbaR57ApplyOriginalObjectPalette(u8 graphics_id,u8 palette_slot);\n"
                "static void LoadObjectEventPalette(u16);",
                "R57 actual source palette installer prototype")
            sprite_src=r16.one(sprite_src,
                "    sprite->oam.paletteNum = paletteSlot;\n"
                "    sprite->coordOffsetEnabled = TRUE;\n"
                "    sprite->sObjEventId = objectEventId;",
                "    sprite->oam.paletteNum = paletteSlot;\n"
                "    if (!XgbaR57ApplyOriginalObjectPalette(objectEvent->graphicsId, paletteSlot)) {\n"
                "        objectEvent->active = FALSE;\n"
                "        DestroySprite(sprite);\n"
                "        return OBJECT_EVENTS_COUNT;\n"
                "    }\n"
                "    sprite->coordOffsetEnabled = TRUE;\n"
                "    sprite->sObjEventId = objectEventId;",
                "R57 copy actual original source palette at real NPC spawn")
            objects.write_text(sprite_src)
        if "#define XGBA_R54_REAL_WARP_ADMISSION" in Path(config).read_text():
            from xgba_r58_fly_menu_patch import patch_native_original_fly_region_map
            originals.update(patch_native_original_fly_region_map(e))
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
