#!/usr/bin/env python3
"""Source-instrument pinned FireRed's REAL Pallet Town map engine for R10.

Unlike R8/R9's standalone tilemap loop, this injection boots FireRed via
CB2_NewGame, loads original MAP_PALLET_TOWN via normal WarpIntoMap, and lets
FireRed own field callbacks, tilemaps, player, object events and sprite/OAM
updates. A custom 64x64 OBJ sprite is managed via actual SpriteTemplate,
CreateSprite, LoadSpritePalette and original LoadSpriteSheet callsites.
SELECT triggers a *second* MMIO resource request without restarting mGBA.

No modified copyrighted ROM is retained after testing or committed here.
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

INJECT = r"""
/* XGBA R10: Native FireRed overworld overlay and runtime resource switch. */
#include "sprite.h"
#include "__XGBA_R4__"
#include "__XGBA_GUEST__"

#define XGBA_R10_TAG_TILE 0xA121u
#define XGBA_R10_TAG_PAL  0xA122u
#define XGBA_R10_BYTES    2048u
#define XGBA_R10_MAGIC    0x58474241u

/* EWRAM data in pret/pokefirered is not automatically ROM-initialised. */
EWRAM_DATA ALIGNED(4) u8 gXgbaR10Tiles[XGBA_R10_BYTES] = {0};
EWRAM_DATA char gXgbaR10CrystalId[24] = {0};
EWRAM_DATA char gXgbaR10MagmaId[24] = {0};
struct XgbaR10Proof {
    volatile u32 magic;
    volatile u32 state;            /* 3 = real FireRed overworld ready */
    volatile u32 verified;
    volatile u32 used;
    volatile u32 tile;
    volatile u32 request_count;    /* total game-issued sidecar loads */
    volatile u32 switch_count;     /* accepted SELECT swaps */
    volatile u32 selected_pack;    /* 0 crystal or disabled, 1 magma */
    volatile u32 frame_count;      /* game engine callback ticks */
    volatile u32 current_group;    /* real gSaveBlock1 map location */
    volatile u32 current_num;
    volatile u32 object_id;        /* sprite engine CreateSprite result */
};
EWRAM_DATA volatile struct XgbaR10Proof gXgbaR10Proof = {0};
void XgbaR10MarkBoot(u32 stage)
{
    gXgbaR10Proof.magic = XGBA_R10_MAGIC;
    gXgbaR10Proof.state = stage;
}
static EWRAM_DATA bool8 sXgbaR10Ready = FALSE;
static EWRAM_DATA u8 sXgbaR10SpriteId = MAX_SPRITES;
static EWRAM_DATA u16 sXgbaR10SpriteTiles = 0xFFFF;

