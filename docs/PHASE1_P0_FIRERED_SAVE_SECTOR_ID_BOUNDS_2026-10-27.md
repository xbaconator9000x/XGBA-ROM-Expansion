# Phase 1 P0 — FireRed main-save sector ID bounds before checksum validation

**27 October 2026.** Pinned source: [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982). **Phase 1 FAIL_INCOMPLETE.** This is a source trace and host-C sanitizer fixture, **not** an ARM/agbcc binary, mGBA run, power-loss test, or demonstrated user-visible vulnerability.

## Producer/consumer boundary

| Source | Git blob | Relevant contract |
| --- | --- | --- |
| `src/save.c` | `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c` | `GetSaveValidStatus` lines 466–582, `CopySaveSlotData` lines 440–464, `TryLoadSaveSlot` lines 423–438, `LoadGameSave` lines 803–832 |
| `include/save.h` | `87fb9b615b434b58823d15688056695acda9feab` | 14 sectors per slot, 2 slots, 16-bit physical sector ID, 32-bit signature, checksum, counter, 4096-byte physical sector |

The ordinary save path is `LoadGameSave(SAVE_NORMAL)` → `TryLoadSaveSlot(FULL_SAVE_SLOT, gRamSaveSectorLocations)` → `GetSaveValidStatus(locations)` → `CopySaveSlotData(FULL_SAVE_SLOT, locations)`. The validity pass reads 14 physical sectors per slot and checks the signature, then uses the **untrusted on-flash `id` as an index into `locations[]` before checking that it is less than 14**. Both loops subsequently use `1 << id` for the sector bitmap. Neither branch has a local `id < NUM_SECTORS_PER_SLOT` guard.

The copy pass likewise reads the untrusted ID and evaluates `locations[id].size` **before** checking signature/checksum. This means even a sector with an invalid signature can reach the unchecked index on the copy path. A 16-bit ID of 14 is one past the 14-entry location table. This is a C bounds/undefined-behaviour concern for malformed save data, not evidence that ordinary, correctly produced saves contain such IDs.

**Important reachability distinction:** `TryLoadSaveSlot` calls `CopySaveSlotData` after `GetSaveValidStatus` without conditioning the copy on `SAVE_STATUS_OK`. Thus rejecting a damaged slot during status evaluation does not by itself establish that its sector IDs are never subsequently consumed. The exact outcome of a malformed sector under the original ARM binary, GBA memory layout, and mGBA emulation remains untested.

## Reproducible, fail-closed host witness

[Source-locked checker](../tools/phase1_firered_save_id_bounds.py) verifies the two Git blobs and exact commit, extracts the **unchanged** `CopySaveSlotData` and `GetSaveValidStatus` C function definitions, verifies six source anchors, and exercises two source-removal negative controls. A Clang host harness mocks flash sector reads and returns a zero checksum for zeroed payloads. It tests two valid 14-sector slots and malformed `id=14` fixtures separately for the validation and copy paths. The copy-path malformed fixture deliberately has a bad signature, testing the order of operations. Host `-fsanitize=address,undefined` is expected to reject the malformed cases; the script fails if valid controls fail or malformed cases lack a sanitizer diagnostic. JSON evidence records exit codes, source provenance and limitations.

Run on a checkout of the **exact pinned FireRed commit**:

```bash
python3 tools/phase1_firered_save_id_bounds.py --source-dir pinned-firered --cc clang --out evidence/save-sector-id-bounds.json
```

[Dedicated CI workflow](../.github/workflows/phase1-firered-save-id-bounds.yml) checks out immutable upstream source, runs the witness and retains its JSON artifact. **CI is not considered passing until the workflow completes at the exact latest PR head.** An expected sanitizer diagnostic is an intentionally passing *negative* test, not evidence of a crash in the original game.

## Unresolved boundaries and negative evidence

- The host model is not compiled with agbcc and does not use the original FireRed link layout or a real flash controller.
- No emulator/hardware boot, malformed `.sav` import, full native recovery or second-slot rollback has been demonstrated.
- The host fixture cannot establish arbitrary memory read/write impact, exploitability, or actual gameplay crashes.
- Slot counter rollover, mixed-generation sectors, duplicate IDs, malformed signatures, short writes, sector-count shifts and sidecar binding still require independent tests.
- mGBA's 128 KiB FLASH1M import, save-type detection and savestate paths require separate cross-tool evidence; Qt/Porymap and Poryscript compatibility are not covered here.
- A prior [save/sidecar contract](SAVE_SECTOR_AND_SIDECAR_SEMANTICS_v25.md) already listed out-of-range sector IDs as an untested obligation. This witness **does not count that file again** and does not grant an independent review.

**Accounting:** 0 new unique machine-indexed files (the two source identities were already inventoried), 0 newly prepared whole-file reviews, 0 independent approvals, **1,000 short of the per-run target because the established untriaged pool is exhausted**. No Phase 2 implementation; all Phase 1 gates remain **FAIL_INCOMPLETE**.

## Follow-on dependency: per-sector save-counter coherence

The same pinned `GetSaveValidStatus` loop overwrites `slot1saveCounter` or `slot2saveCounter` whenever an individual sector passes signature/checksum validation. It does **not** require all 14 sectors in a slot to share the same counter. When all 14 distinct IDs are present, a slot can be classified `SAVE_STATUS_OK` despite inconsistent per-sector counters. The selected slot counter reflects the **last checksum-valid sector encountered in physical scan order**, not a verified unanimous counter or necessarily the largest counter within that slot.

The extracted host-C harness now includes two additional **valid-signature, valid-checksum synthetic** cases: one where the final physical sector of slot 1 has counter 10 while the first 13 have counter 1, and another where the first 13 have counter 11 but the last has counter 1. Slot 2 has counter 2 throughout. The first case should select counter 10; the second should select counter 2. These outcomes establish the selection predicate under the mocked sector contents, **not** that actual interrupted GBA writes generate those arrangements.

**XGBA compatibility implication:** An extension sidecar cannot rely on the selected numeric counter alone to prove that all 14 native sectors are from a coherent transaction. Additional validated native identity, recovery policy, and emulator tests are necessary. This is a new source-level negative-evidence witness, **not** an independently approved file or Phase 1 gate pass.
