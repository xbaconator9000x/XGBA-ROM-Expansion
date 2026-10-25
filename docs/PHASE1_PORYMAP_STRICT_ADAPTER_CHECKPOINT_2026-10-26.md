# Phase 1 P0 editor map-block strictness checkpoint — 2026-10-26

**Gate:** FAIL_INCOMPLETE. No independent whole-file semantic signoffs, Qt editor round-trip proof, or XGBA expansion implementation.

## Pinned semantic basis

The pinned Porymap sources `src/core/block.cpp` (Git blob `fc4fe774ccd75673c549734055907eb7c79c0fc2`), `src/core/bitpacker.cpp` (`34f86b4e3910021613a1d090746ae53a1c6782a2`) and `src/core/blockdata.cpp` (`5fcd4e32b115790f5a86b5cef5726cace8005017`) establish the packed three-field, 16-bit metatile/collision/elevation record. The repository's `docs/PHASE1_P0_PORYMAP_PORYSCRIPT_AUTHORING_ABI_2026-10-26.md` records its source-anchored lossy-export hazards.

## Reproduced code-path defect in our reference adapter

Previously, `strict_encode(fields, masks)` iterated `zip(fields,masks)` without requiring exactly three fields. An extra field would be silently ignored; fewer fields would be silently filled by zero bits. Python `bool` also passed `isinstance(x,int)`, so boolean field and mask inputs could masquerade as integer semantic values. The decoder accepted boolean/fractional block counts in some cases. These are **adapter input validation defects**, not evidence of defects in Porymap itself.

## Bounded corrections and regression controls

- Commit `53664e4611a758e4ac40a631577f9fc962a586f0` requires exactly three fields, exact integer types for fields and masks, integer block count, and binary stream input. Seven negative controls supplement the ten existing overflow/shape fixtures; the 65,536 native 16-bit word round-trip test is unchanged.
- Commit `c4d28e7366ee4dd718b4de1323db24affa0b888c` adds `tools/porymap_block_semantic_reference.py` to the compiled Porymap workflow path triggers, so future edits to the reference model cannot silently avoid its existing pinned Qt/source-backed CI integration.
- [Resulting compiled Porymap workflow](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40209978387) was **queued** at initial verification. Do not infer success until it completes; inspect the resulting job logs if it fails.

**Scope limitation:** A strict Python reference-model pass verifies only the declared encoding contract. It does not prove compiled Porymap Qt project import/export, script label reconstruction, runtime remapping, or whole-file semantic approval.
