# Phase 1 P0 — instruction-level FireRed save-loader reachability under pinned mGBA

Status: **RUNTIME EXPERIMENT / FAIL_INCOMPLETE**. No independent approval and no Phase 2 implementation.

## Provenance and baseline

- Parent: draft PR #24 commit `b6f0cee6a4b5ec25c2eb39eaf4340b65e8da10d8`, exact-head successful CI #40525408728, job 122263516059. This previously established source-built FireRed ROM boot, nine emulator frame-advance cases and host-driven Flash byte persistence across a cold reload. It did **not** establish native in-game save-loader entry, return, selected slot or correct game-state recovery.
- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, compiled with original `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9`.
- mGBA `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`, source-built `libmgba` and `mgba-perf`.
- Native functions: `src/save.c:LoadGameSave`, `GetSaveValidStatus`, `CopySaveSlotData`; executable addresses are read from the **same compiled FireRed ELF** by `arm-none-eabi-nm`. The emulator's `struct ARMCore` and `mCore::step` are compiled with the same mGBA feature macros as the pinned perf frontend.

## Additional runtime experiment

Three existing deterministic Flash fixtures (`slot0`, `malformed_id14`, `older_slot_fallback`) are reloaded into a real emulator with the compiled FireRed cartridge. Instead of merely advancing frames, the probe single-steps actual emulated ARM instructions and counts whether the executing PC equals the ELF entry address for each of the three save-loader functions. The probe compensates for ARM's +8 and Thumb's +4 prefetched PC, enforces a 100-million-instruction cap and requires 180 emulated frames. It records `trace_steps` and three entry-hit counts in per-case JSON evidence.

**Interpretation limits:** A zero hit is negative evidence **only within the observed first 180 frames**; it is not proof the loader can never execute. A nonzero hit demonstrates an entry-address observation, not successful return, checksum validation, selected slot, complete recovery or a user-triggered in-game save. An uninstrumented ROM and a synthetic zero-payload sector remain insufficient to prove authentic player-save compatibility. No debugger breakpoints or write instrumentation are claimed.

## Reproduction and fail-closed gates

Run `.github/workflows/phase1-real-firered-mgba-rom-save.yml` on this branch. The workflow pins three upstream revisions, validates FireRed save source blob IDs, builds original agbcc/FireRed/mGBA, exercises the existing nine probes, then captures the new instruction-step traces. Missing ELF symbols, incomplete frame advance, missing trace fields, malformed fixtures, Flash persistence mismatch or a build error fail CI. A green CI result verifies **this scoped experiment only**, not the Phase 1 runtime gate.

Unresolved dependencies: actual save-loader entry/return and branch reachability after title-screen input; in-game Flash erase/program; malformed-sector ID 14 safety at the real load callsite; mixed-counter acceptance; older-slot selection; cold-boot player-state round trip; changed-header save compatibility; Porymap Qt save/reopen with injected write failure. Source-level out-of-bounds findings from host AddressSanitizer remain separate from actual emulator faults.

## Accounting

Newly machine-indexed distinct pinned source files: **0** (historical machine triage 14,721/14,721; shortfall against 1,000: **1,000**). New registered whole-file analyst-prepared reviews: **0**. Historical registered candidates: **113**, subject to register reconciliation. Independent approvals: **0**. All Phase 1 gates: **FAIL_INCOMPLETE**.

## 28 October continuation: first instruction observations and CI diagnosis

The initial exact-head workflow #40533110096 **failed in its evidence-verification step**, after successfully building pinned agbcc/FireRed/mGBA, booting the ROM and running all three native instruction traces. Its stdout showed, separately for `slot0`, `malformed_id14` and `older_slot_fallback`, 15,652,054 emulated steps through frame 180, **one `LoadGameSave` entry, one `GetSaveValidStatus` entry and zero `CopySaveSlotData` entries**. This is real instruction-entry evidence from a failed workflow, not a successful recovery test. The immediate CI failure was the verifier attempting `json.loads` on the *entire* trace output stream, which includes non-JSON emulator diagnostic lines. The verifier now extracts exactly one structured trace record and rejects missing/duplicate records.

The pinned `src/intro.c:CB2_InitCopyrightScreenAfterBootup` calls `LoadGameSave(SAVE_NORMAL)`; `src/save.c:TryLoadSaveSlot` calls `GetSaveValidStatus` and then `CopySaveSlotData`. `include/save.h` defines `SAVE_STATUS_EMPTY=0`. Therefore, the observed status 0 and missing copy entry at frame 180 **cannot** be interpreted as completed save validation: the loader might still be running, might have returned early, or another untraced path may be involved. The trace now records the live `LoadGameSave` argument, return-PC observation, return value, terminal PC and up to 720 emulated frames (100-million-step cap), stopping after 180 frames if a return is seen. The probe records what happens; it does not assume a particular result.

