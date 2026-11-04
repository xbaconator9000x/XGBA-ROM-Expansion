# Phase 1 — original FireRed input-to-Flash save-path closure

**Status: new exact-head native evidence pending.** This is a bounded
source/runtime closure on the existing PR #28 workflow. It does not duplicate
the green sector-1/7/13 interruption schedules or claim an independent review.
The Phase 1 gate remains `FAIL_INCOMPLETE`.

## Pinned source inventory and provenance

The workflow checks 31 individual files against Git blob IDs at:

- FireRed: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`
- agbcc: `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9`
- mGBA: `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`

The inventory covers FireRed input/callback dispatch, tasks, menu/save dialog,
save-sector serialization and loading, Flash geometry and program/erase APIs,
the revision-0 linker layout, agbcc build/install entry points, and mGBA
ARM/Thumb execution, GBA bus stores, Flash savedata, frame cleanup, core API,
and file-backed VFile mapping/sync. Each source file gets a separate compressed
JSON dossier recording the immutable commit, Git blob SHA-1, raw-byte SHA-256,
size, role, direct dependency references, relevant source line anchors,
license evidence, and `NEEDS_EVIDENCE` status. The workflow artifact also
contains the manifest and SHA-256 of every compressed dossier.

The pinned mGBA `LICENSE` file identifies MPL-2.0. The pinned FireRed and
agbcc repository roots contain no `LICENSE` file; the evidence records that
absence and does not redistribute their source text. The workflow records
the actual GNU ARM compiler, assembler, linker, `cpp`, `nm`, and build-tool
versions and executable SHA-256 values. Ubuntu package names remain
unversioned, so these observed binary identities are provenance, not an
immutable system-package pin.

## Source-grounded producer-to-consumer path

1. Original GBA key polling (`src/main.c::ReadKeys`) updates game key state;
   the overworld invokes player input and task handling.
2. The start-menu Save selection reaches `StartMenuSaveCallback`, the Save
   dialog, and `SaveDialogCB_DoSave`. The normal path calls
   `TrySavingData(SAVE_NORMAL)`.
3. For the actual revision-0 ROM, `TryWriteSector` calls
   `ProgramFlashSectorAndVerify`; revision 10's `svc_WriteSector` path is
   source-identified but is not the path under test.
4. The FireRed Flash API selects the device's sector program implementation.
   The Flash program/erase routines issue GBA stores in the `0x0E` bus region.
5. In pinned mGBA, ARM/Thumb stores reach `GBAStore8`, which dispatches
   Flash-backed SRAM-region writes to `GBASavedataWriteFlash`. Its program
   command updates `currentBank` bytes and savedata dirty state. Frame-end
   cleanup can later reach VFile sync; this does not prove physical power-loss
   durability.
6. Existing controller workflow output captures the first process's actual
   game save, then starts a separate mGBA process on that produced `.sav` and
   requires FireRed's loader and playable field state to recover it.

The machine manifest names each source edge and records the matching source
line numbers. These source facts do not alone establish that an input schedule
reaches a callsite; the compiled/native trace is a separate requirement.

## Native observation matrix

The existing dense-confirm controller schedule is reused; no forced PC,
host Flash write, synthetic function call, or injected save is used for the
positive save path. The probe now traces the linked `ProgramFlashSectorAndVerify`
ELF address in addition to the already observed Save-menu and
`TrySavingData` entry/return PCs. At each sector-program entry it snapshots the
corresponding 4-KiB mGBA mapped Flash sector; at the actual compiled routine's
caller return PC it records the sector argument, return value, changed-byte
count, and mGBA dirty/dirt-age state.

| Boundary | Positive observation required | Negative/control |
|---|---|---|
| Input/menu dispatch | `StartMenuSaveCallback`, `SaveDialogCB_DoSave`, and `TrySavingData` entry/return; return status `SAVE_STATUS_OK=1` | Existing no-input synthetic-slot boot must have no save or Flash-program entries |
| Compiled sector writer | 14 unique physical sectors 14–27, each `ProgramFlashSectorAndVerify` returning 0 | Duplicate/missing sectors or nonzero return rejected offline |
| mGBA Flash callback effect | Each same sector has changed mapped bytes and nonzero savedata dirty state after return | Zero byte changes or missing dirty state rejected offline |
| Fresh-process load | Separate process, no save call/program call, original loader and playable field state | The physical `.sav` must remain byte-identical on cold boot |
| Sector corruption | Existing post-save checksum-corruption control rejects the damaged newest slot and checks older-slot fallback | Existing offline and native corruption controls remain fail-closed |

This probe **does not directly instrument or count host-native
`GBASavedataWriteFlash` callback entries**. It correlates the exact compiled
FireRed function's execution and return with the pinned mGBA bus-to-callback
source path and the actual per-sector mapped-byte/dirty effects. Any report of
direct callback counts is therefore invalid. Callback-entry instrumentation,
if needed, is a distinct follow-up; no emulator source is modified here.

The starting playable save remains a checksum-valid synthetic Pallet Town
fixture. The game then receives ordinary controller input and performs the
observed save; this does not establish human New Game progression. Separate
`.sav` process visibility is not filesystem power-loss durability, and no
cartridge hardware or physical power-cut claim is made.

## Mutation coverage and reporting rule

The source checker has six call-path mutation negatives (menu-to-save,
revision-0 sector programming, device byte programming, mGBA bus dispatch,
savedata byte mutation, and VFile mapping) plus a Git-blob mutation negative.
Eight offline evidence tests include a valid-trace positive and negative
controls for duplicate/corrupted sector IDs, failed program return, invalid
return PC, missing mapped-byte change, missing dirty state, boolean forgeries,
and an unexpected Flash program in the no-input control.

All per-file records are `NEEDS_EVIDENCE`; no machine receipt is marked
`COPILOT_REVIEWED/PASSED`. Promote no claim until the exact final-head native
workflow produces its source manifest, toolchain identities, ELF symbol map,
per-sector trace, and separate-process cold-load result. Keep historical
independent approvals at 0/338 P0 and 0/14,834 total; Phase 2 and shared gate
files are untouched.
