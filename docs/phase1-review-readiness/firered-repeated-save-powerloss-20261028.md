# Phase 1 P0 — repeated native FireRed saves and checksum-corruption control (2026-10-28)

**Experiment pending exact-head CI; all gates FAIL_INCOMPLETE.** No independent approval. This is a focused save subsystem investigation, not a whole-file semantic disposition.

## Pinned source and ownership

- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, agbcc `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9`, mGBA `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`.
- FireRed `src/save.c` owns `TrySavingData`, sector counters, slot parity and checksum; `src/start_menu.c` owns controller Save dialog; `src/load_save.c` and `src/overworld.c` own cold-boot recovery and field control. Native symbol addresses are taken from the actual compiled ELF.
- mGBA `src/gba/savedata.c`, `include/mgba/internal/gba/savedata.h`, and `include/mgba/core/core.h` own Flash device, file flush and input APIs. Existing workflow pins their immutable source revision.
- Starting save is a **game-written first save** from green PR #28 CI #40601242124, but its *original playable player state* was a synthetic PalletTown fixture. This test does not establish human new-game progression.

## New source-grounded dependency tests

1. Copy the previously game-written counter-1 save; verify all 14 unique logical sector IDs, signature `0x08012025`, checksum and counter in physical slot 1.
2. Cold-start a fresh pinned emulator with that saved Flash; replay the already proven controller Save-menu schedule (3,200 frames), tracing real `StartMenuSaveCallback`, `SaveDialogCB_DoSave`, `TrySavingData` and actual caller-return `R0`. Require `SAVE_STATUS_OK=1`, counter **2**, nonzero Flash mutation, physical save SHA change and **14 valid sector IDs in physical slot 0**.
3. Assert second save preserves physical slot 1 unchanged; this tests alternating-slot overwrite isolation, not arbitrary crash safety.
4. Open a separate fresh emulator on the second game-written save, replay only Continue/field navigation (2,400 frames); require counter 2, RED name, PalletTown group 3/map 0/layout 78, field-input execution and no new save or physical Flash changes.
5. Negative control: flip one checksum bit in newly written physical slot 0 **after** save completion. Require offline sector checksum validator rejection; cold boot this altered file and record actual FireRed status/counter, player state and whether older-slot fallback occurs. Do **not** infer that this simulates a real mid-program power loss; the corruption timing is synthetic.

## Fail-closed boundaries and review questions

- A green first-save result from PR #28 does not certify the new repeated-save tests. Report native results only after exact-head CI passes.
- A checksum-corruption surrogate cannot establish actual Flash erase/program interruption, save atomicity on physical cartridges, or arbitrary malformed-sector memory safety.
- Remaining review: check source `save.c` slot parity, save error return propagation, mGBA file-flush behaviour, and the exact sector-selection status on damaged newest slot; then test real interrupted Flash commands if controllable without faking game execution.
- Preserve distinct analyst-prepared whole-file and independently approved counts; do not claim either from this partial subsystem dossier.

**Current Phase 1 decision: FAIL_INCOMPLETE. Phase 2 untouched.**

## Exact-head CI result and negative-control strengthening