/* This fallback is deliberately blank; external art is never in the ROM. */
static const u8 sXgbaR10OriginalBlank[XGBA_R10_BYTES] = {0};
static const char sXgbaR10CrystalName[] = "graphic.crystal";
static const char sXgbaR10MagmaName[] = "graphic.magma";
static const u16 sXgbaR10Palette[16] = {
    0, 0x3083, 0x6396, 0x7FBA, 0x7FFF, 0x58FD, 0x17BF, 0x13DF,
    0x51C4, 0x7294, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000
};
static const struct OamData sXgbaR10Oam = {
    .shape = SPRITE_SHAPE(64x64),
    .size = SPRITE_SIZE(64x64),
    .priority = 0,
    .paletteNum = 0
};
static const struct SpriteTemplate sXgbaR10Template = {
    .tileTag = XGBA_R10_TAG_TILE,
    .paletteTag = XGBA_R10_TAG_PAL,
    .oam = &sXgbaR10Oam,
    .anims = gDummySpriteAnimTable,
    .images = NULL,
    .affineAnims = gDummySpriteAffineAnimTable,
    .callback = SpriteCallbackDummy
};
static void XgbaR10CopyGuestId(char *dst, const char *src, u32 cap)
{
    u32 i;
    for (i = 0; i+1 < cap && src[i]; ++i)
        dst[i] = src[i];
    dst[i] = 0;
}
static void XgbaR10InstallOnRealField(void)
{
    struct SpriteSheet original = {sXgbaR10OriginalBlank,
                                   XGBA_R10_BYTES, XGBA_R10_TAG_TILE};
    struct SpritePalette pal = {sXgbaR10Palette, XGBA_R10_TAG_PAL};
    struct XgbaStagedSprite stage;
    bool8 used = FALSE;
    u32 received;
    gXgbaR10Proof.magic = XGBA_R10_MAGIC;
    gXgbaR10Proof.state = 0x21;

    XgbaR10CopyGuestId(gXgbaR10CrystalId, sXgbaR10CrystalName,
                       sizeof(gXgbaR10CrystalId));
    XgbaR10CopyGuestId(gXgbaR10MagmaId, sXgbaR10MagmaName,
                       sizeof(gXgbaR10MagmaId));
    received = XgbaGuestFetch(gXgbaR10CrystalId, gXgbaR10Tiles,
                              XGBA_R10_BYTES);
    stage.abiVersion = 1;
    stage.resourceId = XGBA_R10_TAG_TILE;
    stage.ewramData = gXgbaR10Tiles;
    stage.byteLength = XGBA_R10_BYTES;
    stage.validatedByProvider = received == XGBA_R10_BYTES;
    sXgbaR10SpriteTiles = XgbaLoadStagedSpriteSheet(
        &original, XGBA_R10_TAG_TILE, &stage, &used);
    gXgbaR10Proof.tile = sXgbaR10SpriteTiles;
    gXgbaR10Proof.state = 0x22;
    LoadSpritePalette(&pal);
    if (sXgbaR10SpriteTiles == 0xFFFF) {
        gXgbaR10Proof.state = 0xE1;
        return;
    }
    sXgbaR10SpriteId = CreateSprite(&sXgbaR10Template, 120, 78, 0);
    if (sXgbaR10SpriteId == MAX_SPRITES) {
        gXgbaR10Proof.state = 0xE2;
        return;
    }
    gSprites[sXgbaR10SpriteId].oam.priority = 0;
    gXgbaR10Proof.magic = XGBA_R10_MAGIC;
    gXgbaR10Proof.verified = received == XGBA_R10_BYTES;
    gXgbaR10Proof.used = used;
    gXgbaR10Proof.tile = sXgbaR10SpriteTiles;
    gXgbaR10Proof.request_count = used ? 1 : 0;
    gXgbaR10Proof.switch_count = 0;
    gXgbaR10Proof.selected_pack = 0;
    gXgbaR10Proof.frame_count = 0;
    gXgbaR10Proof.object_id = sXgbaR10SpriteId;
    gXgbaR10Proof.current_group = gSaveBlock1Ptr->location.mapGroup;
    gXgbaR10Proof.current_num = gSaveBlock1Ptr->location.mapNum;
    gXgbaR10Proof.state = 3;
    sXgbaR10Ready = TRUE;
}