The synthetic fixtures have valid-looking footer signatures and zero data, but they are not game-generated save states. The pinned `GetSaveValidStatus` and `CopySaveSlotData` index `locations[sector->id]` without a local bounds check. An ID of 14 is outside the fourteen-entry array (valid IDs 0–13). This is a source-level malformed-input hazard, **not yet** a demonstrated native emulator crash or a claim of save recovery. The source-level counter selection can also use the last checksum-valid sector's counter rather than verifying uniform counters within a slot; runtime outcomes remain to be measured.

This continuation creates **zero** new machine-triaged source identities, **zero** registered whole-file analyst reviews and **zero** independent approvals. All Phase 1 gates remain `FAIL_INCOMPLETE`.

## Distinct-payload recovery witness — next exact-head CI experiment

A new synthetic-data marker is placed at SaveBlock2 offset `0xB80`, within the pinned `include/global.h:SaveBlock2::filler_B20` range (`0xB20..0xF1F`). The older physical slot uses `0xA5`; the newer slot uses `0x5A`. The fixture checksum is updated to match the actual pinned additive 32-bit-word checksum in `src/save.c` (for an otherwise zero-filled payload, the aligned marker contributes its byte value). The actual source-built ROM's relocated `gSaveBlock2Ptr` pointer is read through the pinned emulator bus after native loader execution, and the corresponding byte is recorded. A marker match would support **which payload was copied**, but not establish a complete, playable save or in-game save generation. The marker outcome is recorded without prejudging it or promoting Phase 1 gates.

The prior exact-head CI #40543682280 at commit `f93a5a77` succeeded: native instruction traces reached `LoadGameSave`, `GetSaveValidStatus` and `CopySaveSlotData`, with `LoadGameSave` entry argument zero. At frame 197, the single-slot fixture showed `gSaveFileStatus=1` (SAVE_STATUS_OK), whereas malformed ID 14 and damaged newer-slot fixtures showed `gSaveFileStatus=255` (SAVE_STATUS_ERROR) with `gSaveCounter=0`. The trace also reported an observed return-PC hit but `r0=160`, inconsistent with the status codes; **do not interpret that register snapshot as a verified function return value** without instruction/ABI reconciliation. These are source-built emulator observations, not independent approval or proof of complete recovery.

## 28 October subsequent CI failure and five-fixture payload experiment

