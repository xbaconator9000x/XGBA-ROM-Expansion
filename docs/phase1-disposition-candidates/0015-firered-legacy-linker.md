# Candidate 0015 — FireRed legacy revision-0 linker script

**State: analyst-prepared whole-file candidate; PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** File was read at the exact pinned upstream commit, including all output-section selectors and debug/discard directives. Neither passing CI nor this analyst record is independent semantic approval.

## Exact source identity
- Repository: `pret/pokefirered`; upstream commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Exact whole-file path: `ld_script.ld`; Git blob SHA verified by direct pinned GitHub file fetch: `9a4b45031e93c1e1da8186d8c697332710526048`.
- [Immutable upstream source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/ld_script.ld); [pinned linker-variant source checker](../../tools/phase1_firered_linker_variant_contract.py); [source evidence](../PHASE1_P0_FIRERED_LINKER_VARIANTS_2026-10-26.md).

## Whole-file allocation and output-section inventory
- Script-level assignments `gNumMusicPlayers = 4`, `gMaxLines = 0`.
- `MEMORY`: EWRAM `0x02000000`/256 KiB, IWRAM `0x03000000`/32 KiB, ROM `0x08000000`/32 MiB. These are **native linker bounds**, not runtime proof or an XGBA extension.
- `ewram` and `iwram` are `NOLOAD` sections, aligned to 4 bytes, with `gHeap` and explicit `0x1C000` location-counter movement in EWRAM; IWRAM collects source/data BSS, m4a BSS code, COMMON, libc sbrk COMMON, and defines `end`. The fixed location counter must not be assumed to equal a checked heap size or all runtime initialized bytes.
- ROM output sections, in authored order: `.text`, `script_data`, `lib_text`, `.rodata`, `song_data`, `lib_rodata`, `multiboot_data`, `gfx_data` at **`0x08D00000`**, and `extra`. The `gfx_data` location is 13 MiB beyond the ROM origin, within the declared 32 MiB region.
- `.text` explicitly enumerates gameplay and engine objects (including ROM header, crt0 and main at its beginning). `script_data` collects seven named script objects; `lib_text` collects library objects. `.rodata` and `lib_rodata` explicitly order their input objects, while `song_data` enumerates music objects. `multiboot_data` collects three named objects; `gfx_data` collects `src/graphics.o(.rodata)` at the fixed address; `extra` catches remaining `src/*.o(.text)`, `src/*.o(.rodata)` and `data/*.o(.rodata)`. All these ROM sections use 4-byte alignment and ROM placement with `=0` fill, subject to actual linker output.
- The file concludes with explicit zero-address DWARF/debug output sections and `/DISCARD/ : { *(*) }`. Unmatched input sections can therefore be discarded; not every new asset or metadata section will be automatically retained.

## Cross-file and expansion relevance
- Selected by build revision and `MODERN` logic in the pinned `Makefile`/`config.mk`; the modern variant is a **different linker script**. Its section addresses, object ordering and initialized-data treatment must not be inferred from this legacy script.
- The ROM entry depends on `src/rom_header.s` and `src/crt0.s`; the RAM handler copy in `src/main.c` depends on actual linked ROM and IWRAM addresses. Build scripts, symbol-include files, object inputs and `gbafix`/`objcopy` are additional producers/consumers, not certified here.
- Future resource relocation must preserve or explicitly adapt input-object ordering, linker placement, ROM pointer references, RAM lifetime, script/music/graphics sections and the catch-all/discard rules. None is an implemented expansion feature.

## Open reviewer obligations
Independent reviewer must (1) verify the complete file and every explicit object entry, not only the summarized section families; (2) resolve all referenced object and symbol-include files and prove variant selection; (3) compare actual pinned compiled ELF map, VMA/LMA, sections and final ROM bytes; (4) establish link-time overlap/overflow and debug/discard behavior; (5) test representative editor/emulator consumer assumptions before any runtime claim. The source checker and its negative controls are **supporting evidence**, not independent whole-file review.

**Independent reviewer/verdict/date: not supplied. Gate contribution: 0. Authoritative state: FAIL_INCOMPLETE, 0/14,834 approvals.**

## Revision-specific dispositions
- This is the **non-modern, non-revision-10** legacy linker variant. It includes `sym_ewram.ld`, `sym_bss.ld`, and `sym_common.ld`, each a separate file whose expansion-sensitive symbol placements must be reviewed independently.
- Complete-file selector comparison against pinned `ld_script_rev10.ld`: the revision-0 file places `src/librfu_stwi.o(.text)` and `src/librfu_rfu.o(.text)` in **`lib_text`**, and `src/librfu_rfu.o(.rodata)` in **`lib_rodata`**; revision 10 moves these inputs into `.text`/`.rodata`. These are section-membership differences, **not** a claim of exact symbol address changes without compiled evidence.
- The revision-0 script additionally contains DWARF 1 sections `.debug`, `.line`, `.debug_srcinfo`, `.debug_sfnames`, and a `.debug_info` selector including `.gnu.linkonce.wi.*`; the revision-10 script's debug list differs.

## Pending verdict
**PENDING_INDEPENDENT_REVIEW; not approved.**
