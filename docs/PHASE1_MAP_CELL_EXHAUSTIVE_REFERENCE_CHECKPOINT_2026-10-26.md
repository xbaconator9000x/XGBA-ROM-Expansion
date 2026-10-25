# Phase 1 P0 map-cell mutation arithmetic — exhaustive reference checkpoint (26 October 2026)

**Gate: FAIL_INCOMPLETE. Independently approved whole-file dispositions: 0/14,834.** No ROM expansion or compiled map-edit runtime certification is claimed.

## Verified preceding evidence

[Phase 1 census run 40237580499](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40237580499) completed successfully. The actual census job log (job 121302322404) reports **ten curated negative guards PASS**, **29/29 exact source Git blobs PASS**, **zero independent signoffs**, and the explicit `"decision": "FAIL_INCOMPLETE"`. This verifies the ten-guard revision from the preceding checkpoint, not the new map-cell test added below.

## Source-backed semantic gap and bounded addition

The pinned [map-cell write operation interpretation](PHASE1_P0_MAP_CELL_WRITE_OPERATION_SEMANTICS_2026-10-26.md) distinguishes Porymap `Layout::setMetatileId`, FireRed `MapGridSetMetatileIdAt`, `MapGridSetMetatileEntryAt`, `MapGridSetMetatileImpassabilityAt`, and both `ScrCmd_setmetatile` branches. Their exact source expressions and Git blob hashes were already checked by the existing 16 additive P0 source assertions in `tools/verify_p0_additive_source_contracts.py`, invoked by `tools/verify_source_contracts.py` in the pinned census workflow.

Commit `1d7823acd0f4817b34b4e8946ce047f79c4e9371` adds `verify_map_cell_word_reference()` to that existing source-pinned verification path. It models **all 65,536 possible native 16-bit input cell words**, comparing **seven distinct write/branch operations per word** against independently reconstructed metatile-ID, collision and elevation field expectations: **458,752 arithmetic comparisons**. The test covers all four collision states and all sixteen elevation states and retains a worked regression example: original `0x5809` → editor `0x580A`, runtime ID `0x500A`, script forced impassable `0x5C0A`. Its machine-readable evidence is added to `audit-output/p0_additive_source_contract_assertions.json` without changing the historical 25-check baseline or the 16 additive source assertions.

The reference function was separately exercised in a local Python interpreter and returned all 458,752 successful comparisons. The committed code was not yet independently confirmed in a post-change GitHub Actions run at checkpoint creation.

## Explicit limits

This is **source-backed arithmetic model coverage**, not an editor Qt round trip or a compiled FireRed ROM test. It does **not** test out-of-bounds coordinates, map persistence/reload, event interactions, custom block masks, pointer lifetimes or XGBA bank remapping. No semantic approval is inferred. The full Phase 1 gate remains authoritative.