Exact-head workflow [#40544347189](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40544347189) at `86f21b080f6b61a935755e308f5a4b7ca6da517d` **failed** after all pinned builds and 180-frame probe controls passed. The concrete cause was a **probe CLI arity mismatch**, not an apt installation stall: the workflow passed the additional `gSaveBlock2Ptr` ELF address as the tenth argument, while the C trace-mode guard incorrectly required nine. The emitted error was `ERROR: trace mode needs three ELF function addresses`. The corrected guard requires ten arguments. That failed run provides **no native marker-selection result**.

The follow-on experiment includes five fixtures: `slot0`, `both`, `mixed_counters`, `malformed_id14` and `older_slot_fallback`. It fail-closes on SaveBlock2's actual relocated pointer, a `CopySaveSlotData` entry hit and the byte at offset `0xB80`. Source-derived expected triples (`gSaveFileStatus`, `gSaveCounter`, marker) are respectively `(1,0,A5)`, `(1,1,5A)`, `(1,2,A5)`, `(255,0,A5)` and `(255,0,A5)`. These are **test hypotheses until the exact-head emulator run passes**. In pinned `src/save.c:GetSaveValidStatus`, the most recent checksum-valid sector updates each slot's counter; a mixed-counter slot is not rejected merely for counter inconsistency. The malformed ID14 path indexes `locations[id]` before validation and remains a source-level bounds hazard, not an established native crash.

Pinned source identities: FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` (`src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`, `include/save.h` blob `87fb9b615b434b58823d15688056695acda9feab`); `include/global.h` SaveBlock2 filler offset checked by source inspection but **not yet separately blob-pinned in this test**. No independent approval or whole-file review is asserted.

Negative evidence: no authentic in-game SaveGame invocation, no playable player-state round trip, no proof of altered-header save correctness, and no Porymap Qt project save/reopen under injected failures. Phase 1 remains `FAIL_INCOMPLETE`.

### Mixed-counter cross-boundary risk (source-grounded, runtime outcome pending)

The pinned `GetSaveValidStatus` updates the second slot's counter from **each checksum-valid sector**. In the deterministic `mixed_counters` fixture, the last sector in physical slot 1 carries counter 2 while the others carry 1, so `gSaveCounter=2`. The pinned `CopySaveSlotData` then computes `NUM_SECTORS_PER_SLOT * (gSaveCounter % NUM_SAVE_SLOTS)`, selecting **physical slot 0** despite the last valid counter having been read from physical slot 1. Therefore the source-derived payload marker is `0xA5`, not `0x5A`. This is a source-proven producer/consumer mismatch for deliberately inconsistent save counters, **not yet** a runtime-confirmed defect or a claim about normal game-generated saves. The five-fixture CI asserts this expected selection and will expose disagreement rather than conceal it.

## Native five-fixture payload observations — CI #40552530270

[Run #40552530270](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40552530270) at `0682b0ae7a0619e6143d4e603d12dec1e2e13e2b` **failed due to a wrong test oracle**: it expected `0x5A` for the mixed-counter case, while the real compiled FireRed/mGBA trace reported `0xA5`. This matches the pinned `GetSaveValidStatus` → `CopySaveSlotData` modulo-selection source reasoning. The CI log contains all five actual emulator trace records, despite the failing assertion; the later commit corrects the oracle rather than altering the ROM or fixtures.

| Synthetic fixture | Observed frame | `gSaveFileStatus` | `gSaveCounter` | SaveBlock2 marker | Interpretation |
| --- | ---: | ---: | ---: | --- | --- |
| `slot0` | 197 | 1 | 0 | `0xA5` | Valid older slot copied |
| `both` | 197 | 1 | 1 | `0x5A` | Newer slot copied |
| `mixed_counters` | 197 | 1 | 2 | `0xA5` | Counter parity selects older physical slot |
| `malformed_id14` | 197 | 255 | 0 | `0xA5` | Error status but older slot copied |
| `older_slot_fallback` | 197 | 255 | 0 | `0xA5` | Damaged newer slot; older slot copied |

Each trace observed one entry into `LoadGameSave`, `GetSaveValidStatus` and `CopySaveSlotData`; the relocated SaveBlock2 pointer was `33703304` (`0x02024A08`), and the payload was read via the actual emulator bus. The persistent `load_game_save_return_value=160` remains **unverified as a function return**. These are synthetic Flash input files and actual ROM/emulator *read/recovery* observations, **not game-initiated Flash writes or complete playable-save recovery**.

The pinned FireRed `include/global.h` blob is `77155b09014aa854fcf87260e6ad2969e222da53` (SaveBlock2 `filler_B20` at `0xB20..0xF1F`). The next exact-head CI must pass with the corrected `mixed_counters` oracle. No independent approval is conferred; Phase 1 remains `FAIL_INCOMPLETE`.

## Additional adversarial native trace experiment — sector IDs 15 and 65535 / changed header

This checkpoint extends the **real pinned mGBA executable** test, not the source-only harness. `tools/phase1_real_firered_mgba_fixtures.py` now emits two additional checksum-valid synthetic Flash fixtures with one newer-slot sector's ID changed to **15** or **65535**, beyond FireRed's fourteen-entry location table. The earlier ID14 case remains unchanged. A separate reproducible runner (`tools/phase1_real_firered_mgba_adversarial.py`) tests the original ROM with a valid-slot control and the two malformed fixtures, plus a checksum-repaired ROM-header `BPRE` → `ZZZZ` variant using the same valid-slot save. It records process exit classification, emulator trace, selected payload if observed, and physical save SHA256 before/after, without asserting an unproven result for malformed data or changed headers.

The valid original-header slot0 case must still enter the native loader/validator/copier and load the `0xA5` marker with status 1 and counter 0. For changed headers and malformed IDs, the runner **records** a completed native trace, a signal termination or an explicit probe error; it fails on unclassified exit or timeout. A green CI would establish only that these cases were observed and classified, not that arbitrary malformed sector IDs are safe. Source-level `locations[sector->id]` out-of-range indexing remains a hazard, with no runtime crash asserted before evidence exists. Save-file hash comparisons detect physical changes during the observation window but do not attribute them to a game-initiated SaveGame call.

Pinned source identities and builds remain the existing workflow's FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, agbcc `da598c1d918402c42c0c0d7128ba14567f3175e9`, mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`, including the pinned FireRed save source blob checks. This experiment introduces **zero** newly machine-indexed files (shortfall **1,000**), **zero** whole-file analyst approvals, and **zero** independent approvals. All Phase 1 gates remain `FAIL_INCOMPLETE`. The next proof still requires a game-initiated save write and cold-boot player-state round trip.

## Exact-head runtime classification checkpoint

Commit `3c7dc7a8d69a34222fae4fb1fedcb74d50e368ce`, [CI #40562306927](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40562306927), passed. The pinned native probe produced process return code 0 and a structured trace for all four added cases: unmodified slot0 control, changed-header slot0, malformed ID15 and malformed ID65535. This establishes **trace completion only** for the adversarial cases; the initial log printed classification but not the internal status/counter/marker fields, so those values must not be invented from the green check. Artifact `12760991993` contains the text evidence.

The follow-up checkpoint validates fixture SHA256 against its generated manifest, ROM source/header digests and exact malformed footer IDs before invoking the emulator. It also prints per-case frame count, loader/validator/copier entry hits, status, counter, selected SaveBlock2 marker and whether the physical save file changed during tracing. This exposes the previously artifact-only details in exact-head CI logs. A save-file hash change alone would not prove that the game performed a normal save transaction. Independent approvals and Phase 1 gate states remain unchanged.
