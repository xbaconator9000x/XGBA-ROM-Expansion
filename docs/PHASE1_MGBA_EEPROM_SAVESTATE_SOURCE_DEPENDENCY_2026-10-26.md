# Phase 1 P0 — pinned mGBA EEPROM/savestate source dependency (26 October 2026)

**Decision: FAIL_INCOMPLETE. Independent whole-file dispositions: 0.** This is source-grounded interpretation of an unchanged pinned upstream revision, not a runtime expansion or a compatibility approval.

## Immutable upstream identity

All paths below are from mGBA commit `fd9dc5c2cbf234365068855851107e762fc6211b`.

| Source | Exact Git blob SHA-1 | Interpreted obligation |
| --- | --- | --- |
| [savedata.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/savedata.c) | `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` | EEPROM bit-command state, save type changes, settling event, savestate restoration |
| [savedata.h](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/savedata.h) | `6227be25e8c9d2c1cc14c06ded34389b96138577` | Command/read/write fields, file backing, pending event layout |
| [memory.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c) | `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc` | CPU 16-bit ROM2_EX EEPROM/e-Reader/ROM read-write priority |
| [serialize.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/serialize.c) | `a307a51e751f412c64a7378323c56758304ebe85` | Savestate sequencing, including savedata before Matrix and timing reroot |
| [timing.c](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/core/timing.c) | `cebd619957b0845deedfc03b1e9c89d168861ea1` | Scheduling and reroot callback dependencies |

The first two sources are **new candidate files** beyond the historical 29 curated sources. The remaining three are dependency anchors already considered in prior Phase 1 mapping. This packet does not modify the authoritative 14,834-file queue.

## Source-grounded producer/consumer interpretation

1. **Cartridge region is not exclusively ROM.** `memory.c:611–625` selects `GBASavedataReadEEPROM` for 16-bit ROM2_EX reads when EEPROM save type is active; `memory.c:986–999` handles e-Reader writes first, otherwise detects EEPROM and forwards to `GBASavedataWriteEEPROM`. The DMA-specific ROM2_EX EEPROM path in `dma.c:259–315` is a separate consumer and cannot be replaced with a generic ROM-bank intercept.
2. **EEPROM has a stateful timing dependency.** `savedata.c:507–583` implements bit-serial command/read/write behaviour. Writes mark save dirty and reschedule the `dust` event for `EEPROM_SETTLE_CYCLES = 115000` (`savedata.c:31, 536–540`). When not in read mode, `GBASavedataReadEEPROM` returns busy/ready based on whether this event is scheduled (`savedata.c:560–567`). The event callback is registered in `GBASavedataInit` (`savedata.c:46–64`).
3. **Savestate restores pending EEPROM timing.** `savedata.c:715–756` serializes command, addresses, pending settling status and remaining cycles, then schedules a restored event if pending. `serialize.c:229–240` calls `GBASavedataDeserialize` before `GBAMatrixDeserialize`, followed by `mTimingInterrupt`. These are source-level ordering facts, **not** proof of correct external resource-bank identity or every callback interleaving.
4. **Save capacity and backing are mutable.** `savedata.c:299–324, 485–504` initializes EEPROM as 512 bytes under autodetection and may promote to 8 KiB, unmap/remap the save file and signal `memoryBlocksChanged`. A hypothetical external cartridge bank cannot assume save backing, memory block type or callback lifetime is immutable.

## Machine-verifiable evidence and limits

The additive [candidate register](../semantic-snapshots/curated/mgba_eeprom_savestate_additive_candidates_2026-10-26.json) records source paths, exact blob hashes, dependency endpoints and unresolved whole-file obligations. [Source verifier](../tools/verify_mgba_eeprom_savestate_additive.py) checks five Git blobs, 13 pinned source expressions, and eight false-signoff/identity/dependency mutations.

[CI run #40221384077](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40221384077) passed the source-verification and evidence-archival steps at commit `8ce037ec735d13d0bfb87744d3ada1e68a317d40`. The successful workflow **did not run a new native emulator regression**, perform whole-file review or certify editor/save-state compatibility.

**Still required:** full control-flow/alias review of both new files; source-to-compiled layout verification, EEPROM bit-count and DMA/CPU interleavings, event callback reentrancy, save-type transition/mapping failure paths, restoration ordering under Matrix remap and explicit independent review. The two candidates must be reconciled into the versioned secondary review scheduler alongside the earlier timing/DMA additions before they can be counted as scheduled, without changing the original source census.

No XGBA Phase 2 code or native emulator behaviour was changed.
