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
