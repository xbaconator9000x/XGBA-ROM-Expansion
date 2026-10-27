# Phase 1 semantic disposition candidate 0005 — mGBA GBA savestate serializer

**State: PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** This is an analyst-prepared whole-file candidate and is not a reviewer signoff or gate input.

## Exact identity and complete scope

- Repository: `mgba-emu/mgba`; pinned commit: `fd9dc5c2cbf234365068855851107e762fc6211b`.
- Entire [`src/gba/serialize.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/serialize.c); Git blob SHA-1 `a307a51e751f412c64a7378323c56758304ebe85`.
- Complete source: **243 lines plus a trailing newline** (244 split fields). File declares two exported constants, one log category, a private `GBABundledState` structure with state/extdata pointers, and exactly two exported functions: `GBASerialize` and `GBADeserialize`. The bundled structure has no direct use within this file; do not infer whether other translation units reference it.
- Direct pinned dependencies inspected: [serialized format/header](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/serialize.h), [RAM state copying](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c), [Matrix ROM mapping](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c), and the [six-blob cross-repository trace](../PHASE1_P0_FIRERED_MGBA_SAVESTATE_MATRIX_2026-10-27.md).

## Complete function-level semantic inventory

### `GBASerialize`

Writes format magic/version, BIOS checksum, ROM CRC32, master/global cycles; copies cartridge title and ID from the normal/VFAME ROM or multicart ROM, or zeroes identity when no ROM is loaded. Serializes 16 CPU registers, CPSR/SPSR, CPU event cycles, 6 banks of banked registers/SPSRs, BIOS and CPU prefetch, last-prefetched PC, halted/POSTFLG/IRQ-pending/blocked/key state, pending IRQ event time and BIOS stall. Delegates RAM, I/O, unlicensed-cartridge, video, audio and savedata protocol state to their respective serializers. Calls Matrix serializer only when `gba->memory.matrix.size` is nonzero. It does **not** serialize arbitrary external ROM-bank file contents in this function.

### `GBADeserialize`

Performs version-range validation (too-new/invalid hard error; older valid-range version warning and continue), BIOS checksum comparison (conditionally hard error for BIOS PC region), cartridge ID/title identity validation (hard error), ROM CRC32 comparison (**warning only**), negative/excessive CPU cycle checks (hard errors), and a conditional ROM-region PC-versus-loaded-ROM-size check (hard error). Returns `false` on accumulated hard validation errors **before** clearing timing state.

After acceptance, clears/reloads timing, CPU registers and banked registers, updates privilege mode, and masks an odd PC low bit with a warning. It restores unlicensed-cartridge mapping **before** selecting active memory region and reconstructing CPU prefetch (or using the backwards-compatibility memory-read fallback for older snapshots). Restores halted/POSTFLG/IRQ/blocked/keys/BIOS stall and delegates video, RAM, I/O, audio and savedata protocol restoration. Matrix ROM-window restoration is conditional on the **current** nonzero Matrix size, occurs after active-region/prefetch selection and memory restoration, and precedes the final timing interrupt. The function returns `true` after these calls; it does not examine a return status from each delegated restoration.

## XGBA impact and limits of evidence

- The saved `0x61000`-byte struct and ROM CRC field do not make the snapshot an external-resource identity manifest. A CRC warning alone does not prevent a snapshot with matching game ID/title from continuing; the PC-size check covers only a specific current-PC boundary.
- Reconstructed prefetch and remapped ROM-window bytes have an ordering dependency. The source does not demonstrate stale execution or prove coherence for a hypothetical external-bank architecture.
- The Matrix implementation's 16-entry replay and unchecked-in-function VFile read results create a **resource-length and provenance review obligation**, not proof that the current emulator necessarily reads invalid data.
- FireRed's in-game EWRAM-only `ReloadSave` and this emulator-wide snapshot restoration are separate lifecycles; do not merge their contracts.

## Independent reviewer checklist and disposition

A separate reviewer must verify the complete 243-line source, both functions and all branches; audit include/type/link dependencies and all delegated serializer implementations; test invalid/old/new savestate, BIOS variants, ROM identity and physical-bank truncation; inspect compiled struct layout, ROM remapping and prefetch on native emulator; verify external resource identity and editor round trips. Reviewer identity, date, rationale and verdict are **not supplied**. No generated or machine-tested evidence may be counted as independent approval.

**Gate contribution: 0. Phase 1: FAIL_INCOMPLETE; independent whole-file approvals 0/14,834.**
