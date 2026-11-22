#!/usr/bin/env python3
"""Fail-closed, reversible source adapter for RHH pokeemerald-expansion.

A single upstream repository builds Emerald AND FireRed/LeafGreen as separate
targets. This adapter reuses XGBA's existing guest MMIO ABI instead of
pretending a vanilla Emerald binary patch is compatible with an expansion.

Initial gate: source boot bridge, not full external maps/graphics/gameplay.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("emerald", "firered", "leafgreen")
UPSTREAM = "https://github.com/rh-hideout/pokeemerald-expansion"
VALIDATED_RELEASE = "expansion/1.17.2"
VALIDATED_RELEASE_SHA = "79dd436920845ebc145577649de624f65298c209"
MGBA_PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"

class ExpansionDrift(RuntimeError):
    """Refuse unsupported or already-patched source instead of guessing."""


def _one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ExpansionDrift(f"{label}: expected 1 source anchor, found {count}")
    return text.replace(old, new, 1)


def validate_source(source: Path, target: str) -> dict:
    if target not in TARGETS:
        raise ExpansionDrift(f"unsupported game target: {target!r}")
    makefile_path = source / "Makefile"
    main_path = source / "src/main.c"
    global_path = source / "include/global.h"
    if not all(p.is_file() for p in (makefile_path, main_path, global_path)):
        raise ExpansionDrift("not an intact pokeemerald-expansion source checkout")
    makefile = makefile_path.read_text(encoding="utf-8")
    normalized_makefile = " ".join(makefile.split())
    main = main_path.read_text(encoding="utf-8")
    required_make = (
        "GAME_VERSION ?= EMERALD",
        "GAME_VERSION := FIRERED",
        "GAME_VERSION := LEAFGREEN",
        "emerald: all",
        "firered: all",
        "leafgreen: all",
    )
    missing = [s for s in required_make if s not in normalized_makefile]
    if missing:
        raise ExpansionDrift(f"unsupported expansion build matrix: {missing}")
    if "XgbaExpansionProbeBoot" in main or "gXgbaExpansionProof" in main:
        raise ExpansionDrift("upstream main.c is already patched")
    for anchor in ("void AgbMain(void)\n{",
                   "    InitHeap(gHeap, HEAP_SIZE);",
                   "    ReadKeys();"):
        if main.count(anchor) != 1:
            raise ExpansionDrift(f"expansion main ABI drift at {anchor!r}")
    fieldmap_path = source / "src/fieldmap.c"
    battle_path = source / "src/battle_gfx_sfx_util.c"
    if not battle_path.is_file():
        raise ExpansionDrift("missing original battle graphics loader")
    battle = battle_path.read_text(encoding="utf-8")
    if battle.count("void DecompressTrainerFrontPic(enum TrainerPicID trainerPicId, enum BattlerId battler)") != 1 or battle.count("    DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId), gMonSpritesGfxPtr->spritesGfx[position]);") != 1:
        raise ExpansionDrift("original trainer graphics loader ABI drift")
    if "XgbaExpansionTryTrainerPic" in battle:
        raise ExpansionDrift("upstream battle graphics loader already patched")
    if not (source / "src/load_save.c").is_file():
        raise ExpansionDrift("missing original save-block heap lifecycle")
    if not fieldmap_path.is_file():
        raise ExpansionDrift("missing original fieldmap.c")
    fieldmap = fieldmap_path.read_text(encoding="utf-8")
    for anchor in (
        "static inline u16 GetBorderBlockAt(int x, int y)",
        "    InitBackupMapLayoutData(mapLayout->map, mapLayout->width, mapLayout->height);",
        "static void CopyTilesetToVram(struct Tileset const *tileset, u16 numTiles, u16 offset)",
        "static void CopyTilesetToVramUsingHeap(struct Tileset const *tileset, u16 numTiles, u16 offset)",
    ):
        if fieldmap.count(anchor) != 1:
            raise ExpansionDrift(f"expansion fieldmap ABI drift at {anchor!r}")
    if "XgbaExpansionTryMapCopy" in fieldmap:
        raise ExpansionDrift("upstream fieldmap.c already patched")
    if "EWRAM_DATA" not in main:
        raise ExpansionDrift("missing expected expansion EWRAM declaration usage")
    return {
        "framework": "rh-hideout/pokeemerald-expansion",
        "target": target,
        "source_main_sha256": hashlib.sha256(main.encode()).hexdigest(),
        "guest_mmio_abi": 1,
        "source_anchors": 3,
        "runtime_gameplay_verified": False,
    }


def patched_fieldmap(original: str) -> str:
    """Integrate original RHH fieldmap and both tileset load entrypoints."""
    bridge_path = ROOT / "integration/expansion/xgba_expansion_fieldmap.inc"
    page_api = ROOT / "integration/expansion/xgba_expansion_page.h"
    bridge = bridge_path.read_text(encoding="utf-8").replace(
        "XGBA_EXPANSION_MAP_API_PLACEHOLDER", page_api.resolve().as_posix())
    # The reusable graphics lease owns buffers across the upstream BG DMA.
    # Include its allocator declarations explicitly, not transitively.
    bridge = '#include "malloc.h"\n' + bridge
    text = _one(original,
                "static inline u16 GetBorderBlockAt(int x, int y)",
                bridge + "\nstatic inline u16 GetBorderBlockAt(int x, int y)",
                "fieldmap declaration ABI")
    text = _one(text,
                "    InitBackupMapLayoutData(mapLayout->map, mapLayout->width, mapLayout->height);",
                "    XgbaExpansionBindOriginalMap(mapHeader);\n"
                "    InitBackupMapLayoutData(mapLayout->map, mapLayout->width, mapLayout->height);\n"
                "    XgbaExpansionTryMapCopy(mapLayout);",
                "original map layout copy")
    for signature in (
        "static void CopyTilesetToVram(struct Tileset const *tileset, u16 numTiles, u16 offset)",
        "static void CopyTilesetToVramUsingHeap(struct Tileset const *tileset, u16 numTiles, u16 offset)",
    ):
        text = _one(text, signature + "\n{\n    if (tileset)",
                    signature + "\n{\n    if (XgbaExpansionTryTilesetCopy(tileset, numTiles, offset))\n"
                    "        return;\n    if (tileset)",
                    signature)
    return text


def patched_battle_graphics(original: str) -> str:
    """Load raw trainer tiles into the existing battler-owned WRAM buffer."""
    page_api = ROOT / "integration/expansion/xgba_expansion_page.h"
    bridge = r'''
#include "XGBA_BATTLE_PAGE_API"
extern void XgbaExpansionTrainerTransfer(u32 id, const void *dest, u32 bytes);
static bool8 XgbaExpansionTryTrainerPic(u32 id, const u32 *original, void *dest)
{
    static const char hex[] = "0123456789abcdef";
    char resource[] = "rhh.trainer.0000";
    u32 bytes;
    const u8 *page;
    /* Only admit the source-verified 64x64 4bpp trainer resources.
     * Other IDs must retain the original decompressor until their
     * graphics bindings and dimensions have been independently verified. */
    if (!original || !dest || (id != TRAINER_PIC_HIKER && id != TRAINER_PIC_HIKER_FRLG))
        return FALSE;
    /* The page lease is invalidated immediately after the synchronous copy.
     * Refuse any destination overlapping the leased tail of gHeap, even if
     * the caller changes sprite-buffer ownership in a future RHH release. */
    bytes = GetDecompressedDataSize(original);
    /* Trainer tiles must land entirely in engine-owned EWRAM, never VRAM,
     * ROM, I/O or a transient page. Check the end without addition overflow. */
    if (bytes != 64u * 64u / 2u || bytes > MON_PIC_SIZE
        || bytes > XGBA_EXPANSION_PAGE_CAPACITY || ((u32)dest & 3u)
        || (u32)dest < 0x02000000u
        || (u32)dest > 0x02040000u - bytes)
        return FALSE;
    for (u32 i = 0; i < 4; ++i)
        resource[sizeof(resource) - 2u - i] = hex[(id >> (4 * i)) & 15u];
    if (XgbaExpansionPageAcquire(resource, bytes) != bytes)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    page = XgbaExpansionPageData();
    /* CpuCopy32 requires a word-aligned resident source. Refuse malformed
     * provider addresses rather than copying through an unaligned pointer. */
    if (!page || ((u32)page & 3u)
        || (u32)page < 0x02000000u
        || (u32)page > 0x02040000u - bytes
        || XgbaExpansionPageResidentBytes() != bytes)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    /* The leased page is available only after Acquire. Compare address
     * intervals using subtraction to avoid wraparound in dest + bytes. */
    if ((u32)dest >= (u32)page
        ? (u32)dest - (u32)page < XGBA_EXPANSION_PAGE_CAPACITY
        : (u32)page - (u32)dest < bytes)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    /* Do not report external success until the engine-owned destination
     * contains the entire original-source page.  A failed verification
     * releases the lease and lets the original decompressor restore tiles. */
    /* A nested provider request must not replace this lease while the
     * destination is being populated. Reject a changed generation and let
     * the original compressed graphics path recover. */
    u32 generation = XgbaExpansionPageGeneration();
    u32 sourceHash = 2166136261u;
    u32 destinationHash = 2166136261u;
    /* Hash the leased source BEFORE the transfer. Comparing only against
     * the page after copying can silently accept a provider that rewrites
     * the page in place without incrementing its generation. */
    for (u32 i = 0; i < bytes; ++i)
        sourceHash = (sourceHash ^ page[i]) * 16777619u;
    if (XgbaExpansionPageGeneration() != generation
        || XgbaExpansionPageData() != page
        || XgbaExpansionPageResidentBytes() != bytes)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    {
        CpuCopy32(page, dest, bytes);
        if (XgbaExpansionPageGeneration() != generation
            || XgbaExpansionPageData() != page
            || XgbaExpansionPageResidentBytes() != bytes)
        {
            XgbaExpansionPageRelease();
            return FALSE;
        }
    }
    for (u32 i = 0; i < bytes; ++i)
    {
        destinationHash = (destinationHash ^ ((const u8 *)dest)[i]) * 16777619u;
        if (((const u8 *)dest)[i] != page[i])
        {
            XgbaExpansionPageRelease();
            return FALSE;
        }
    }
    if (destinationHash != sourceHash)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    /* Rehash the provider page after the transfer as well. A host that
     * rewrites the leased bytes in place without advancing its generation
     * must never turn a torn page into a successful battle graphics load. */
    {
        u32 finalSourceHash = 2166136261u;
        for (u32 i = 0; i < bytes; ++i)
            finalSourceHash = (finalSourceHash ^ page[i]) * 16777619u;
        if (finalSourceHash != sourceHash)
        {
            XgbaExpansionPageRelease();
            return FALSE;
        }
    }
    /* A provider callback can invalidate the lease during verification too.
     * Check residency again before reporting a successful transfer. */
    if (XgbaExpansionPageGeneration() != generation
        || XgbaExpansionPageData() != page
        || XgbaExpansionPageResidentBytes() != bytes)
    {
        XgbaExpansionPageRelease();
        return FALSE;
    }
    XgbaExpansionPageRelease();
    XgbaExpansionTrainerTransfer(id, dest, bytes);
    return TRUE;
}
'''.replace("XGBA_BATTLE_PAGE_API", page_api.resolve().as_posix())
    signature = "void DecompressTrainerFrontPic(enum TrainerPicID trainerPicId, enum BattlerId battler)"
    text = _one(original, signature, bridge + "\n" + signature, "trainer loader ABI")
    call = "    DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId), gMonSpritesGfxPtr->spritesGfx[position]);"
    return _one(text, call,
                "    if (!XgbaExpansionTryTrainerPic(trainerPicId, GetTrainerFrontPicData(trainerPicId), gMonSpritesGfxPtr->spritesGfx[position]))\n    " + call,
                "trainer graphics fallback")


def patched_save_heap(original: str) -> str:
    """Keep the external page outside the original save-block heap reset.

    RHH MoveSaveBlocks_ResetHeap restores HEAP_SIZE after save relocation.
    That would re-expose the 16-KiB leased tail to the game's allocator.
    """
    return _one(original,
                "    InitHeap(gHeap, HEAP_SIZE);",
                "    InitHeap(gHeap, HEAP_SIZE - 0x4000u);",
                "save relocation heap lease")


def patched_overworld(original: str) -> str:
    """Test-only direct new-game entry followed by unmodified overworld input."""
    test_start = """    XgbaExpansionLiveStage(2u);
    NewGameInitData();
    XgbaExpansionLiveStage(3u);
    /* RHH XGBA playable test: real new-game state, no intro or scripted truck.
     * Preserve all map events, NPCs, scripts and original map/tileset IDs. */
    if (IS_FRLG)
    {
        /* Test fixture: establish the starter prerequisite through the
         * engine's normal scripted gift API before approaching Oak's exit.
         * Do not disable map scripts or force the Route 1 transition. */
        ScriptGiveMon(SPECIES_BULBASAUR, 5, ITEM_NONE);
        FlagSet(FLAG_SYS_POKEMON_GET);
        /* Pinned PalletTown_Frlg/map.json gates both north exit triggers
         * on Oak scene 0, not FLAG_SYS_POKEMON_GET. Scene 1 is the
         * original post-Oak escort state (PalletTown_Frlg/scripts.inc). */
        VarSet(VAR_MAP_SCENE_PALLET_TOWN_OAK, 1);
        FlagSet(FLAG_HIDE_OAK_IN_PALLET_TOWN);
        VarSet(VAR_MAP_SCENE_PALLET_TOWN_PROFESSOR_OAKS_LAB, 4);
        FlagSet(FLAG_BEAT_RIVAL_IN_OAKS_LAB);
        SetWarpDestination(MAP_GROUP(MAP_PALLET_TOWN),
                           MAP_NUM(MAP_PALLET_TOWN), WARP_ID_NONE, 11, 4);
    }
    else
    {
        VarSet(VAR_LITTLEROOT_TOWN_STATE, 4);
        VarSet(VAR_ROUTE101_STATE, 3);
        SetWarpDestination(MAP_GROUP(MAP_LITTLEROOT_TOWN),
                           MAP_NUM(MAP_LITTLEROOT_TOWN), WARP_ID_NONE, 10, 4);
    }
    WarpIntoMap();
    XgbaExpansionLiveStage(4u);
    ResetInitialPlayerAvatarState();"""
    text = _one(original,
                "    NewGameInitData();\n    ResetInitialPlayerAvatarState();",
                test_start, "authentic new-game-to-overworld transition")
    text = _one(text,
                "    gFieldCallback2 = NULL;\n    DoMapLoadLoop(&gMain.state);",
                "    gFieldCallback = FieldCB_WarpExitFadeFromBlack;\n"
                "    gFieldCallback2 = NULL;\n"
                "    XgbaExpansionLiveStage(5u);\n"
                "    DoMapLoadLoop(&gMain.state);\n"
                "    XgbaExpansionLiveStage(6u);",
                "original field callback")
    text = _one(text,
                "void CB2_Overworld(void)\n{\n    bool32 fading = (gPaletteFade.active != 0);\n",
                "void CB2_Overworld(void)\n{\n    bool32 fading = (gPaletteFade.active != 0);\n",
                "overworld callback entry")
    text = _one(text,
                "    OverworldBasic();\n    if (fading)\n",
                "    OverworldBasic();\n"
                "    XgbaExpansionGraphicsPoll();\n"
                "    XgbaExpansionLiveTick(gMapHeader.mapLayoutId,\n"
                "        gSaveBlock1Ptr->pos.x, gSaveBlock1Ptr->pos.y);\n"
                "    if (fading)\n",
                "actual overworld movement callback")
    text = _one(text,
                "void CB2_NewGame(void)\n{",
                "extern void XgbaExpansionLiveStage(u32 stage);\n"
                "void CB2_NewGame(void)\n{",
                "native source new-game stage declaration")
    return _one(text,
                "void CB2_Overworld(void)\n{",
                "extern void XgbaExpansionGraphicsPoll(void);\n"
                "extern void XgbaExpansionLiveTick(u32 layout, s32 x, s32 y);\n"
                "void CB2_Overworld(void)\n{",
                "external witness declaration")


def patched_main(original: str, header: Path, probe: str, *, map_smoke: bool = False,
                 overworld_play: bool = False) -> str:
    header_name = header.resolve().as_posix()
    if '"' in header_name or "\n" in header_name:
        raise ExpansionDrift("unsafe header path")
    if probe.count("__XGBA_SHARED_GUEST__") != 1 or probe.count("__XGBA_PAGE_API__") != 1:
        raise ExpansionDrift("XGBA source ABI include drift")
    page_api = ROOT / "integration/expansion/xgba_expansion_page.h"
    if not page_api.is_file():
        raise ExpansionDrift("XGBA expansion page ABI header missing")
    page_api_name = page_api.resolve().as_posix()
    if '"' in page_api_name or "\n" in page_api_name:
        raise ExpansionDrift("unsafe page API header path")
    probe = (probe.replace("__XGBA_SHARED_GUEST__", header_name)
                  .replace("__XGBA_PAGE_API__", page_api_name))
    text = _one(original,
                "void AgbMain(void)\n{",
                probe + "\nextern void XgbaExpansionGraphicsPoll(void);\nvoid AgbMain(void)\n{",
                "game boot function")
    boot = ("    InitHeap(gHeap, XGBA_EXPANSION_HEAP_BYTES);\n"
            "    XgbaExpansionProbeBoot();")
    if map_smoke:
        boot += ("\n    XgbaExpansionNativeMapTileSmoke();"
                 " /* explicit native source-loader test only */")
    if overworld_play:
        boot += ("\n    XgbaExpansionLiveStage(1u);"
                 " /* gameplay callback is scheduled after boot initialization */")
    text = _one(text,
                "    InitHeap(gHeap, HEAP_SIZE);",
                boot,
                "post-heap initialization")
    tick = "    XgbaExpansionProbeTick();\n    XgbaExpansionGraphicsPoll();\n    ReadKeys();"
    if overworld_play:
        # AgbMain continues configuring callbacks after InitHeap. Scheduling
        # CB2_NewGame there can be overwritten by subsequent boot setup.
        # Initialize save-block pointers before NewGameInitData: pinned RHH
        # InitMainCallbacks initializes only SaveBlock2/Storage, while
        # gSaveBlock1Ptr remains NULL until SetSaveBlocksPointers().
        # Install the callback once after this prerequisite.
        tick += ("\n    { static bool8 sXgbaNewGameScheduled = FALSE;"
                 "\n      if (!sXgbaNewGameScheduled) {"
                 "\n        sXgbaNewGameScheduled = TRUE;"
                 "\n        SetSaveBlocksPointers(0);"
                 "\n        /* FRLG normally receives a terminated rival name from the intro. */"
                 "\n#if defined(FIRERED) || defined(LEAFGREEN)" 
                 "\n        gSaveBlock1Ptr->rivalName[0] = EOS;"
                 "\n#endif"
                 "\n        SetMainCallback2(CB2_NewGame);"
                 "\n      }\n    }")
    text = _one(text,
                "    ReadKeys();",
                tick,
                "normal game loop")
    return text


@contextmanager
def patched_source(source: Path, target: str, *, map_smoke: bool = False,
                   overworld_play: bool = False):
    """Apply only during build; reliably restore upstream source afterwards."""
    if map_smoke and overworld_play:
        raise ExpansionDrift("native map smoke and playable overworld are mutually exclusive")
    report = validate_source(source, target)
    path = source / "src/main.c"
    fieldmap_path = source / "src/fieldmap.c"
    overworld_path = source / "src/overworld.c"
    save_heap_path = source / "src/load_save.c"
    battle_path = source / "src/battle_gfx_sfx_util.c"
    if not battle_path.is_file():
        raise ExpansionDrift("pinned RHH battle graphics loader missing")
    battle_before = battle_path.read_text(encoding="utf-8")
    battle_after = patched_battle_graphics(battle_before)
    save_heap_before = save_heap_path.read_text(encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    fieldmap_before = fieldmap_path.read_text(encoding="utf-8")
    overworld_before = overworld_path.read_text(encoding="utf-8") if overworld_play else None
    header = ROOT / "integration/fire_red/xgba_guest.h"
    probe_path = ROOT / "integration/expansion/xgba_expansion_probe.inc"
    if not header.is_file() or not probe_path.is_file():
        raise ExpansionDrift("XGBA shared ABI/probe source unavailable")
    after = patched_main(before, header, probe_path.read_text(encoding="utf-8"),
                         map_smoke=map_smoke, overworld_play=overworld_play)
    fieldmap_after = patched_fieldmap(fieldmap_before)
    save_heap_after = patched_save_heap(save_heap_before)
    overworld_after = patched_overworld(overworld_before) if overworld_play else None
    try:
        path.write_text(after, encoding="utf-8")
        fieldmap_path.write_text(fieldmap_after, encoding="utf-8")
        save_heap_path.write_text(save_heap_after, encoding="utf-8")
        if battle_after is not None:
            battle_path.write_text(battle_after, encoding="utf-8")
        if overworld_play:
            overworld_path.write_text(overworld_after, encoding="utf-8")
        yield report
    finally:
        path.write_text(before, encoding="utf-8")
        fieldmap_path.write_text(fieldmap_before, encoding="utf-8")
        save_heap_path.write_text(save_heap_before, encoding="utf-8")
        if battle_before is not None:
            battle_path.write_text(battle_before, encoding="utf-8")
        if overworld_play:
            overworld_path.write_text(overworld_before, encoding="utf-8")


def require_release_tag(source: Path, tag: str) -> str:
    sha = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    tags = subprocess.check_output(
        ["git", "-C", str(source), "tag", "--points-at", "HEAD"], text=True)
    if tag not in tags.splitlines():
        raise ExpansionDrift(f"source HEAD {sha} is not tagged {tag}")
    if tag == VALIDATED_RELEASE and sha != VALIDATED_RELEASE_SHA:
        raise ExpansionDrift(f"release tag {tag} moved to unexpected commit {sha}")
    return sha


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--target", choices=TARGETS, required=True)
    p.add_argument("--map-smoke", action="store_true",
                   help="opt-in actual original map and tileset loader test at boot")
    p.add_argument("--overworld-play", action="store_true",
                   help="opt-in real game new-game callback and physical mGBA D-pad test")
    p.add_argument("--build", action="store_true",
                   help="build the temporary patched upstream source")
    p.add_argument("--require-tag", default=None,
                   help="fail closed unless HEAD carries this exact tag")
    args = p.parse_args()
    source = args.source.resolve()
    report = validate_source(source, args.target)
    # Compiled adapters depend on exact RHH source anchors and structures.
    # Refuse an unpinned checkout even when the caller omits --require-tag.
    # Read-only source inspection remains available without a Git checkout.
    required_tag = args.require_tag or (VALIDATED_RELEASE if args.build else None)
    if required_tag:
        if required_tag != VALIDATED_RELEASE:
            raise ExpansionDrift(f"unsupported expansion release: {required_tag}")
        report["upstream_head"] = require_release_tag(source, required_tag)
        report["release_tag"] = required_tag
    report["map_smoke_requested"] = bool(args.map_smoke)
    report["overworld_play_requested"] = bool(args.overworld_play)
    if args.build:
        with patched_source(source, args.target, map_smoke=args.map_smoke,
                            overworld_play=args.overworld_play):
            subprocess.run(["make", args.target, "-j2"], cwd=source, check=True)
        report["source_build_passed"] = True
    else:
        report["source_build_passed"] = False
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
