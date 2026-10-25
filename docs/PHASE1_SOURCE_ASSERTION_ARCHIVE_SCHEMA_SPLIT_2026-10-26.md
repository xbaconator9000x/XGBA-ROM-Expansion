# Phase 1 source assertion packaging contract — baseline + additive P0

**2026-10-26. Decision: `FAIL_INCOMPLETE`.** Source-anchored assertions are *not* independent whole-file semantic signoffs.

## Problem encountered and correction

The historical [Phase 1 archival workflow](../.github/workflows/archive-semantic-evidence.yml) validates `audit-output/source_contract_assertions.json` using **exactly 25 passing source checks**. Its successful census can consequently fail at the permanent archive stage if this original JSON is silently extended in place. Two release packaging attempts failed with `Source check count changed` while the underlying expanded source census succeeded.

**Resolved by explicit versioned additive evidence, not weakening tests:** `tools/verify_source_contracts.py` retains its original 25-case CHECKS list and its exact output schema. It then runs `tools/verify_p0_additive_source_contracts.py`, which verifies **16 additional independently named pinned source contracts** and writes `audit-output/p0_additive_source_contract_assertions.json`. All 41 assertions must pass in the Phase 1 census. The legacy archival workflow continues to check its original 25 and archives the *entire* `audit-output` directory including the additive file. No existing approval or completion gate is loosened.

This change preserves compatibility with the historical automatic release workflow, and lets future source-grounded analysis grow as an explicitly revisioned contract family. Future new checks belong in a new additive suite or a formally migrated archive schema, never under an unversioned changed base count.

## Supplemental P0 semantics, pending peer and runtime review

| Domain | Source-backed meaning |
| --- | --- |
| FireRed map grid | 16-bit `10/2/4` metatile, collision and elevation encoding; 0x2800-cell virtual backup grid |
| FireRed render attributes | Metatile layer type is in **separate 32-bit metatile attributes**, not in the collision bits |
| FireRed saved view | Legacy array has 256 `u16` slots, non-`UBFIX` reader scans 512; modern source configuration enables `UBFIX` |
| FireRed script interpreter | 20-address return stack, 19 successful pushes, ignored `ScriptPush` failure in `ScriptCall` |
| Porymap serialization | Native `u16` little-endian block records and configurable default masks |
| Editor versus runtime writes | Porymap `setMetatileId` preserves collision+elevation; FireRed runtime `MapGridSetMetatileIdAt` replaces collision, preserving elevation; script setter optionally forces impassability |

### Required independent validation

- Check [Phase 1 census CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/workflows/phase1-census.yml) and confirm `source_contract_assertions.json` counts remain exactly 25, while `p0_additive_source_contract_assertions.json` records 16 passed. **Do not claim both tested until the resulting runner confirms.**
- Check subsequent archive workflow and artifact checksum, because successful census does not imply permanent archive succeeded.
- Obtain whole-file semantic review and compiled behavior test evidence before approving any candidate disposition.
- Preserve both JSON families, including their source-hash and line anchors, with matching original Git revisions.

**Phase 1 remains incomplete; none of these additional 16 source assertions certifies a fully compatible XGBA engine, arbitrary ROM import, or complete per-file semantic mapping.**