At `ff6cc431841a4961853af530808100f47c7ca80b`, [CI #40604175206](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40604175206) **passed** (text artifact `12780755653`). Actual second controller-driven `TrySavingData` entry/return 1/1, return `SAVE_STATUS_OK=1`, counter 2, **862 Flash bytes changed**, physical `.sav` SHA changed, 14 checksum-valid rotated sectors in physical slot 0, prior slot 1 unchanged. A new emulator process recovered RED/PalletTown, counter 2 and 1,259 field-input hits without writing Flash. One-bit post-save checksum corruption produced native status **255**, counter **1**, older-slot recovery and 1,018 field-input hits. This is **not** actual in-flight power loss. Pinned FireRed `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`; pinned mGBA `src/gba/savedata.c` blob `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`.

This follow-up makes the observed older-slot fallback an **asserted regression requirement**, adds a Python syntax check and includes the new test/dossier paths in the workflow trigger list. **New head requires its own exact-head CI** before promotion; the previous green run remains valid for its immutable commit. All Phase 1 gates `FAIL_INCOMPLETE`, no independent approval.

## Third genuine game save — in-flight emulator-process interruption experiment

**New experiment; exact-head CI not yet verified.** Source-built pinned
FireRed/agbcc/mGBA starts from the already game-written counter-2 Flash
save and navigates the real Save menu via controller input. The test
observes checksum-valid counter-3 sectors in the mGBA mapped Flash1M
image during actual `TrySavingData`, polling every 2,048 instructions.
After 1, 7 or 13 complete new sectors in physical slot 1, the test
immediately calls `_exit(86)` **before the game save returns**.
There are no host Flash bus writes and no graceful emulator deinit.

The runner independently reads the resulting physical .sav, requires
counter-2 physical slot 0 byte-for-byte unchanged, verifies the new
sector count matches the in-memory observation, then cold-boots each
interrupted file in a new emulator process. The expected fallback is
counter 2, RED in Pallet Town, playable field input and no new writes.
A threshold of 14 is deliberately rejected as a negative control,
because a completed 14-sector save is not an in-flight interruption.

**Limit:** abrupt emulator process exit is not hardware power loss or
a filesystem durability guarantee. Pinned mGBA `src/gba/savedata.c`
blob `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` maps Flash
with writable VFile mapping and can later sync through
`GBASavedataClean`. Host OS page-cache writeback can persist mapped
changes even when the emulator exits abruptly. Pinned FireRed
`src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`
defines rotating sectors and the game-save call path.

Do not infer results from successful compilation alone. No new
complete-file analyst review or independent approval; all Phase 1
gates remain FAIL_INCOMPLETE. Phase 2 untouched.

### Pinned mGBA flush lifecycle and durability boundary

Additional pinned source closure:
`mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`
`src/gba/gba.c` blob `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e`
calls `GBASavedataClean` from `GBAFrameEnded`.
`include/mgba/internal/defines.h` blob
`67b8ec8fd2f51ee2c0c6231443af752158397b03`
defines `mSAVEDATA_CLEANUP_THRESHOLD=15`: a newly dirty save
is marked seen, then `mSavedataClean` requests cleanup only after
**more than 15 frames** without a new dirty write. Pinned
`src/gba/savedata.c` blob
`fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`
calls `vf->sync` only on that cleanup path with a writable mapping.
The in-flight hook now records the actual mGBA `dirty` flags and
`dirtAge` at interruption, without asserting that those flags prove
or disprove physical durability. This differentiates emulated Flash
programming, emulator-managed sync eligibility, host shared-memory
mapping persistence, and real power-failure durability.

**Unresolved:** no actual storage power cut, no proven sync-success
callback from VFile, no fsync guarantee, and no independent review.

### Source-verified VFile mapping: visibility is not power-failure durability

The pinned Linux file backend `src/util/vfs/vfs-fd.c` at
`mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`,
Git blob `2535bd0fb76740745ae038d5523ead28658f1035`,
uses `mmap(..., MAP_SHARED, ...)` for writable save mappings.
Thus a second process can read page-cache-coherent .sav changes
after `_exit` **even without** `GBASavedataClean` or `core->deinit`.
A successful in-flight test proves *mapped-byte visibility and game
fallback* under this Linux environment, **not persistence across
host power loss**.

The same pinned `_vfdSync` implementation returns immediately after
`msync(buffer, size, MS_ASYNC)` when `_POSIX_MAPPED_FILES` is enabled,
before the later `fsync(fd)` branch. Therefore a source-level
`GBASavedataClean` sync-success observation would **not alone**
establish durable media commit on that build. `_vfdUnmap` uses
`msync(..., MS_SYNC)` before `munmap`, but the in-flight hook
intentionally bypasses it. A hardware power-loss or fault-injected
filesystem durability test is still missing.

Reviewer questions: Which VFile backend/configuration is selected in
each target environment? Does the mapped save require explicit durable
`fsync` on the fd after `MS_ASYNC`? What evidence can establish the
power-loss ordering of sectors on real hardware? Do not generalize
the Linux `MAP_SHARED` observation to Android, Windows or GBA Flash.

## Native player-position roundtrip investigation (pending exact-head CI)

The new `tools/phase1_firered_position_roundtrip.py` checks a state change
that prior RED/PalletTown-only tests did not distinguish: player **x/y**.
Pinned FireRed `include/global.h` blob `77155b09014aa854fcf87260e6ad2969e222da53`
defines `SaveBlock1.pos` at offsets 0 and 2; pinned `src/save.c` blob
`36b960f375c92711aa49b99bdfe9c6b3a99d6b1c` maps sector ID 1 to
the first SaveBlock1 chunk. The source-built emulator reads relocated
`gSaveBlock1Ptr` through the bus, and the runner independently decodes
the checksum-valid physical sector ID 1, not a host-edited save payload.

The controller-only experiment separately requires (a) movement without
saving changes RAM x/y but not the physical save, (b) a cold boot reverts
unsaved movement, (c) movement followed by actual `TrySavingData` with
return `SAVE_STATUS_OK` persists different x/y to counter2 Flash,
and (d) a fresh process recovers exactly those persisted x/y without
further Flash changes. Missing movement, unexpected save, failed checksum,
wrong physical slot, or mismatched x/y all fail closed.

**Pending:** this paragraph documents a test design, NOT a passed result.
The initial playable counter0 fixture remains synthetic; this does not
establish human-played new-game progression or physical power-loss durability.

## Save-error source branch verification (pending exact-head CI)

A separate fail-closed checker now covers pinned `TrySavingData`,
`TryWriteSector`, full-slot counter rollback, `SAVE_NORMAL` serialization,
the revision-0 versus revision-10 compiler branch, and the unchecked
sector-ID indexing boundary. It checks seven immutable upstream Git blobs,
six function bodies, and five source-tampering negative controls. See
`docs/phase1-review-readiness/firered-save-error-semantics-20261028.md`.
This is source-only evidence, not a game-executed error return.

## First x/y test failed closed; controller movement diagnostic (2026-10-28)

Exact-head [CI #40616288179](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40616288179)
at `3e27327561499c6872d62cd4b4a30ee75daac7d3` **failed** in
the new x/y test, not in the previously green save/interrupt tests.
The source-only seven-blob/six-function/five-tamper checker **passed**.
The native no-save controller case had status1 counter1, 1,767
`FieldGetPlayerInput` hits, zero Flash changes and no
`TrySavingData`, but final `SaveBlock1.pos` was still (11,10), equal
to the physical first-save coordinates. This does not establish
movement, and is **not** a player-position roundtrip pass.

The previous movement schedule used three 16-frame RIGHT pulses near
frames 1005/1030/1055, possibly too short or blocked. The new
investigation replaces them with distinct 96-frame RIGHT and DOWN holds
after title Continue, separates earlier A pulses, and records **actual
gMain held/new directional keys during CB2_Overworld**, first/last
SaveBlock1 positions and first position-change frame. It fails closed
if keys are not received or coordinates do not change. The result
must be read from the new exact-head CI, not inferred from the test
design. All Phase 1 gates FAIL_INCOMPLETE, zero independent approvals.

## Held directions registered, but no camera position change (2026-10-28)

At `3f260ca238ab2f2c76755b7d91eaa61e10216e10`,
[CI #40616759445](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40616759445)
**failed closed** in the new player-movement assertion. Unlike the
earlier short-pulse test, the actual `gMain` registers **192 held
direction frames and 2 new directional presses while CB2_Overworld is
active**, and `FieldGetPlayerInput` executes 1,767 times. Yet
`gSaveBlock1Ptr->pos` remains (11,10), with **zero** position-change
frames and no game save or Flash writes. The controller schedule itself
is not sufficient to establish movement; do not infer a position
roundtrip or simply extend the held-key duration again.

Pinned `src/overworld.c` blob `339014da46ae8543143edc99ab72bf7496203a0d`
shows `DoCB1_Overworld` calls `FieldGetPlayerInput` before testing
`ArePlayerFieldControlsLocked()`, and only calls `player_step`
when unlocked and no other field event consumes input. Pinned
`src/script.c` blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`
defines `sLockFieldControls`; pinned
`include/global.fieldmap.h` blob
`e2828ec0cb1439718e830fbef4366770b3b77b1c` defines
`gPlayerAvatar` flags/running/tile-transition/object-event offsets.
Pinned `src/field_player_avatar.c` blob
`ef086dda3a6bf2d175861d6a7be1831790208ecb` owns `player_step`.

The next exact-head test reads these **actual compiled ELF symbols**,
records locked frames, `player_step` entry and nonzero-direction
hits, and avatar flags/transition state, while preserving the fail-closed
movement assertion. It must distinguish locked field controls,
missing player-step dispatch, and avatar/collision failures before
changing synthetic fixtures or declaring playable movement.
