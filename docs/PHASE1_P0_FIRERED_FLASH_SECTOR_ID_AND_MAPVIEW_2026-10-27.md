# Phase 1 P0 — FireRed save-sector ID validation and persistent map-view boundary

**27 October 2026 · EXACT-PINNED SOURCE TRACE + DETERMINISTIC ARITHMETIC · NOT APPROVED.** FireRed source: [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982). This is an additional dependency-connected **save-sector producer → validator → loader → fieldmap** investigation. It is **not** a full-file disposition, a corrupted-save exploit demonstration, a compiled-code comparison, or a runtime test. Independent approvals **0/14,834**; Phase 1 **FAIL_INCOMPLETE**.

## Immutable source identities and trace

| Pinned FireRed path | Git blob SHA-1 | Producer/consumer role |
| --- | --- | --- |
| `include/save.h` | `87fb9b615b434b58823d15688056695acda9feab` | 4 KiB sector, 3,968-byte payload, 16-bit sector ID, 14-entry save slot and signature |
| `include/global.h` | `77155b09014aa854fcf87260e6ad2969e222da53` | SaveBlock2 0xF24-byte layout, mapView at 0x898, adjacent records |
| `include/config.h` | `db131b2717ab739e62e41c5054a798f045c0631d` | MODERN forces UBFIX |
| `src/save.c` | `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c` | sector location table, flash writer, validator, raw copier and normal-load dispatch |
| `src/load_save.c` | `8b723dd044c6024b3671bb890b25b56a53f99ec5` | relocated SaveBlock2 pointer and non-SaveBlock2 party/event serialization |
| `src/fieldmap.c` | `41567772299000ba5855419e5c39ad9373a34c20` | 210-word map-view producer, 256/512-word variant scan and continue-map reader |

### FSID-001 — the map-view is included in the normal flash-sector payload

`src/save.c:43–76` assigns **sector ID 0** to `SAVEBLOCK_CHUNK(struct SaveBlock2, 0)` and statically checks that the structure fits the 3,968-byte sector payload. `UpdateSaveAddresses` (630–648) sets `gRamSaveSectorLocations[0].data` to the *current relocated* `gSaveBlock2Ptr`, and its size to the structure chunk size. `HandleSavingData(SAVE_NORMAL)` (650–675) invokes `SaveSerializedGame` and then writes `FULL_SAVE_SLOT`; the sector writer (300–320) copies the configured bytes into the flash buffer and calculates a checksum. `LoadGameSave(SAVE_NORMAL)` (803–821) calls `TryLoadSaveSlot` before `LoadSerializedGame`. The latter saves/restores party and object-event RAM copies, **not a separate map-view buffer** (`src/load_save.c:196–206`).

The declared `SaveBlock2.mapView[0x100]` occupies bytes **0x898–0xA97** relative to `gSaveBlock2Ptr`, within sector 0's payload and the 0xF24-byte SaveBlock2. Thus the map-view buffer is part of the serialized SaveBlock2 image when the normal save writer runs; it is **not categorically RAM-only**. This establishes the serialization route, **not** that a particular save operation leaves a nonempty view or that a saved-game resume encounters a given value.

`src/fieldmap.c:469–515` scans 0x200 halfwords without UBFIX and 0x100 with UBFIX, then `InitMapFromSavedGame` (96–100) invokes the loader. The legacy scan's last exclusive byte offset is **0xC98**, 512 bytes past the declared array's end at 0xA98, but still within SaveBlock2 and the 3,968-byte sector payload. It overlaps the persisted neighboring `linkBattleRecords`, `berryCrush`, `pokeJump`, `berryPick`, and early filler fields. This strengthens the earlier [saved-map-view boundary dossier](PHASE1_P0_FIRERED_MAPVIEW_SAVE_ARRAY_BOUNDARY_2026-10-27.md): a neighboring nonzero field could affect the emptiness predicate even if the map-view array is zero. **Reachability, actual values and any visible effect remain untested.** The normal build's UBFIX selection and exact compiled instructions remain separate gates.

### FSID-002 — raw 16-bit flash sector IDs index a 14-element array without a bounds check

The flash-sector footer declares `u16 id` (`include/save.h`); the RAM location array has `NUM_SECTORS_PER_SLOT = 14` entries (`src/save.c:91`). In `GetSaveValidStatus` (466–522), each of the two slot loops checks the sector **signature** before calculating a checksum with `locations[gSaveDataBufferPtr->id].size`. There is **no prior ID range check**. The signature check is **not** a proof that the ID is 0–13. A signature-matching malformed footer with ID 14 or higher reaches an out-of-range array access at source level. The subsequent `validSectors |= 1 << id` also has a shift-width precondition if the checksum branch is reached, but a shift outcome for malformed input is **not** demonstrated.

