# Phase 1 — FireRed revision-10 linker and generated-symbol ABI (26 October 2026)

**Decision: `FAIL_INCOMPLETE`.** This checkpoint extends the v6 source-grounded review queue with the previously uncurated `pret/pokefirered/ld_script_rev10.ld` at pinned FireRed commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. It does **not** approve whole-file semantics, certify a compiled binary, or change any emulator/ROM architecture.

## Source-grounded findings

1. The pinned `config.mk` names `GAME_REVISION=10` builds `*_switch` (lines 41–48). The Makefile selects `ld_script_rev10.ld` only for **non-modern revision 10**, together with three separate generated symbol linker inputs: `sym_bss_rev10.ld`, `sym_common_rev10.ld` and `sym_ewram_rev10.ld` (Makefile lines 352–382). Modern builds use `ld_script_modern.ld` instead.
2. Original and revision-10 linker scripts have the same 11 named output sections and 32 MiB native ROM *linker region* (0x08000000, 32 MiB). They do **not** have identical ordered object placement. In revision 10, `librfu_stwi.o` and `librfu_rfu.o` move from `lib_text` into `.text`; `librfu_rfu.o` moves from `lib_rodata` into `.rodata`. The retained `librfu_intr.o` and `librfu_sio32id.o` entries also exchange relative order within `lib_text`. These are **linker source ordering differences**, not yet proven compiled address changes.
3. Revision-10 `sym_bss_rev10.txt` adds two RFU object inputs relative to `sym_bss.txt`. `sym_common_rev10.txt` adds `union_room.o` and changes RFU-related include/alignment ordering relative to `sym_common.txt`. The two EWRAM symbol-input text files have identical pinned Git blobs. Generated linker fragments and resulting RAM symbol addresses still require compilation and examination.
4. The modern linker uses wildcard object/section aggregation rather than the original/revision-10 explicit ordering. Its layout cannot be inferred from either non-modern variant.
5. The Makefile's `--pad-to 0x9000000` binary-output rule is a separate 16 MiB output-padding boundary, **not** an expansion of the GBA's native executable address space or proof of unlimited ROM capacity.

## Reproducible evidence and review status

`tools/phase1_rev10_linker_semantics.py` verifies **11 exact pinned Git blobs**, the pinned revision, bounded Makefile/config/linker source expressions, and **10 typed cross-file dependency endpoints**. It generates a full ordered diff of the original and revision-10 linker source files and the three paired generated-symbol input files, preserving line ranges and exact changed text in `audit-output/rev10_linker_semantic_index_v7.json`. It rejects unexpected section membership or order drift and executes **9 additional fail-closed negative controls**.

The v7 queue preserves the original **14,834 source identities**, **338 P0 priorities**, **29 original curated candidates**, and all earlier machine-review statuses. It advances the pending source-grounded candidate count from **40 to 41**, with **zero independent whole-file approvals**. All source interpretations are explicitly marked `PINNED_SOURCE_INTERPRETATION_ONLY`.

## Unresolved Phase 1 gates

Compiled original/revision-10/modern ELF symbol and relocation comparisons, RAM placement and lifetime, real ROM hashes, editor import/export preservation, cross-emulator behaviour, and authenticated independent whole-file dispositions remain outstanding. CI success for this packet verifies pinned-source consistency and deterministic queue provenance only. **Phase 2 remains blocked.**
