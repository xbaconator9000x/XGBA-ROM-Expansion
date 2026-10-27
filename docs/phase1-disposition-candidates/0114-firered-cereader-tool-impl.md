# Candidate 0114 — complete pinned FireRed Trainer Tower CE-reader implementation

**Review preparation only — pending independent review, not approved.**

- Identity: pret/pokefirered:src/cereader_tool.c
- Pinned upstream commit: ce6406d8c2eaf46d543c8a2606de0c3cb1951982
- Git blob SHA-1: 395be0bcbed8454e645a9f5670cde3024eda508e
- Complete-file scope: **all 97 nonempty-or-code/comment source lines (file has 97 lines plus terminal newline)**, including includes, macros, static assertion, both public save/load wrappers, validators and stub. No excerpt is treated as whole-file proof.
- Source: https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/cereader_tool.c

## Exhaustive source region inventory

| Lines | Source element | Semantic disposition and dependencies |
| --- | --- | --- |
| 1–5 | Includes global, gflib, util, save and cereader_tool | Types, allocator, flash helper and byte-sum dependencies |
| 7–11 | SEC30_SIZE/SEC31_SIZE and STATIC_ASSERT | Split at floors[4]; combined payload bound only, not per-half runtime flash test |
| 13–16 | GetTrainerHillUnkVal | Increment and truncate/wrap to u8; reads relocated SaveBlock1 trainerTower[0].unk9 |
| 18–27 | ValidateTrainerTowerTrainer | Checks floorIdx 1–8, challengeType <= knockout and per-floor additive checksum; does not enforce floor uniqueness |
| 29–43 | ValidateTrainerTowerData | Checks numFloors 1–8, loops only active floor prefix, and compares sum of active floor bytes; excludes set header and inactive tail |
| 45–60 | CEReaderTool_SaveTrainerTower_r | Assertions on id/dummy, zeroed buffers, first-half byte-1 mutation, sequential special-sector writes and early failure |
| 62–68 | CEReaderTool_SaveTrainerTower | AllocZeroed(SECTOR_SIZE), delegates, frees, returns result; allocator failure path requires separate tracing |
| 70–83 | CEReaderTool_LoadTrainerTower_r | Both special-sector reads required; two memcpy operations; validates only after both; failed validation returns FALSE |
| 85–91 | CEReaderTool_LoadTrainerTower | AllocZeroed, delegates, frees and returns success |
| 93–97 | ReadTrainerTowerAndValidate | Stub returns FALSE, explicitly not a working Emerald-style e-reader import |

## Dependency closure and review questions

Native producers/consumers: include/cereader_tool.h, include/constants/trainer_tower.h, src/save.c, include/save.h, src/util.c, trainer-tower gameplay consumers, gSaveBlock1Ptr and gflib allocation helpers. External boundaries: flash physical sectors 30/31, raw mGBA FLASH1M file, compiler struct layout, original agbcc, editor/sidecar round trips. The [active-prefix dossier](../PHASE1_P0_FIRERED_TOWER_PREFIX_INTEGRITY_2026-10-27.md) records source-proven preconditions and deterministic synthetic counterexamples.

**Negative evidence:** no complete native emulator or hardware execution of malformed sectors; no original agbcc linked-ROM comparison; no tested atomic recovery across a failed second-sector write; no demonstration that inactive-floor bytes are used by gameplay; no independent signoff. The source checker checks exact blobs and selected anchors but does **not** itself verify exhaustive whole-file semantics. This document is an analyst-prepared whole-file candidate for later external review, not a disposition approval.

**Phase 1: FAIL_INCOMPLETE. Independent approvals added: 0. Phase 2: untouched.**
