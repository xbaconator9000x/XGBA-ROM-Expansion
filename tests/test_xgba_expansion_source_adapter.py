"""Source-safe regression tests for the RHH Emerald/FireRed/LeafGreen adapter."""
import sys
import re
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import xgba_expansion_source_adapter as adapter

MAIN = (
    '#include "global.h"\n'
    'EWRAM_DATA unsigned char sTestBuffer[1];\n'
    'void AgbMain(void)\n'
    '{\n'
    '    InitHeap(gHeap, HEAP_SIZE);\n'
    '    gSoftResetDisabled = FALSE;\n'
    '}\n'
    'void AgbMainLoop(void)\n'
    '{\n'
    '    for (;;) {\n'
    '    ReadKeys();\n'
    '    }\n'
    '}\n'
)
FIELDMAP = (
    'COMMON_DATA struct BackupMapLayout gBackupMapLayout = {0};\n'
    'static inline u16 GetBorderBlockAt(int x, int y)\n'
    '{\n    return 0;\n}\n'
    'static void InitMapLayoutData(const struct MapHeader *mapHeader)\n'
    '{\n'
    '    InitBackupMapLayoutData(mapLayout->map, mapLayout->width, mapLayout->height);\n'
    '}\n'
    'static void CopyTilesetToVram(struct Tileset const *tileset, u16 numTiles, u16 offset)\n'
    '{\n    if (tileset) {}\n}\n'
    'static void CopyTilesetToVramUsingHeap(struct Tileset const *tileset, u16 numTiles, u16 offset)\n'
    '{\n    if (tileset) {}\n}\n'
)

OVERWORLD = (
    'void CB2_NewGame(void)\n'
    '{\n'
    '    NewGameInitData();\n'
    '    ResetInitialPlayerAvatarState();\n'
    '    gFieldCallback2 = NULL;\n'
    '    DoMapLoadLoop(&gMain.state);\n'
    '}\n'
    'void CB2_Overworld(void)\n'
    '{\n'
    '    bool32 fading = (gPaletteFade.active != 0);\n'
    '    OverworldBasic();\n'
    '    if (fading)\n'
    '        SetFieldVBlankCallback();\n'
    '}\n'
)

MAKEFILE = (
    'GAME_VERSION ?= EMERALD\n'
    'GAME_VERSION := FIRERED\n'
    'GAME_VERSION := LEAFGREEN\n'
    'emerald: all\n'
    'firered: all\n'
    'leafgreen: all\n'
)


class ExpansionSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "include").mkdir()
        (self.root / "Makefile").write_text(MAKEFILE)
        (self.root / "src/main.c").write_text(MAIN)
        (self.root / "src/fieldmap.c").write_text(FIELDMAP)
        (self.root / "src/battle_gfx_sfx_util.c").write_text(
            "void DecompressTrainerFrontPic(enum TrainerPicID trainerPicId, enum BattlerId battler)\n"
            "{\n"
            "    DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId), gMonSpritesGfxPtr->spritesGfx[position]);\n"
            "}\n"
            "void BattleLoadMonSpriteGfx(struct Pokemon *mon, enum BattlerId battler)\n"
            "{\n"
            "    position = GetBattlerPosition(battler);\n"
            "    HandleLoadSpecialPokePic(!IsOnPlayerSide(battler),\n"
            "                             gMonSpritesGfxPtr->spritesGfx[position],\n"
            "                             species, personalityValue);\n"
            "    paletteOffset = OBJ_PLTT_ID(battler);\n"
            "}\n"
        )
        (self.root / "src/load_save.c").write_text("void MoveSaveBlocks_ResetHeap(void)\n{\n    InitHeap(gHeap, HEAP_SIZE);\n}\n")
        (self.root / "src/overworld.c").write_text(OVERWORLD)
        (self.root / "include/global.h").write_text("/* RHH global ABI */\n")

    def test_all_three_upstream_targets_checked(self):
        for target in adapter.TARGETS:
            with self.subTest(target=target):
                report = adapter.validate_source(self.root, target)
                self.assertEqual(report["target"], target)
                self.assertFalse(report["runtime_gameplay_verified"])
                self.assertEqual(report["guest_mmio_abi"], 1)

    def test_reversible_patch_restores_upstream_even_after_failure(self):
        file = self.root / "src/main.c"
        for target in adapter.TARGETS:
            with self.subTest(target=target):
                with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                    with adapter.patched_source(self.root, target):
                        patched = file.read_text()
                        self.assertEqual(patched.count("XgbaExpansionProbeBoot();"), 1)
                        self.assertEqual(patched.count("XgbaExpansionProbeTick();"), 1)
                        self.assertIn("XGBA_EXPANSION_RESOURCE_ID", patched)
                        self.assertIn("InitHeap(gHeap, XGBA_EXPANSION_HEAP_BYTES);", patched)
                        self.assertNotIn("InitHeap(gHeap, HEAP_SIZE);", patched)
                        fieldmap = (self.root / "src/fieldmap.c").read_text()
                        self.assertIn("XgbaExpansionTryMapCopy(mapLayout);", fieldmap)
                        self.assertIn("XgbaExpansionBindOriginalMap(mapHeader);", fieldmap)
                        self.assertEqual(fieldmap.count("XgbaExpansionTryTilesetCopy(tileset, numTiles, offset)"), 2)
                        self.assertIn("xgba_guest.h", patched)
                        raise RuntimeError("synthetic failure")
                self.assertEqual(file.read_text(), MAIN)
                self.assertEqual((self.root / "src/fieldmap.c").read_text(), FIELDMAP)

    def test_pinned_build_policy_rejects_unsupported_tag(self):
        # All compiled target adapters share one exact RHH release ABI.
        self.assertEqual(adapter.VALIDATED_RELEASE, "expansion/1.17.2")
        self.assertEqual(len(adapter.VALIDATED_RELEASE_SHA), 40)
        source = (adapter.ROOT / "tools/xgba_expansion_source_adapter.py").read_text()
        self.assertIn("required_tag = args.require_tag or (VALIDATED_RELEASE if args.build else None)", source)
        self.assertIn("if required_tag != VALIDATED_RELEASE:", source)
        self.assertIn("require_release_tag(source, required_tag)", source)

    def test_real_battle_sprite_lifecycle_releases_field_and_trainer_leases(self):
        original = (
            "void AllocateBattleSpritesData(void)\n"
            "{\n"
            "    gBattleSpritesDataPtr = AllocZeroed(sizeof(struct BattleSpriteData));\n"
            "}\n"
            "void FreeBattleSpritesData(void)\n"
            "{\n"
            "    if (gBattleSpritesDataPtr == NULL)\n"
            "        return;\n"
            "}\n"
            "void DecompressTrainerFrontPic(enum TrainerPicID trainerPicId, enum BattlerId battler)\n"
            "{\n"
            "    DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId), gMonSpritesGfxPtr->spritesGfx[position]);\n"
            "}\n"
        )
        patched = adapter.patched_battle_graphics(original)
        self.assertIn("extern void XgbaExpansionPageRelease(void);", patched)
        self.assertLess(patched.index("extern void XgbaExpansionPageRelease(void);"),
                        patched.index("void AllocateBattleSpritesData(void)"))
        self.assertIn("void AllocateBattleSpritesData(void)\n{\n    XgbaExpansionPageRelease();", patched)
        self.assertIn("void FreeBattleSpritesData(void)\n{\n    XgbaExpansionPageRelease();", patched)
        self.assertLess(patched.index("void AllocateBattleSpritesData(void)"),
                        patched.index("gBattleSpritesDataPtr = AllocZeroed"))
        self.assertLess(patched.index("void FreeBattleSpritesData(void)"),
                        patched.index("if (gBattleSpritesDataPtr == NULL)"))
        self.assertIn("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)", patched)
        broken = original.replace("void FreeBattleSpritesData(void)", "void RenamedFreeBattleSpritesData(void)")
        with self.assertRaisesRegex(adapter.ExpansionDrift, "incomplete battle sprite phase lifecycle"):
            adapter.patched_battle_graphics(broken)

    def test_trainer_red_leaf_original_loader_allowlist(self):
        original = (
            "void DecompressTrainerFrontPic(enum TrainerPicID trainerPicId, enum BattlerId battler)\n"
            "{\n"
            "    DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId), gMonSpritesGfxPtr->spritesGfx[position]);\n"
            "}\n"
        )
        patched = adapter.patched_battle_graphics(original)
        for name in ("RED", "LEAF", "HIKER", "HIKER_FRLG"):
            self.assertIn("id != TRAINER_PIC_" + name, patched)
        self.assertIn("bytes = GetDecompressedDataSize(original)", patched)
        self.assertIn("!IsCompressedData(original)", patched)
        self.assertIn("bytes != 64u * 64u / 2u", patched)
        self.assertIn("CpuCopy32", patched)
        self.assertIn("DecompressDataWithHeaderWram", patched)

    def test_trainer_page_never_aliases_engine_owned_sprite_destination(self):
        # The 16-KiB lease is poisoned on release. A partial overlap
        # (including a buffer starting before the page) must fall back.
        original = (
            "void DecompressTrainerFrontPic(enum TrainerPicID trainerPicId, enum BattlerId battler)\n"
            "{\n"
            "    DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId), gMonSpritesGfxPtr->spritesGfx[position]);\n"
            "}\n"
        )
        patched = adapter.patched_battle_graphics(original)
        # A 2-KiB graphics copy may only target engine-owned EWRAM.
        # This also excludes VRAM, I/O, ROM and destinations crossing 0x02040000.
        self.assertIn("(u32)dest < 0x02000000u", patched)
        self.assertIn("(u32)dest > 0x02040000u - bytes", patched)
        self.assertLess(patched.index("(u32)dest > 0x02040000u - bytes"),
                        patched.index("XgbaExpansionPageAcquire(resource, bytes)"))
        self.assertIn("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);", patched)
        self.assertIn("((u32)page & 3u)", patched)
        self.assertIn("(u32)page < 0x02000000u", patched)
        self.assertIn("(u32)page > 0x02040000u - XGBA_EXPANSION_PAGE_CAPACITY", patched)
        self.assertLess(patched.index("((u32)page & 3u)"),
                        patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);"))
        self.assertLess(patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);"),
                        patched.index("XgbaExpansionPageRelease();\n    /* A release must advance"))
        self.assertIn("(u32)dest - (u32)page < XGBA_EXPANSION_PAGE_CAPACITY", patched)
        self.assertIn("(u32)page - (u32)dest < bytes", patched)
        self.assertIn("XgbaExpansionPageRelease();\n        return FALSE;\n    }", patched)
        self.assertLess(patched.index("/* Do not report external success"), patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);"))
        self.assertNotIn("(u32)XGBA_EXPANSION_PAGE +", patched)
        self.assertIn("if (!XgbaExpansionTryTrainerPic(", patched)
        self.assertIn("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)", patched)

    def test_save_block_heap_reset_preserves_page_lease_and_restores_source(self):
        path = self.root / "src/load_save.c"
        before = path.read_text()
        with adapter.patched_source(self.root, "emerald"):
            self.assertIn("InitHeap(gHeap, HEAP_SIZE - 0x4000u);", path.read_text())
            self.assertNotIn("InitHeap(gHeap, HEAP_SIZE);", path.read_text())
        self.assertEqual(path.read_text(), before)
        with self.assertRaisesRegex(adapter.ExpansionDrift, "save relocation heap lease"):
            adapter.patched_save_heap(before.replace("HEAP_SIZE", "OTHER_HEAP_SIZE"))

    def test_trainer_destination_excludes_entire_reserved_heap_tail(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        lease = patched.index("leaseStart = (u32)gHeap + HEAP_SIZE - XGBA_EXPANSION_PAGE_CAPACITY;")
        end = patched.index("leaseEnd = leaseStart + XGBA_EXPANSION_PAGE_CAPACITY;", lease)
        overlap = patched.index("destStart < leaseEnd && leaseStart < destStart + bytes", end)
        acquire = patched.index("XgbaExpansionPageAcquire(resource, bytes)")
        copy = patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);")
        self.assertLess(lease, end)
        self.assertLess(end, overlap)
        self.assertLess(overlap, acquire)
        self.assertLess(acquire, copy)
        self.assertIn("if (destStart < leaseEnd && leaseStart < destStart + bytes)\n            return FALSE;", patched)

    def test_trainer_copy_revalidates_lease_before_reading_source_after_copy(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        copy = patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);")
        verify = patched.index("if (((const u8 *)dest)[offset + j] != page[offset + j])", copy)
        between = patched[copy:verify]
        # A provider may revoke or replace a page during the synchronous
        # copy. Never dereference the invalidated source in verification.
        for guard in ("XgbaExpansionPageGeneration() != generation",
                      "XgbaExpansionPageData() != page",
                      "XgbaExpansionPageResidentBytes() != bytes"):
            self.assertIn(guard, between)
        self.assertRegex(between, r"XgbaExpansionPageRelease\(\);\s*return FALSE;")
        self.assertLess(between.index("XgbaExpansionPageGeneration() != generation"),
                        between.index("if (((const u8 *)dest)[offset + j]")
                        if "if (((const u8 *)dest)[offset + j]" in between
                        else len(between))

    def test_trainer_copy_rejects_provider_generation_churn(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        self.assertIn("u32 generation = XgbaExpansionPageGeneration();", patched)
        self.assertIn("XgbaExpansionPageGeneration() != generation", patched)
        self.assertIn("XgbaExpansionPageData() != page", patched)
        self.assertIn("XgbaExpansionPageResidentBytes() != bytes", patched)
        copy = patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);")
        post_copy_generation = patched.index("XgbaExpansionPageGeneration() != generation", copy)
        self.assertLess(copy, post_copy_generation)
        # The first generation guard follows the pre-copy source hash;
        # the second must follow the actual synchronous transfer.
        source_hash = patched.index("sourceHash = (sourceHash ^ page[i])")
        pre_copy_guard = patched.index("XgbaExpansionPageGeneration() != generation", source_hash)
        self.assertLess(source_hash, pre_copy_guard)
        self.assertLess(pre_copy_guard, copy)
        self.assertLess(copy, post_copy_generation)
        self.assertIn("XgbaExpansionPageRelease();\n            return FALSE;", patched)

    def test_trainer_verification_rechecks_page_generation_before_success(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        start = patched.index("for (u32 i = 0; i < bytes; ++i)")
        final_check = patched.index("/* A provider callback can invalidate the lease", start)
        transfer = patched.index("XgbaExpansionTrainerTransfer(id, dest, bytes);", final_check)
        self.assertLess(start, final_check)
        self.assertLess(final_check, transfer)
        guard = patched[final_check:transfer]
        self.assertIn("XgbaExpansionPageGeneration() != generation", guard)
        self.assertIn("XgbaExpansionPageData() != page", guard)
        self.assertIn("XgbaExpansionPageResidentBytes() != bytes", guard)
        self.assertIn("XgbaExpansionPageRelease();", guard)
        self.assertIn("return FALSE;", guard)

    def test_trainer_page_rehashed_after_engine_copy_before_success(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        copy = patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);")
        final_hash = patched.index("u32 finalSourceHash = 2166136261u;")
        comparison = patched.index("if (finalSourceHash != sourceHash)")
        release = patched.index("XgbaExpansionPageRelease();", comparison)
        success = patched.index("XgbaExpansionTrainerTransfer(id, dest, bytes);")
        self.assertLess(copy, final_hash)
        self.assertLess(final_hash, comparison)
        self.assertLess(comparison, release)
        self.assertLess(release, success)
        self.assertIn("finalSourceHash = (finalSourceHash ^ page[i]) * 16777619u;", patched)

    def test_trainer_rejects_invalid_heap_lease_geometry_before_provider(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        geometry = transfer.index("leaseStart < 0x02000000u")
        upper = transfer.index("leaseStart > 0x02040000u - XGBA_EXPANSION_PAGE_CAPACITY")
        end = transfer.index("leaseEnd = leaseStart + XGBA_EXPANSION_PAGE_CAPACITY;")
        acquire = transfer.index("XgbaExpansionPageAcquire(resource, bytes)")
        copy = transfer.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);")
        self.assertLess(geometry, upper)
        self.assertLess(upper, end)
        self.assertLess(end, acquire)
        self.assertLess(acquire, copy)
        self.assertIn("if (destStart < leaseEnd && leaseStart < destStart + bytes)", transfer)
        self.assertIn("return FALSE;", transfer[geometry:acquire])

    def test_trainer_lease_rejects_undersized_heap_before_acquisition(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1]
        guard = "HEAP_SIZE < XGBA_EXPANSION_PAGE_CAPACITY"
        self.assertIn(guard, transfer)
        self.assertLess(transfer.index(guard),
                        transfer.index("leaseStart = (u32)gHeap + HEAP_SIZE - XGBA_EXPANSION_PAGE_CAPACITY;"))
        self.assertLess(transfer.index(guard),
                        transfer.index("XgbaExpansionPageAcquire(resource, bytes)"))
        self.assertIn("if (!XgbaExpansionTryTrainerPic(", patched)
        self.assertIn("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)", patched)

    def test_trainer_release_invalidates_generation_before_reporting_success(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        release = patched.index("XgbaExpansionPageRelease();\n    /* A release must advance")
        generation_guard = patched.index("XgbaExpansionPageGeneration() == generation", release)
        residency_guard = patched.index("XgbaExpansionPageResidentBytes() != 0u", generation_guard)
        transfer = patched.index("XgbaExpansionTrainerTransfer(id, dest, bytes);", residency_guard)
        self.assertLess(release, generation_guard)
        self.assertLess(generation_guard, residency_guard)
        self.assertLess(residency_guard, transfer)
        self.assertIn("return FALSE;", patched[generation_guard:residency_guard])

    def test_trainer_external_transfer_requires_original_rom_image_stream(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        checks = (
            "(u32)original < 0x08000000u",
            "(u32)original > 0x0A000000u - 8u",
            "!IsCompressedData(original)",
        )
        for check in checks:
            self.assertIn(check, transfer)
            self.assertLess(transfer.index(check), transfer.index("bytes = GetDecompressedDataSize(original)"))
        self.assertLess(transfer.index("!IsCompressedData(original)"),
                        transfer.index("bytes = GetDecompressedDataSize(original)"))
        self.assertLess(transfer.index("bytes = GetDecompressedDataSize(original)"),
                        transfer.index("if (bytes != 64u * 64u / 2u)"))
        self.assertLess(transfer.index("if (bytes != 64u * 64u / 2u)"),
                        transfer.index("XgbaExpansionPageAcquire(resource, bytes)"))
        self.assertIn("smol.mode > ENCODE_BOTH_DELTA_SYMS", transfer)
        self.assertIn("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)", patched)

    def test_trainer_release_cannot_silently_corrupt_engine_sprite_buffer(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        release = transfer.index("    XgbaExpansionPageRelease();\n    /* A release must advance")
        post_release = transfer.index("u32 releasedHash = 2166136261u;", release)
        reject = transfer.index("if (releasedHash != destinationHash)", post_release)
        witness = transfer.index("XgbaExpansionTrainerTransfer(id, dest, bytes);", reject)
        self.assertLess(release, post_release)
        self.assertLess(post_release, reject)
        self.assertLess(reject, witness)
        self.assertIn("if (releasedHash != destinationHash)\n            return FALSE;", transfer)
        self.assertIn("if (!XgbaExpansionTryTrainerPic(", patched)

    def test_trainer_witness_rejects_transient_page_reacquisition(self):
        # A witness can acquire and release a page in one callback, leaving
        # no resident pointer. The lease generation still must invalidate
        # external success, with the original RHH decompressor as fallback.
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        capture = transfer.index("u32 releasedGeneration = XgbaExpansionPageGeneration();")
        witness = transfer.index("XgbaExpansionTrainerTransfer(id, dest, bytes);", capture)
        guard = transfer.index("XgbaExpansionPageGeneration() != releasedGeneration", witness)
        hash_check = transfer.index("u32 witnessedHash = 2166136261u;", guard)
        success = transfer.index("return TRUE;", hash_check)
        self.assertLess(capture, witness)
        self.assertLess(witness, guard)
        self.assertLess(guard, hash_check)
        self.assertLess(hash_check, success)
        self.assertIn("XgbaExpansionPageRelease();", transfer[guard:hash_check])
        self.assertIn("return FALSE;", transfer[guard:hash_check])
        self.assertIn("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)", patched)

    def test_trainer_page_requires_exact_reserved_heap_tail(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        exact = "(u32)page != (u32)gHeap + HEAP_SIZE - XGBA_EXPANSION_PAGE_CAPACITY"
        self.assertIn(exact, transfer)
        self.assertIn("(u32)page > 0x02040000u - XGBA_EXPANSION_PAGE_CAPACITY", transfer)
        self.assertLess(transfer.index(exact), transfer.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);"))
        self.assertLess(transfer.index(exact), transfer.index("XgbaExpansionTrainerTransfer(id, dest, bytes);"))
        self.assertIn("XgbaExpansionPageRelease();\n        return FALSE;", transfer)

    def test_trainer_chunk_verification_precedes_next_copy_and_falls_back(self):
        # Every 256-byte synchronous copy must be checked before the next
        # chunk, and a torn chunk must release the page and use RHH fallback.
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        copy = patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);")
        verify = patched.index("((const u8 *)dest)[offset + j] != page[offset + j]", copy)
        release = patched.index("XgbaExpansionPageRelease();", verify)
        next_guard = patched.index("XgbaExpansionPageGeneration() != generation", release)
        self.assertLess(copy, verify)
        self.assertLess(verify, release)
        self.assertLess(release, next_guard)
        self.assertIn("for (u32 j = 0; j < chunk; ++j)", patched[copy:verify])
        self.assertIn("return FALSE;", patched[verify:next_guard])
        self.assertIn("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)", patched)

    def test_trainer_copy_integrity_precedes_success_and_releases_on_mismatch(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        copy = patched.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);")
        verify = patched.index("((const u8 *)dest)[i] != page[i]")
        failure = patched.index("XgbaExpansionPageRelease();", verify)
        success = patched.index("XgbaExpansionTrainerTransfer(id, dest, bytes);")
        self.assertLess(copy, verify)
        self.assertLess(verify, failure)
        self.assertLess(failure, success)
        self.assertIn("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)", patched)

    def test_trainer_loader_preserves_original_palette_and_fallback(self):
        # The original RHH battle entry loads the trainer palette after
        # decompressing tiles; external tiles must not skip that side effect.
        original = (
            "void DecompressTrainerFrontPic(enum TrainerPicID trainerPicId, enum BattlerId battler)\n"
            "{\n"
            "    DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId), gMonSpritesGfxPtr->spritesGfx[position]);\n"
            "    LoadSpritePaletteWithTag(GetTrainerFrontPicPalette(trainerPicId), GetTrainerPicTag(trainerPicId, TRUE));\n"
            "}\n"
        )
        patched = adapter.patched_battle_graphics(original)
        self.assertEqual(patched.count("LoadSpritePaletteWithTag("), 1)
        self.assertIn("if (!XgbaExpansionTryTrainerPic(", patched)
        self.assertLess(patched.index("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)"),
                        patched.index("LoadSpritePaletteWithTag("))

    def test_patched_build_rejects_missing_battle_loader(self):
        # A source build without the authentic loader must never silently
        # ship map-only integration while reporting battle support.
        battle = self.root / "src/battle_gfx_sfx_util.c"
        battle.unlink()
        with self.assertRaisesRegex(adapter.ExpansionDrift, "missing original battle graphics loader"):
            with adapter.patched_source(self.root, "emerald"):
                self.fail("missing battle loader was accepted")
        self.assertEqual((self.root / "src/main.c").read_text(), MAIN)
        self.assertEqual((self.root / "src/fieldmap.c").read_text(), FIELDMAP)

    def test_original_battle_loader_must_be_present_and_unmodified(self):
        path = self.root / "src/battle_gfx_sfx_util.c"
        original = path.read_text()
        path.unlink()
        with self.assertRaisesRegex(adapter.ExpansionDrift, "missing original battle graphics loader"):
            adapter.validate_source(self.root, "emerald")
        path.write_text(original.replace("DecompressTrainerFrontPic", "AlteredTrainerLoader"))
        with self.assertRaisesRegex(adapter.ExpansionDrift, "trainer graphics loader ABI drift"):
            adapter.validate_source(self.root, "firered")
        path.write_text(original)
        with adapter.patched_source(self.root, "leafgreen"):
            self.assertIn("XgbaExpansionTryTrainerPic", path.read_text())
        self.assertEqual(path.read_text(), original)

    def test_rejects_missing_game_target_or_build_matrix(self):
        with self.assertRaises(adapter.ExpansionDrift):
            adapter.validate_source(self.root, "ruby")
        (self.root / "Makefile").write_text(MAKEFILE.replace("firered: all", ""))
        with self.assertRaisesRegex(adapter.ExpansionDrift, "build matrix"):
            adapter.validate_source(self.root, "emerald")

    def test_rejects_source_drift_instead_of_wrong_hook(self):
        file = self.root / "src/main.c"
        file.write_text(MAIN.replace("InitHeap(gHeap, HEAP_SIZE);", "InitHeapEx();"))
        with self.assertRaisesRegex(adapter.ExpansionDrift, "main ABI drift"):
            adapter.validate_source(self.root, "firered")

    def test_rejects_double_patching(self):
        file = self.root / "src/main.c"
        with adapter.patched_source(self.root, "emerald"):
            with self.assertRaisesRegex(adapter.ExpansionDrift, "already patched"):
                adapter.validate_source(self.root, "emerald")
        self.assertEqual(file.read_text(), MAIN)

    def test_opt_in_smoke_calls_real_upstream_loader_and_restores_source(self):
        path = self.root / "src/main.c"
        fieldmap_path = self.root / "src/fieldmap.c"
        for target in adapter.TARGETS:
            with self.subTest(target=target):
                with adapter.patched_source(self.root, target, map_smoke=True):
                    text = path.read_text()
                    fieldmap = fieldmap_path.read_text()
                    self.assertEqual(text.count("XgbaExpansionNativeMapTileSmoke();"), 1)
                    self.assertIn("InitMapLayoutData(&header);", fieldmap)
                    self.assertIn("CopyPrimaryTilesetToVram(layout);", fieldmap)
                    self.assertIn("XgbaExpansionMapSmokeReport(layoutId", fieldmap)
                self.assertEqual(path.read_text(), MAIN)
                self.assertEqual(fieldmap_path.read_text(), FIELDMAP)


    def test_real_overworld_entry_uses_normal_new_game_map_and_player_callback(self):
        path = self.root / "src/main.c"
        game = self.root / "src/overworld.c"
        for target in adapter.TARGETS:
            with self.subTest(target=target):
                with adapter.patched_source(self.root, target, overworld_play=True):
                    main = path.read_text()
                    ow = game.read_text()
                    self.assertIn("SetMainCallback2(CB2_NewGame);", main)
                    self.assertIn("SetSaveBlocksPointers(0);", main)
                    self.assertIn("#if defined(FIRERED) || defined(LEAFGREEN)", main)
                    self.assertIn("gSaveBlock1Ptr->rivalName[0] = EOS;", main)
                    self.assertIn("#endif\n        SetMainCallback2(CB2_NewGame);", main)
                    self.assertNotIn("if (IS_FRLG) gSaveBlock1Ptr->rivalName", main)
                    self.assertLess(main.index("SetSaveBlocksPointers(0);"), main.index("rivalName[0] = EOS;"))
                    self.assertLess(main.index("rivalName[0] = EOS;"), main.index("SetMainCallback2(CB2_NewGame);"))
                    self.assertLess(main.index("SetSaveBlocksPointers(0);"), main.index("SetMainCallback2(CB2_NewGame);"))
                    self.assertIn("static bool8 sXgbaNewGameScheduled = FALSE;", main)
                    self.assertLess(main.index("ReadKeys();"), main.index("SetMainCallback2(CB2_NewGame);"))
                    self.assertNotIn("InitHeap(gHeap, XGBA_EXPANSION_HEAP_BYTES);\\n    SetMainCallback2", main)
                    self.assertNotIn("XgbaExpansionNativeMapTileSmoke();", main)
                    self.assertIn("NewGameInitData();", ow)
                    self.assertIn("WarpIntoMap();", ow)
                    self.assertIn("MAP_LITTLEROOT_TOWN", ow)
                    self.assertIn("MAP_PALLET_TOWN", ow)
                    self.assertIn("XgbaExpansionLiveTick(gMapHeader.mapLayoutId", ow)
                    self.assertEqual(ow.count("OverworldBasic();"), 1)
                self.assertEqual(game.read_text(), OVERWORLD)
                self.assertEqual(path.read_text(), MAIN)
                self.assertEqual((self.root / "src/fieldmap.c").read_text(), FIELDMAP)

    def test_overworld_and_boot_smoke_exclusive(self):
        with self.assertRaisesRegex(adapter.ExpansionDrift, "mutually exclusive"):
            with adapter.patched_source(self.root, "emerald",
                                        map_smoke=True, overworld_play=True):
                pass

    def test_real_overworld_host_does_not_write_player_memory(self):
        code = (adapter.ROOT / "integration/mgba/xgba_expansion_overworld_native.h").read_text()
        self.assertIn("core->setKeys(core,1u<<4)", code)
        self.assertIn("core->setKeys(core,1u<<6)", code)
        self.assertIn("RHH_REAL_OVERWORLD_DIAG", code)
        self.assertIn("RHH_ROUTE_ATTEMPT", code)
        self.assertIn("if (final_map!=next_id || transitions<1u)", code)
        self.assertNotIn("core->busWrite", code)
        proof = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        self.assertIn("void XgbaExpansionLiveTick(u32 layout, s32 x, s32 y)", proof)
        self.assertIn("live_transitions", proof)
        self.assertIn("live_source_primary", proof)

    def test_short_final_map_page_and_two_part_frlg_tileset_are_counted(self):
        # A for(start += 16KiB) loop cannot compare start == total
        # after the final 800-byte map or 4096-byte FRLG tileset page.
        # Only bytes actually transferred establish success.
        bridge = (adapter.ROOT / "integration/expansion/xgba_expansion_fieldmap.inc").read_text()
        self.assertNotIn("if (start == total)", bridge)
        self.assertEqual(bridge.count("copied += n;"), 1)
        self.assertEqual(bridge.count("if (copied == total)"), 1)
        # The graphics path now stages every page in owned heap memory
        # before handing the complete tileset to the upstream BG DMA API.
        self.assertIn("CpuCopy16(page, staging + start, resident);", bridge)
        self.assertIn("resident = XgbaExpansionPageResidentBytes();", bridge)
        self.assertIn("resident != n && tileset != sXgbaMapLayout->secondaryTileset", bridge)
        self.assertIn("if (copied != total || partialSecondary)", bridge)
        self.assertIn("XgbaExpansionPageAcquire(id, n) != n", bridge)
        self.assertIn("copied += resident;", bridge)
        self.assertIn("header[0] != 0x10u", bridge)
        self.assertIn("LoadBgTiles(2, staging, total, offset)", bridge)
        self.assertIn("IsDma3ManagerBusyWithBgCopy()", bridge)
        self.assertNotIn("REG_DISPCNT = originalDisplay", bridge.split("static bool8 XgbaExpansionTryTilesetCopy")[1].split("Explicit test-only")[0])
        self.assertIn("sXgbaSmokeMapUsed = TRUE;", bridge)
        self.assertIn("sXgbaSmokePrimaryUsed = TRUE;", bridge)
        self.assertIn("InitBackupMapLayoutData(layout->map", bridge)
        self.assertIn("XgbaExpansionPageRelease();", bridge)

    def test_native_map_proof_verifies_guest_hashes_and_both_provider_states(self):
        native = (adapter.ROOT / "integration/mgba/xgba_expansion_native.h").read_text()
        self.assertIn("xgba_expansion_native_field_load", native)
        self.assertIn("actual_map!=expect_map", native)
        self.assertIn("enabled && actual_tiles!=expect_tiles", native)
        self.assertIn("used_map!=(enabled?1u:0u)", native)
        self.assertIn("device->successful_reads!=expected_reads", native)
        probe = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        self.assertIn("map_smoke_map_hash", probe)
        self.assertIn("map_smoke_tiles_hash", probe)

    def test_trainer_transfer_detects_in_place_provider_mutation(self):
        # A page can change its bytes without changing its pointer or
        # generation. Capture an independent source digest before copying,
        # and compare with the engine-owned destination after transfer.
        patched = adapter.patched_battle_graphics(
            (self.root / "src/battle_gfx_sfx_util.c").read_text())
        start = patched.index("static bool8 XgbaExpansionTryTrainerPic")
        end = patched.index("void DecompressTrainerFrontPic", start)
        transfer = patched[start:end]
        self.assertIn("u32 sourceHash = 2166136261u;", transfer)
        self.assertIn("u32 destinationHash = 2166136261u;", transfer)
        self.assertLess(transfer.index("sourceHash = (sourceHash ^ page[i])"),
                        transfer.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk)"))
        self.assertGreater(transfer.index("destinationHash = (destinationHash ^"),
                           transfer.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk)"))
        self.assertLess(transfer.index("if (destinationHash != sourceHash)"),
                        transfer.index("XgbaExpansionTrainerTransfer(id, dest, bytes)"))
        self.assertIn("XgbaExpansionPageRelease();\n        return FALSE;", transfer)

    def test_trainer_transfer_requires_released_page_before_success(self):
        # A provider that retains its lease after Release must not be
        # considered a completed battle sprite transfer.
        patched = adapter.patched_battle_graphics(
            (self.root / "src/battle_gfx_sfx_util.c").read_text())
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        release = transfer.index("    XgbaExpansionPageRelease();\n    /* A release must advance")
        resident = transfer.index("if (XgbaExpansionPageResidentBytes() != 0u", release)
        data = transfer.index("|| XgbaExpansionPageData() != NULL", resident)
        integrity = transfer.index("u32 releasedHash = 2166136261u;", data)
        witness = transfer.index("XgbaExpansionTrainerTransfer(id, dest, bytes);", integrity)
        self.assertLess(release, resident)
        self.assertLess(resident, data)
        self.assertLess(data, integrity)
        self.assertLess(integrity, witness)

    def test_native_expansion_mode_owns_lcd_buffer_in_both_guards(self):
        # Regression: every expanded-engine variant previously segfaulted
        # (signal 11) when native LCD capture had no allocated video buffer.
        native = (adapter.ROOT / "integration/mgba/xgba_mgba_headless.c").read_text()
        self.assertEqual(native.count("r15_dir || r16_dir || expansion_dir || r24_dir"), 2)
        self.assertIn("if (video)\n        core->setVideoBuffer(core, video, 240);", native)
        header = (adapter.ROOT / "integration/mgba/xgba_expansion_native.h").read_text()
        self.assertIn('fail("RHH native mGBA framebuffer not attached")', header)

    def test_real_heap_tail_16k_page_contract(self):
        content = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        native = (adapter.ROOT / "integration/mgba/xgba_expansion_native.h").read_text()
        harness = (adapter.ROOT / "tools/xgba_expansion_native_acceptance.py").read_text()
        self.assertIn("#define XGBA_EXPANSION_PAGE_BYTES 0x4000u", content)
        self.assertIn("HEAP_SIZE - XGBA_EXPANSION_PAGE_BYTES", content)
        self.assertIn("XgbaExpansionPageAcquire", content)
        self.assertIn("XgbaExpansionPageReset", content)
        self.assertIn("gXgbaExpansionProof.page_resident = 0u;", content)
        self.assertIn("gXgbaExpansionProof.page_resident = length;", content)
        self.assertIn("return 0u; /* reject truncation/ambiguous source resource ID */", content)
        self.assertIn("uint8_t expected[16384];", native)
        self.assertIn("RHH original engine overwrote protected XGBA page", native)
        self.assertIn("PAGE_PAYLOAD = bytes(", harness)
        self.assertIn("range(16 * 1024)", harness)

    def test_public_runtime_page_api_contract(self):
        header = (adapter.ROOT / "integration/expansion/xgba_expansion_page.h").read_text()
        impl = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        for fn in ("XgbaExpansionPageAcquire", "XgbaExpansionPageRelease",
                   "XgbaExpansionPageData", "XgbaExpansionPageResidentBytes",
                   "XgbaExpansionPageGeneration"):
            self.assertIn(fn, header)
            self.assertIn(fn, impl)
        self.assertIn("return gXgbaExpansionProof.page_resident ? XGBA_EXPANSION_PAGE : NULL;", impl)
        self.assertIn("XgbaExpansionPageReset();\n        return 0u;", impl)
        self.assertIn("XgbaExpansionPageReset();\n        return 0u; /* reject truncation", impl)
        self.assertIn("XGBA_EXPANSION_PAGE_CAPACITY 16384u", header)
        patched = adapter.patched_main(
            MAIN, adapter.ROOT / "integration/fire_red/xgba_guest.h", impl)
        self.assertIn("xgba_expansion_page.h", patched)
        self.assertNotIn("__XGBA_PAGE_API__", patched)

    def test_fieldmap_hooks_fail_closed_and_reversible(self):
        patched = adapter.patched_fieldmap(FIELDMAP)
        self.assertIn("XgbaExpansionTryMapCopy(mapLayout)", patched)
        self.assertIn("DISPCNT_FORCED_BLANK", patched)
        self.assertIn("XgbaExpansionBindOriginalMap(mapHeader);", patched)
        self.assertIn("XgbaExpansionChunkId", patched)
        self.assertIn("InitBackupMapLayoutData(layout->map", patched)
        self.assertIn("XgbaExpansionPageRelease()", patched)
        self.assertIn("XgbaExpansionBindMapTilesets", patched)
        self.assertEqual(patched.count("XgbaExpansionTryTilesetCopy(tileset, numTiles, offset)"), 2)
        with self.assertRaisesRegex(adapter.ExpansionDrift, "CopyTilesetToVram"):
            adapter.patched_fieldmap(patched)

    def test_rejects_injected_header_path(self):
        probe = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        with self.assertRaisesRegex(adapter.ExpansionDrift, "unsafe header path"):
            adapter.patched_main(MAIN, Path('/bad/"quote.h'), probe)


    def test_trainer_battle_entry_evicts_stale_field_page_even_on_fallback(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        entry_release = transfer.index("XgbaExpansionPageRelease();")
        allowlist = transfer.index("if (!original || !dest")
        acquire = transfer.index("XgbaExpansionPageAcquire(resource, bytes)")
        self.assertLess(entry_release, allowlist)
        self.assertLess(allowlist, acquire)
        self.assertIn("if (!XgbaExpansionTryTrainerPic(", patched)
        self.assertIn(
            "DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)",
            patched,
        )


    def test_private_trainer_pack_flushes_data_before_manifest_publish(self):
        # A manifest must not advertise a partially buffered private provider.
        pack = (adapter.ROOT / "tools/xgba_expansion_trainer_pages.py").read_text()
        self.assertIn("import os", pack)
        data = pack.index('with private_create(data) as handle:')
        data_flush = pack.index("os.fsync(handle.fileno())", data)
        verify = pack.index('with data.open("rb") as verify:', data_flush)
        manifest = pack.index('with private_create(manifest, text=True) as handle:', verify)
        manifest_flush = pack.index("os.fsync(handle.fileno())", manifest)
        self.assertLess(data, data_flush)
        self.assertLess(data_flush, verify)
        self.assertLess(verify, manifest)
        self.assertLess(manifest, manifest_flush)
        self.assertIn("if created_manifest and manifest.exists():", pack)
        self.assertIn("if created_data and data.exists():", pack)


    def test_private_provider_verifies_manifest_and_syncs_directory(self):
        pack = (adapter.ROOT / "tools/xgba_expansion_trainer_pages.py").read_text()
        publish = pack.index('with private_create(manifest, text=True) as handle:')
        metadata_verify = pack.index('with manifest.open("r", encoding="utf-8") as verify_manifest:', publish)
        integrity = pack.index('json.load(verify_manifest) != record', metadata_verify)
        directory_open = pack.index('directory_fd = os.open(output, os.O_RDONLY', integrity)
        directory_sync = pack.index('os.fsync(directory_fd)', directory_open)
        directory_close = pack.index('os.close(directory_fd)', directory_sync)
        cleanup = pack.index('except BaseException:', directory_close)
        self.assertLess(publish, metadata_verify)
        self.assertLess(metadata_verify, integrity)
        self.assertLess(integrity, directory_open)
        self.assertLess(directory_open, directory_sync)
        self.assertLess(directory_sync, directory_close)
        self.assertLess(directory_close, cleanup)
        self.assertIn('private trainer manifest verification failed', pack)


    def test_trainer_witness_cannot_retain_page_or_corrupt_sprite_destination(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        witness = transfer.index("XgbaExpansionTrainerTransfer(id, dest, bytes);")
        post_residency = transfer.index("|| XgbaExpansionPageResidentBytes() != 0u", witness)
        post_release = transfer.index("XgbaExpansionPageRelease();", post_residency)
        post_hash = transfer.index("u32 witnessedHash = 2166136261u;", post_release)
        fail_closed = transfer.index("if (witnessedHash != destinationHash)", post_hash)
        success = transfer.index("return TRUE;", fail_closed)
        self.assertLess(witness, post_residency)
        self.assertLess(post_residency, post_release)
        self.assertLess(post_release, post_hash)
        self.assertLess(post_hash, fail_closed)
        self.assertLess(fail_closed, success)
        self.assertIn("if (!XgbaExpansionTryTrainerPic(", patched)


    def test_trainer_transfer_checks_lease_before_and_after_each_bounded_chunk(self):
        original = (self.root / "src/battle_gfx_sfx_util.c").read_text()
        patched = adapter.patched_battle_graphics(original)
        transfer = patched.split("static bool8 XgbaExpansionTryTrainerPic", 1)[1].split(
            "void DecompressTrainerFrontPic", 1)[0]
        loop = transfer.index("for (u32 offset = 0; offset < bytes; offset += 256u)")
        before = transfer.index("XgbaExpansionPageGeneration() != generation", loop)
        copy = transfer.index("CpuCopy32(page + offset, (u8 *)dest + offset, chunk);", before)
        after = transfer.index("XgbaExpansionPageGeneration() != generation", copy)
        verify = transfer.index("destinationHash = (destinationHash", after)
        self.assertLess(loop, before)
        self.assertLess(before, copy)
        self.assertLess(copy, after)
        self.assertLess(after, verify)
        self.assertIn("if (chunk > 256u)", transfer[loop:copy])
        self.assertIn("XgbaExpansionPageRelease();", transfer[before:copy])
        self.assertIn("XgbaExpansionPageRelease();", transfer[after:verify])
        self.assertIn("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)", patched)


    def test_private_trainer_provider_rejects_inherited_trainer_namespace(self):
        # A map/tileset base pack cannot inject arbitrary battle graphics,
        # including IDs outside the four source-verified trainer pictures.
        pack = (adapter.ROOT / "tools/xgba_expansion_trainer_pages.py").read_text()
        guard = pack.index('identifier.startswith("rhh.trainer.")')
        overlap = pack.index('or identifier in seen', guard)
        read = pack.index('handle.read(length)', overlap)
        publish = pack.index('with private_create(data) as handle:', read)
        self.assertLess(guard, overlap)
        self.assertLess(overlap, read)
        self.assertLess(read, publish)
        self.assertIn('raise SourceAssetError("invalid, overlapping or duplicate base resource")', pack)

    def test_original_trainer_loader_reports_attempts_before_provider_or_fallback(self):
        path = self.root / "src/battle_gfx_sfx_util.c"
        original = path.read_text()
        with adapter.patched_source(self.root, "firered"):
            patched = path.read_text()
        self.assertEqual(patched.count("XgbaExpansionTrainerAttempt(trainerPicId);"), 1)
        self.assertLess(patched.index("XgbaExpansionTrainerAttempt(trainerPicId);"),
                        patched.index("if (!XgbaExpansionTryTrainerPic(trainerPicId"))
        self.assertLess(patched.index("if (!XgbaExpansionTryTrainerPic(trainerPicId"),
                        patched.index("DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)"))
        self.assertEqual(path.read_text(), original)
        probe = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        self.assertIn("void XgbaExpansionTrainerAttempt(u32 id)", probe)
        self.assertLess(probe.index("battle_trainer_resident;"), probe.index("battle_attempt_count;"))

    def test_original_pokemon_loader_is_bridged_with_original_fallback_and_restores(self):
        path = self.root / "src/battle_gfx_sfx_util.c"
        original = path.read_text()
        with adapter.patched_source(self.root, "emerald"):
            patched = path.read_text()
        attempt = patched.index("XgbaExpansionMonAttempt(!IsOnPlayerSide(battler), species);")
        attempt_call = patched.index("if (!XgbaExpansionTryMonPic(!IsOnPlayerSide(battler),")
        original_call = patched.index("HandleLoadSpecialPokePic(!IsOnPlayerSide(battler),", attempt_call)
        note = patched.index("XgbaExpansionNoteMonFallback(!IsOnPlayerSide(battler), species,")
        palette = patched.index("paletteOffset = OBJ_PLTT_ID(battler);")
        self.assertLess(attempt, attempt_call)
        self.assertLess(attempt_call, original_call)
        self.assertLess(original_call, note)
        self.assertLess(note, palette)
        self.assertEqual(patched.count("XgbaExpansionTryMonPic("), 2)
        self.assertEqual(path.read_text(), original)
        bridge = (adapter.ROOT / "integration/expansion/xgba_expansion_pokemon_battle.inc").read_text()
        for fragment in ("XgbaExpansionPageRelease();", "offset += 256u",
                         "P_GBA_STYLE_SPECIES_GFX", "ShouldDrawSpotsOnSpecies",
                         "frontPicFemale", "XgbaExpansionPageGeneration()",
                         "(u32)page != leaseStart"):
            self.assertIn(fragment, bridge)
        self.assertNotIn("DecompressDataWithHeaderWram", bridge)

    def test_pokemon_loader_validation_fails_closed_on_drift_or_double_patch(self):
        path = self.root / "src/battle_gfx_sfx_util.c"
        original = path.read_text()
        path.write_text(original.replace("species, personalityValue);", "species, personalityValue, 0);"))
        with self.assertRaises(adapter.ExpansionDrift):
            adapter.validate_source(self.root, "emerald")
        path.write_text(original + "static bool8 XgbaExpansionTryMonPic(void);\n")
        with self.assertRaises(adapter.ExpansionDrift):
            adapter.validate_source(self.root, "emerald")

    def test_pokemon_proof_fields_match_native_blocks_and_acceptance(self):
        header = (adapter.ROOT / "integration/mgba/xgba_expansion_native.h").read_text()
        probe = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        acceptance = (adapter.ROOT / "tools/xgba_expansion_native_acceptance.py").read_text()
        fields = re.search(r"struct XgbaExpansionProof \{(.*?)\n\};", probe, re.S).group(1)
        names = re.findall(r"volatile u32 (\w+);", fields)
        suffixes = ["attempts", "attempt_species", "transfers", "transfer_species",
                    "transfer_bytes", "transfer_hash", "transfer_generation",
                    "transfer_resident", "fallback_count", "fallback_species",
                    "fallback_bytes", "fallback_hash", "sprite_ok", "sprite_species",
                    "sprite_tile", "palette_hash", "vram_frame", "sprite_live"]
        front = 4 * names.index("mon_front_attempts")
        back = 4 * names.index("mon_back_attempts")
        self.assertEqual(front, int(re.search(r"F=(\d+)", header).group(1)))
        self.assertEqual(back, int(re.search(r"B=(\d+)", header).group(1)))
        for side in ("front", "back"):
            start = names.index(f"mon_{side}_attempts")
            self.assertEqual(names[start:start + 18], [f"mon_{side}_{s}" for s in suffixes])
        self.assertEqual(names.index("mon_front_attempts"), names.index("battle_fallback_bytes") + 1)
        for word, suffix in re.findall(r"(\w+)=(\d+)", re.search(r"enum \{ F=.*?\};", header, re.S).group(0))[2:]:
            self.assertEqual(int(suffix), suffixes.index(self._native_suffix(word)))
        self.assertIn("PASS_XGBA_RHH_NATIVE_POKEMON_BATTLE", header)
        self.assertIn("PASS_XGBA_RHH_NATIVE_TRAINER_BATTLE", header)
        self.assertIn('"native_pokemon_battle_verified": trainer_battle', acceptance)
        self.assertIn('"native_trainer_battle_verified": trainer_battle', acceptance)
        self.assertIn("pokemon-battle", acceptance)
        trainer_body = header.split("xgba_expansion_native_trainer_battle(", 1)[1]
        self.assertIn("xgba_expansion_native_pokemon_battle(core,probe", trainer_body)

    @staticmethod
    def _native_suffix(word):
        return {"ATT": "attempts", "ATTS": "attempt_species", "TR": "transfers",
                "TRS": "transfer_species", "TRB": "transfer_bytes", "TRH": "transfer_hash",
                "TRG": "transfer_generation", "TRR": "transfer_resident",
                "FBC": "fallback_count", "FBS": "fallback_species", "FBB": "fallback_bytes",
                "FBH": "fallback_hash", "OK": "sprite_ok", "SPS": "sprite_species",
                "TILE": "sprite_tile", "PAL": "palette_hash", "FRAME": "vram_frame",
                "LIVE": "sprite_live"}[word]

    def test_native_trainer_battle_harness_is_guest_driven_and_offsets_match_proof(self):
        header = (adapter.ROOT / "integration/mgba/xgba_expansion_native.h").read_text()
        headless = (adapter.ROOT / "integration/mgba/xgba_mgba_headless.c").read_text()
        launcher = (adapter.ROOT / "tools/xgba_mgba_run.py").read_text()
        acceptance = (adapter.ROOT / "tools/xgba_expansion_native_acceptance.py").read_text()
        probe = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        body = header.split("xgba_expansion_native_trainer_battle(", 1)[1]
        for fragment in ("PASS_XGBA_RHH_NATIVE_TRAINER_BATTLE",
                         "never rendered an original trainer battle opponent sprite",
                         "resource->reads<=count", "disabled trainer battle used the external provider",
                         "xgba_expansion_source_hash(resource,id,2048u)",
                         "fallback_hash!=source_hash", "left the external page lease resident"):
            self.assertIn(fragment, body)
        self.assertNotIn("busWrite", body)
        fields = re.search(r"struct XgbaExpansionProof \{(.*?)\n\};", probe, re.S).group(1)
        names = re.findall(r"volatile u32 (\w+);", fields)
        for enum, name in (("RHH_TRAINER_COUNT", "battle_trainer_count"),
                           ("RHH_TRAINER_HASH", "battle_trainer_hash"),
                           ("RHH_TRAINER_RESIDENT", "battle_trainer_resident"),
                           ("RHH_TRAINER_ATTEMPTS", "battle_attempt_count"),
                           ("RHH_TRAINER_ATTEMPT_ID", "battle_attempt_last_id"),
                           ("RHH_PAGE_RESIDENT", "page_resident"),
                           ("RHH_BATTLE_FLOW", "battle_flow_state"),
                           ("RHH_BATTLE_OPPONENT", "battle_opponent_id"),
                           ("RHH_BATTLE_MAIN_FRAMES", "battle_main_frames"),
                           ("RHH_BATTLE_SPRITE_PIC", "battle_sprite_pic"),
                           ("RHH_BATTLE_SPRITE_ARRIVED", "battle_sprite_arrived"),
                           ("RHH_BATTLE_SPRITE_VISIBLE", "battle_sprite_visible"),
                           ("RHH_BATTLE_FALLBACK_COUNT", "battle_fallback_count"),
                           ("RHH_BATTLE_FALLBACK_HASH", "battle_fallback_hash"),
                           ("RHH_BATTLE_FALLBACK_ID", "battle_fallback_id"),
                           ("RHH_BATTLE_FALLBACK_BYTES", "battle_fallback_bytes")):
            offset = int(re.search(enum + r" = (\d+)", header).group(1))
            self.assertEqual(offset, 4 * names.index(name))
        self.assertEqual(int(re.search(r"RHH_TRAINER_PROOF_END = (\d+)", header).group(1)),
                         4 * len(names))
        self.assertIn("--expansion-trainer-battle", headless)
        inc = (adapter.ROOT / "integration/expansion/xgba_expansion_trainer_battle.inc").read_text()
        self.assertRegex(inc, r"#if IS_FRLG\s+#define XGBA_TRAINER_BATTLE_OPPONENT TRAINER_HIKER_MARCOS")
        self.assertIn('strcmp(target,"emerald")==0 ? 1u : 87u', body)
        self.assertIn("--expansion-trainer-battle", launcher)
        self.assertIn("trainer_battle=trainer_battle", acceptance.replace("expansion_", ""))
        self.assertIn("PASS_XGBA_RHH_NATIVE_TRAINER_BATTLE", acceptance)

    def test_trainer_battle_build_uses_original_start_and_restores_source(self):
        probe = (adapter.ROOT / "integration/expansion/xgba_expansion_probe.inc").read_text()
        header = adapter.ROOT / "integration/fire_red/xgba_guest.h"
        main = adapter.patched_main(MAIN, header, probe, overworld_play=True,
                                    trainer_battle=True)
        self.assertEqual(main.count("XgbaExpansionTrainerBattleWitness();"), 1)
        self.assertIn("BattleSetup_StartTrainerBattle();", main)
        self.assertIn("TRAINER_BATTLE_PARAM.opponentA = XGBA_TRAINER_BATTLE_OPPONENT;", main)
        self.assertNotIn("CreateSprite", main)
        plain = adapter.patched_main(MAIN, header, probe, overworld_play=True)
        self.assertNotIn("XgbaExpansionTrainerBattle", plain)
        with self.assertRaisesRegex(adapter.ExpansionDrift, "original field flow"):
            adapter.patched_main(MAIN, header, probe, trainer_battle=True)
        overworld = adapter.patched_overworld(OVERWORLD, trainer_battle=True)
        self.assertEqual(overworld.count("XgbaExpansionTrainerBattleTick();"), 1)
        self.assertLess(overworld.index("XgbaExpansionLiveTick(gMapHeader"),
                        overworld.index("XgbaExpansionTrainerBattleTick();\n"))
        self.assertNotIn("XgbaExpansionTrainerBattleTick", adapter.patched_overworld(OVERWORLD))
        for target in adapter.TARGETS:
            with self.subTest(target=target):
                before = {name: (self.root / name).read_text() for name in
                          ("src/main.c", "src/overworld.c", "src/battle_gfx_sfx_util.c")}
                with adapter.patched_source(self.root, target, trainer_battle=True):
                    self.assertIn("XgbaExpansionTrainerBattleTick();",
                                  (self.root / "src/overworld.c").read_text())
                    self.assertIn("XgbaExpansionTrainerBattleWitness();",
                                  (self.root / "src/main.c").read_text())
                for name, text in before.items():
                    self.assertEqual((self.root / name).read_text(), text)
        for kwargs in ({"map_smoke": True}, {"overworld_play": True}):
            with self.assertRaisesRegex(adapter.ExpansionDrift, "exclusive"):
                with adapter.patched_source(self.root, "emerald",
                                            trainer_battle=True, **kwargs):
                    pass

    def test_original_fallback_decompress_is_witnessed_after_original_call(self):
        patched = adapter.patched_battle_graphics(
            (self.root / "src/battle_gfx_sfx_util.c").read_text())
        call = patched.index("    DecompressDataWithHeaderWram(GetTrainerFrontPicData(trainerPicId)")
        note = patched.index("XgbaExpansionNoteTrainerFallback(trainerPicId")
        self.assertLess(call, note)
        self.assertGreater(call, patched.index("if (!XgbaExpansionTryTrainerPic(trainerPicId"))

    def test_trainer_battle_acceptance_is_exclusive_of_map_modes(self):
        acceptance = (adapter.ROOT / "tools/xgba_expansion_native_acceptance.py").read_text()
        guard = acceptance.index("if trainer_battle and (map_smoke or overworld_play):")
        self.assertIn("exclusive", acceptance[guard:guard + 200])
        self.assertLess(guard, acceptance.index("adapter.require_release_tag"))


if __name__ == "__main__":
    unittest.main()