static void XgbaR10TickRealOverworld(void)
{
    if (!sXgbaR10Ready) {
        gXgbaR10Proof.magic = XGBA_R10_MAGIC;
        gXgbaR10Proof.state = 0x20;
        XgbaR10InstallOnRealField();
        return;
    }
    /* The genuine CB1_Overworld, CB2_Overworld, map scripts, player object
     * events and tile renderer still run; no replacement LCD scene. */
    ++gXgbaR10Proof.frame_count;
    gXgbaR10Proof.current_group = gSaveBlock1Ptr->location.mapGroup;
    gXgbaR10Proof.current_num = gSaveBlock1Ptr->location.mapNum;
    if (gMain.newKeys & SELECT_BUTTON) {
        const char *id = gXgbaR10Proof.selected_pack
                       ? gXgbaR10CrystalId : gXgbaR10MagmaId;
        u32 amount = XgbaGuestFetch(id, gXgbaR10Tiles,
                                    XGBA_R10_BYTES);
        if (amount == XGBA_R10_BYTES) {
            /* Keep the existing FireRed sprite alive and replace its 64x64
             * tiles at the same native allocated OBJ VRAM address. */
            RequestSpriteCopy(gXgbaR10Tiles,
                              (u8 *)(0x06010000u
                                  + sXgbaR10SpriteTiles * 32u),
                              XGBA_R10_BYTES);
            ++gXgbaR10Proof.request_count;
            ++gXgbaR10Proof.switch_count;
            gXgbaR10Proof.selected_pack ^= 1u;
        }
    }
}
"""


def replace_once(source: str, before: str, after: str, name: str) -> str:
    count=source.count(before)
    if count != 1:
        raise RuntimeError(f"BLOCKED: pinned FireRed {name} drift: expected 1 anchor, saw {count}")
    return source.replace(before, after, 1)


def make_firered_real_overworld_sources(firered:Path):
    main=firered/"src/main.c"
    overworld=firered/"src/overworld.c"
    original_main=main.read_text(encoding="utf-8")
    original_world=overworld.read_text(encoding="utf-8")
    if "gXgbaR10Proof" in original_world or "XgbaR10" in original_main:
        raise RuntimeError("Refusing already-instrumented source")
    main_new=replace_once(
        original_main,
        "    gLinkTransferringData = FALSE;\n\n    for (;;)",
        "    gLinkTransferringData = FALSE;\n"
        "    /* R10: boot straight into FireRed's OWN map engine. */\n"
        "    SetMainCallback2(CB2_NewGame);\n"
        "    XgbaR10MarkBoot(0x01);\n\n    for (;;)",
        "AgbMain startup",
    )
    main_new=replace_once(
        main_new, "void AgbMain()\n{",
        "extern void XgbaR10MarkBoot(u32 stage);\n\nvoid AgbMain()\n{",
        "AgbMain declaration",
    )
    marker='#define PLAYER_LINK_STATE_IDLE 0x80'
    world_new=replace_once(
        original_world, marker,
        INJECT.replace("__XGBA_R4__",
            (ROOT/"tools/xgba_resource_firered_adapter.c").as_posix())
              .replace("__XGBA_GUEST__",
            (ROOT/"integration/fire_red/xgba_guest.h").as_posix())
        + "\n" + marker,
        "overworld injection",
    )
    world_new=replace_once(
        world_new,
        "void CB2_NewGame(void)\n{\n    FieldClearVBlankHBlankCallbacks();",
        "void CB2_NewGame(void)\n{\n"
        "    XgbaR10MarkBoot(0x11);\n"
        "    FieldClearVBlankHBlankCallbacks();",
        "CB2_NewGame entry",
    )
    world_new=replace_once(
        world_new,
        "    NewGameInitData();\n    ResetInitialPlayerAvatarState();",
        "    NewGameInitData();\n"
        "    XgbaR10MarkBoot(0x12);\n"
        "    /* Native real Pallet Town map assets, events and overworld loop. */\n"
        "    SetWarpDestination(MAP_GROUP(MAP_PALLET_TOWN),\n"
        "                       MAP_NUM(MAP_PALLET_TOWN), -1, 10, 13);\n"
        "    WarpIntoMap();\n"
        "    XgbaR10MarkBoot(0x13);\n"
        "    ResetInitialPlayerAvatarState();",
        "CB2_NewGame map warp",
    )
    world_new=replace_once(
        world_new,
        "    DoMapLoadLoop(&gMain.state);\n"
        "    SetFieldVBlankCallback();\n"
        "    SetMainCallback1(CB1_Overworld);\n"
        "    SetMainCallback2(CB2_Overworld);",
        "    DoMapLoadLoop(&gMain.state);\n"
        "    XgbaR10MarkBoot(0x14);\n"
        "    SetFieldVBlankCallback();\n"
        "    SetMainCallback1(CB1_Overworld);\n"
        "    SetMainCallback2(CB2_Overworld);",
        "CB2_NewGame after map load",
    )
    world_new=replace_once(
        world_new,
        "static void CB2_Overworld(void)\n{\n"
        "    bool32 fading = !!gPaletteFade.active;\n"
        "    if (fading)\n        SetVBlankCallback(NULL);\n"
        "    OverworldBasic();\n"
        "    if (fading)\n        SetFieldVBlankCallback();\n}",
        "static void CB2_Overworld(void)\n{\n"
        "    bool32 fading = !!gPaletteFade.active;\n"
        "    if (fading)\n        SetVBlankCallback(NULL);\n"
        "    OverworldBasic();\n"
        "    XgbaR10TickRealOverworld();\n"
        "    if (fading)\n        SetFieldVBlankCallback();\n}",
        "native CB2_Overworld callback",
    )
    main.write_text(main_new,encoding="utf-8")
    overworld.write_text(world_new,encoding="utf-8")
    return {main:original_main,overworld:original_world}


def restore_firered_sources(originals):
    for path,content in originals.items():
        path.write_text(content,encoding="utf-8")