In `CopySaveSlotData` (439–463), the loop assigns `id = gSaveDataBufferPtr->id` and evaluates `locations[id].size` **before** checking the signature and checksum. That is a distinct, less restrictive input boundary: a malformed footer need not have a valid signature to reach the unguarded location lookup. The subsequent `locations[id].data[j]` copy is inside the signature/checksum branch; do not claim a write occurs without a valid branch. `TryLoadSaveSlot` (423–437) invokes `GetSaveValidStatus` and then `CopySaveSlotData` without checking the returned validation status first. This is a source-level **malformed-save precondition**, not an observed emulator crash, reachable player action, or a finding about normally generated save sectors.

The source contract for a future XGBA save importer is therefore to **validate sector ID in 0–13 before indexing, checksum sizing, shift or destination-copy selection**, while preserving native sector order, rotation, checksum and recovery semantics. That is an architectural compatibility requirement, **not** permission to patch the pinned game in Phase 1.

### FSID-003 — randomized RAM pointer must not be mistaken for flash offset

`src/load_save.c:69–83` computes an aligned 0–124-byte RAM offset and binds `gSaveBlock2Ptr = &gSaveBlock2 + offset`. `UpdateSaveAddresses` serializes from this pointer, not from the fixed `&gSaveBlock2` base. Consequently, the saved-sector layout offsets above are relative to the active SaveBlock2 pointer. A raw RAM snapshot or editor import must distinguish the runtime relocated pointer from the **logical sector-0 serialized structure**.

### FSID-004 — mGBA's flash savedata loader preserves raw bytes; game-level validation remains FireRed's responsibility

The pinned emulator [mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b](https://github.com/mgba-emu/mgba/tree/fd9dc5c2cbf234365068855851107e762fc6211b) has a separate boundary: `src/gba/savedata.c` (blob `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`) `GBASavedataSize` (169–192) selects **0x20000 bytes for FLASH1M** and `GBASavedataLoad` (194–226) copies the selected number of raw bytes from a `VFile` to savedata memory when `savedata->data` exists, or streams into a mapped VFile when the backing representation is file-based. The size constants come from `include/mgba/internal/gba/memory.h` (blob `0aad912613e726560d06bbdbf6061986e69e5842`, lines 72–73): FLASH512 = 0x10000, FLASH1M = 0x20000.

The bounded `GBASavedataLoad` function has **no FireRed-specific footer-ID, checksum, or signature parser**. Likewise, `GBASavedataReadFlash` (377–396) returns the addressed raw bank byte outside flash-command/status conditions. Thus a successful emulator savedata file load is **not evidence that the FireRed game will accept all its sector footers**, nor that `src/save.c` can safely index their IDs. This is a two-repository **storage-versus-game-validation distinction**; it does not assert that mGBA has no checks elsewhere or that malformed savedata causes a runtime crash. A full emulator save/load/restore test remains open.

## Reproducibility and fail-closed evidence

The [source checker](../tools/phase1_firered_flash_sector_id_boundary.py) verifies **six exact pinned blobs**, producer/consumer ordering, both validation loops, the unchecked copy path, map-view offsets and the normal save/load path. It rejects **16 in-memory semantic mutations** (IDs, sector extent, table lookups, save route, map-view variant and pointer rebinding). The dedicated [CI workflow](../.github/workflows/phase1-firered-flash-sector-id.yml) checks out the pinned upstream source, runs the checker and retains JSON evidence even on failure. A passing source checker only certifies its asserted source contract, **not** runtime safety or independent approval. The workflow's run result must be checked at its exact commit SHA.

## Unresolved dependency edges

1. **Compiled classic/modern:** extract original agbcc and modern GCC save and fieldmap functions, verify actual branch bounds, sector pointer layout and linker-visible data; source checks do not replace object disassembly.
2. **Runtime:** test normal save/continue, empty view with nonzero neighboring fields, both UBFIX modes, relocated SaveBlock2 pointer, and malformed footer IDs including 13, 14, 31, 32 and 65535. Capture emulator faults/status without relying on undefined C behaviour as a deterministic outcome.
3. **Recovery:** test both save slots, rotation, damaged checksum/signature, partial-sector validity and fallback. The source validator/copy order must not be conflated with observed recovery correctness.
4. **Editor and XGBA interchange:** preserve logical sector IDs, sector sizes, SaveBlock2 offsets and source provenance; do not silently normalize corrupted IDs into another valid sector.
5. **Whole-file and independent review:** `src/save.c`, `src/load_save.c` and `src/fieldmap.c` remain partial-subsystem traces, **not** newly prepared complete-file candidates. No external signoff exists.

**Phase 1: FAIL_INCOMPLETE. Independent approvals: 0/14,834. Phase 2: NOT STARTED.**
