# Phase 1 whole-file analyst candidate 0010 — FireRed modern linker script

**State: PENDING_INDEPENDENT_REVIEW.** Candidate preparation only; not an independent whole-file approval or authoritative gate input.

## Pinned identity and scope
- Repository: `pret/pokefirered`; commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Whole file: `ld_script_modern.ld`; Git blob: `e930243522bd21da40cc1a05de9a42b8ad409b46` (verified directly at pinned GitHub ref).
- [Full immutable source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/ld_script_modern.ld); [five-blob linker-variant evidence](../PHASE1_P0_FIRERED_LINKER_VARIANTS_2026-10-26.md).
- The entire ~2.1 KB linker script was inspected, including every output section, wildcard and discard rule.

## Whole-file semantic disposition candidate
1. **Top-level symbols:** `gNumMusicPlayers = 4`, `gMaxLines = 0`. These are link-time symbol assignments, not C storage allocations or runtime writes.
2. **MEMORY:** `EWRAM (rwx)` origin `0x02000000`, length `256K`; `IWRAM (rwx)` origin `0x03000000`, length `32K`; `ROM (rx)` origin `0x08000000`, length `32M`. A declared ROM region is not an expansion mechanism or evidence of a physical aperture.
3. **`ewram` output section:** fixed `0x02000000`, `NOLOAD`, `ALIGN(4)`, destination EWRAM. Assigns `gHeap = .` at section start, then sets section-relative location counter `. = 0x1C000`, then collects `*(ewram_data)`. A heap symbol does not establish heap capacity or safe runtime use.
4. **`iwram` output section:** fixed `0x03000000`, `NOLOAD`, `ALIGN(4)`, destination IWRAM. Collects `*(.bss*)`, then `src/m4a.o(.bss.code)`, then `*(COMMON)` and `*(common_data)`; assigns both `end = .` and `__end__ = .`. The source comments suggest `.bss.code` at `0x03001AA8` and COMMON at `0x030022A8`, but those comments are not a compiled address proof. Section order, wildcard reach and reserved upper IWRAM must be checked in ELF.
5. **ROM placement:** sets location counter to `0x08000000`; `.text` output is aligned to four bytes and selects `src/rom_header.o(.text*)`, `src/rom_header_gf.o(.text.*)`, `src/crt0.o(.text)`, `src/main.o(.text)`, then all remaining `*(.text*)`. Destination ROM with `=0` fill. This ordering matters for the reset vector and header; it does not by itself prove final byte addresses.
6. **Other ROM outputs:** `script_data` collects `*(script_data)`; `.data` collects `*(.data*)`; `.rodata` collects `*(.rodata*)`. Each uses four-byte alignment, ROM destination and `=0` fill. The modern `.data` name does **not** imply EWRAM initialization or a conventional RAM copy.
7. **Non-ROM debug outputs:** DWARF `.debug`, `.line`, `.debug_srcinfo`, `.debug_sfnames`, `.debug_aranges`, `.debug_pubnames`, `.debug_info` (including `.gnu.linkonce.wi.*`), `.debug_abbrev`, `.debug_line`, `.debug_frame`, `.debug_str`, `.debug_loc`, `.debug_macinfo`, and DWARF 5 `.debug_line_str` are explicitly placed at section-relative address zero, not in the ROM region.
8. **Terminal `/DISCARD/`:** catches `*(*)` not previously consumed. This is a material compatibility boundary: newly introduced input sections may be silently discarded unless linker coverage is amended. It is not a claim that all orphan-section behaviour is tested.

## Dependency and interoperability assessment
- Producer: pinned build `Makefile` and `config.mk` select the modern linker variant; compiler emits input sections, GNU linker consumes this script; `gbafix` and `objcopy` transform linked output. Other two pinned linker scripts differ in explicit legacy section inventories and fixed `gfx_data` placement.
- Consumers: ROM boot/header, startup RAM initialization, script/data pointers and linker-symbol users; exact symbol-consumer census remains for independent review.
- XGBA implication: a future adapter must distinguish ROM `VMA/LMA`, RAM `NOLOAD`, section wildcards, debug outputs and discarded sections. Do not infer unlimited addressing, resource relocatability, ROM header safety, runtime initialization or emulation support from this linker script.

## Evidence and reviewer obligations
- **Verified here:** pinned full source and Git blob; all top-level symbols, region declarations, output sections, input selectors, alignment/fill and discard/debug rules.
- **Supporting evidence:** pinned five-blob linker variant checker (20 negative controls) and separate compiled ABI workflows; consult the actual exact-head CI artifacts before citing compiled claims.
- **Still open:** compare all input object section names with actual link map and ELF section/program headers; ensure intended data isn't discarded; verify `gHeap` and `end` consumers; test ROM image bytes, header, RAM lifetime, emulator fetch and editor/patcher round trips; independent whole-file reviewer verdict.
- Reviewer identity/date/verdict: **not provided / pending**. No fabricated signoff.

**Authoritative gate: FAIL_INCOMPLETE, 0/14,834 independently approved.**
