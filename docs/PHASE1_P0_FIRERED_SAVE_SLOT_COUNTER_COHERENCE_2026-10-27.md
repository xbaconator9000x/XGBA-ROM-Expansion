# Phase 1 P0 — FireRed save-sector counter coherence and slot-parity boundary

**27 October 2026 · exact-pinned source trace + two synthetic models · not runtime-certified · no approval.** FireRed pin [ce6406d8c2eaf46d543c8a2606de0c3cb1951982](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982). Source identities: src/save.c blob **36b960f375c92711aa49b99bdfe9c6b3a99d6b1c**, include/save.h blob **87fb9b615b434b58823d15688056695acda9feab**. This extends [flash sector ID validation](PHASE1_P0_FIRERED_FLASH_SECTOR_ID_AND_MAPVIEW_2026-10-27.md) and [sidecar save consistency](SAVE_SECTOR_AND_SIDECAR_SEMANTICS_v25.md).

## Dependency-connected producer → validator → copier

- **Normal producer:** WriteSaveSectorOrSlot increments gSaveCounter for a full save (src/save.c:133–160), and HandleWriteSector selects physical slot by gSaveCounter modulo NUM_SAVE_SLOTS (src/save.c:163–194). In normally produced full saves, the physical slot and the counter parity therefore correspond. There are 14 logical IDs per slot and two physical slots (include/save.h).
- **Validator:** GetSaveValidStatus iterates physical slots 0–13 and 14–27, tests signature and per-sector checksum, and accumulates the logical ID bitset (src/save.c:466–565). Each checksum-valid sector **overwrites** slot1saveCounter or slot2saveCounter. A slot is classified OK when all 14 logical ID bits are present; **the function does not require their counters to be equal**. The selected gSaveCounter is taken from the last checksum-valid sector encountered in that physical slot, not from a cross-sector coherence proof.
- **Reader:** TryLoadSaveSlot calls the validator and then CopySaveSlotData without gating copying on the validator's returned status (src/save.c:423–437). CopySaveSlotData chooses the physical slot **again**, this time using gSaveCounter modulo 2, and copies every sector whose signature and checksum pass (src/save.c:439–463). It does not compare per-sector counter values to the selected counter. LoadGameSave(SAVE_NORMAL) then invokes LoadSerializedGame (src/save.c:803–821).
- **Emulator/tool boundary:** The pinned mGBA FLASH1M raw importer copies bytes without validating FireRed logical slot counters (mgba-emu/mgba pin fd9dc5c2cbf234365068855851107e762fc6211b, src/gba/savedata.c blob fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb). A save editor/sidecar cannot infer an atomic native commit merely from the presence of all 14 ID bits.

## Two deterministic counterexamples — synthetic, not emulator runs

Assume physical slot 0 contains exactly one sector for each ID 0–13, every sector has a valid signature and matching payload checksum, and physical slot 1 is empty. The following counter values are **constructed**; they are not asserted to arise from a normal in-game save.

| Synthetic physical slot 0 | Validator result | Selected counter | Copy reads physical slot | Consequence at source-model level |
| --- | --- | --- | --- | --- |
| IDs 0–12 counter 100; ID 13 counter 102 | OK (all 14 ID bits) | 102 | 0 (102 modulo 2) | Mixed-generation slot accepted and its mixed data can be copied |
| IDs 0–12 counter 100; ID 13 counter 101 | OK (all 14 ID bits) | 101 | 1 (101 modulo 2) | Validator accepted slot 0, but copier reads **empty slot 1** |

The second case is a **source-level validator/copier selection divergence**, not a demonstrated runtime corruption. The pinned game may have additional initialisation/recovery behaviour outside these functions; actual flash manipulation and emulator tests remain open. No claim is made that normally generated full saves produce either fixture.

## Compatibility and open edges

An XGBA sidecar/flash importer must preserve native recovery semantics while checking **ID range, signature, checksum, per-slot generation coherence, physical slot/counter parity, and selected slot identity** before binding extension state to a commit. A checker must not silently redefine which native slot the game selects; compare the original game's behaviour separately from any proposed safer importer. The writer's incremental/link-save paths and counter wraparound require their own compiled/runtime treatment.

[Reproducible source/model checker](../tools/phase1_firered_slot_counter_coherence.py) pins both blobs, traces the writer, validator, selector and copier, runs eight fail-closed source mutations, and emits JSON for both synthetic fixtures. It is executed by the existing [flash-sector-ID workflow](../.github/workflows/phase1-firered-flash-sector-id.yml) after its existing source test. **Workflow success must be checked at the exact new commit; this document does not assert a pass.**

No complete-file candidate or independent approval is added. Inventory **14,834/14,834**; independently approved **0/14,834**; Phase 1 **FAIL_INCOMPLETE**. No Phase 2 implementation.
