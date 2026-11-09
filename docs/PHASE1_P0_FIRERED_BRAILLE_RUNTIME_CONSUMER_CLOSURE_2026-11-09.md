# Phase 1 P0 — FireRed Braille runtime-consumer closure

**9 November 2026 · SOURCE-ONLY WHOLE-FILE READ · NON-APPROVING HANDOFF.** Prepared on existing PR #7 from starting head `97ffc7fd5eb06e0cd5b71402f2e9e9ea9b9d4f1e`, following the PR #8 system-batch review protocol. The machine-readable per-file handoff is [`phase1-review-readiness/firered-braille-runtime-consumer-handoff-20261109.json`](phase1-review-readiness/firered-braille-runtime-consumer-handoff-20261109.json).

Phase 1 remains `FAIL_INCOMPLETE`; independent whole-file approvals remain `0/14,834`. This handoff is not an independent receipt, does not alter any approval register or gate, and makes no Phase 2 claim.

## Packet and assignment reconciliation

The pinned PR #8 packet `packet-0200-0299.json` (Git blob `c998c2ea8c887968e586b1792c5207ecb5286839`, SHA-256 `fde3a0dbf9f8b5cf19bc2591d81508f9dc9084e4d62d57d1ead8835b744f6586`) enumerates FireRed P0 source indices 260–294:

- **260–292:** 33 `data/maps/*/scripts.inc` files. They are authored map-script inputs overlapping Poryscript/map-script ABI assignments on PRs #16, #20 and #36. They are not new whole-file dispositions here.
- **293:** `src/agb_flash.c`, assigned to PR #10’s flash-sector work.
- **294:** `src/braille_text.c`, the only distinct, unassigned FireRed C source in this range. Its exact source identity and original dossier/archive provenance are recorded in the JSON handoff.

The PR #8 second-packet indices 112–127/129 are mGBA translation/SQLite entries, not FireRed, and are excluded. Indices 295–298 are already covered by the prior runtime-consumer handoff; index 299 (`src/load_save.c`) belongs to the existing save-reload closure. No overlapping scripts or flash work is repeated. The requested range supports one truthful package, not two or three distinct FireRed source packages.

## One bounded package: Braille renderer, script entry and generated font

`src/braille_text.c` was read in full (212 lines). Its pinned source identity is FireRed blob `d4afdf87f19a5b3345dd561d0cd1360683b30a6a`, SHA-256 `def45ae49f0e1666908c39e5ddd0f63f57cf834d8e23e779cb756e5e9b161c03`. The packet’s source dossier hash is `dcda24274c44df7a6d4ed2e984667b1ddf2f7b3349b7d9b9a572edcdc26a56e9`; the matching original archive row including its newline hashes to `56061998283611826e1ced1922b932d8a8d40d4ad597348648aedc22483bb134`. The compressed original dossier archive SHA-256 is `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.

The dependency trace is intentionally bounded:

1. `src/scrcmd.c:1558–1567` implements `ScrCmd_braillemessage`; `data/script_cmd_table.inc:124` maps opcode `0x78` to it, and `asm/macros/event.inc:972` defines the authored macro. The handler passes its selected message pointer to `AddTextPrinterParameterized` with `FONT_BRAILLE` and fixed speed `0`. `include/text.h` declares `FontFunc_Braille` and `GetGlyphWidth_Braille`; `src/new_menu_helpers.c:121–125` installs the renderer for `FONT_BRAILLE`; `src/text.c:46–50` installs its width reader. These are targeted call/declaration excerpts, not new whole-file dispositions.
2. `graphics_file_rules.mk:81–82` generates `graphics/fonts/braille.fwjpnfont` from `graphics/fonts/braille.png` through `$(GFX)`. The pinned PNG is 256×64 with a 2-bit colormap, corresponding geometrically to 64 16×16 cells. The actual generated `.fwjpnfont` output, decompression input extent and authored glyph-ID domain were not built or verified.
3. The scroll-speed table has three entries for slow/mid/fast values 0/1/2, with deltas 1/2/4 (`src/braille_text.c:10–14`). In the scroll state it indexes that table from `gSaveBlock2Ptr->optionsTextSpeed` at lines 165, 172 and 173 without a local bounds check. The pinned `SaveBlock2` field is 3 bits (`include/global.h:338`), so values 3–7 are representable in that field even though `include/constants/global.h:99–101` names only values 0–2.
4. `src/new_game.c:60–63` initializes the option to mid. `src/option_menu.c:209,216–219` normalizes an out-of-range menu copy to zero, then writes the option back on close at line 513. `GetTextSpeedSetting` clamps an invalid option to mid (`src/new_menu_helpers.c:658–663`) when called. Those paths do not establish that the clamp precedes every Braille scroll: the Braille script handler passes a fixed speed and does not call `GetTextSpeedSetting`. Save deserialization, all script ordering and malformed-save reachability remain outside this package.
5. `DecompressGlyph_Braille` computes its pointer from `glyph` at line 200 and performs four tile decompressions at lines 201–204 without a local glyph-range check. The PNG’s nominal grid alone does not prove that every authored message stays within the generated asset’s valid glyph domain.

The local source-backed objection is conditional: if the Braille scroll state is reached with `optionsTextSpeed == 3`, the indexed table read is out of bounds. A temporary GCC 13.3 host harness compiled the unchanged pinned source body with stubbed headers and renderer functions under ASan/UBSan. Valid values 0–2 produced the expected scroll deltas and state changes. The value-3 fault control produced an ASan/UBSan bounds diagnostic at line 165; a temporary source mutation fixing the index to mid removed that diagnostic. The mutation was only a harness sensitivity control and was not applied to repository source. This does **not** show that an ordinary saved game or stock gameplay reaches value 3, and the stubbed host harness does not establish GBA ABI, generated-font behavior, ARM execution or emulator behavior.

## Evidence boundary and disposition

Supporting files in the JSON record are identified by pinned blob/SHA-256 and explicitly marked as targeted excerpts or partial closure; the only whole-file read newly counted here is `src/braille_text.c`. No native toolchain (`arm-none-eabi-gcc`, `arm-none-eabi-as`, agbcc), GBA emulator or generated font output was available. No ARM build, linked-ROM validation, save-integrity test, editor round trip or emulator test was performed. The source-level host witness is not CI evidence. The exact-head PR and push Actions status is checked separately after delivery; no prior run is reused as proof.

The pinned upstream root listing has no `LICENSE` file, and the pinned README does not establish a license for these files. Licensing remains pending; no source text or asset content is reproduced in this handoff.

**Disposition:** `NON_APPROVING_HANDOFF`; independent verdict `NEEDS_REVIEW`; no `COPILOT_REVIEWED/PASSED` or historical `APPROVED` receipt; no Phase 2 credit.
