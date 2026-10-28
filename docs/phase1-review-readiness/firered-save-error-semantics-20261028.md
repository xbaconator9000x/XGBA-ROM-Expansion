# Phase 1 — pinned FireRed save-error semantics and revision boundary

**Status: source-backed dependency investigation only. Gate FAIL_INCOMPLETE; no independent approval.** This does not claim a game-executed failed-save return or actual hardware power-loss durability.

## Immutable source identities

- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`; `include/save.h` blob `87fb9b615b434b58823d15688056695acda9feab`.
- `config.mk` blob `c07d31fc083fa341cca29c340e560ed107d5364a`; `Makefile` blob `8b454dbd18eb0069fa5851d788697190890a5b37`.
- `include/global.h` blob `77155b09014aa854fcf87260e6ad2969e222da53`; `src/fieldmap.c` blob `41567772299000ba5855419e5c39ad9373a34c20`; `src/field_camera.c` blob `88f94bff08ef951523facf2b579fbc3d4d8455b2`.

## Source-proven failure and data-flow edges

1. `TrySavingData` first checks `gFlashMemoryPresent`; false sets `gSaveAttemptStatus=SAVE_STATUS_ERROR` and returns `0xFF` without calling `HandleSavingData`.
2. For `SAVE_NORMAL`, `HandleSavingData` calls `SaveSerializedGame`, then `WriteSaveSectorOrSlot(FULL_SAVE_SLOT,...)`. The latter increments `gSaveCounter` before writing 14 sectors, but restores the old counter and last-written sector when `gDamagedSaveSectors != 0`.
3. In the default `GAME_REVISION=0` build, `TryWriteSector` calls `ProgramFlashSectorAndVerify`, sets or clears damaged-sector bits based on its result, and returns success/error. `TrySavingData` subsequently checks damaged bits and invokes `DoSaveFailedScreen` on failure.
4. `config.mk` defaults to `GAME_REVISION ?= 0`, and `Makefile` passes `-DREVISION=$(GAME_REVISION)`. The `REVISION >= 0xA` branch uses `svc_WriteSector` and a different verification contract. Passing native revision-0 tests does not certify revision 10.
5. `GetSaveValidStatus` indexes `locations[gSaveDataBufferPtr->id]` and `CopySaveSlotData` indexes `locations[id]` without a demonstrated ID bound. Native observations for malformed 14/15/65535 are finite examples, not arbitrary-ID safety.
6. `CameraUpdate` calls `CameraMove`, which mutates `gSaveBlock1Ptr->pos.x/y`. `SaveBlock1.pos` starts at offset zero, and `src/save.c` maps sector ID 1 to the first SaveBlock1 chunk. This grounds the player-coordinate roundtrip test.

## Reproducibility and negative controls

`tools/phase1_firered_save_error_semantics.py` verifies all seven pinned Git blob hashes, required source branches, six complete function-body boundaries, default compiler revision and five deliberately tampered source variants. It emits structured text evidence; no ROM, save or Flash mutation occurs.

The prior green CI #40610367694 demonstrates three **in-flight emulator-process terminations** at 1/7/13 valid counter-3 sectors, each with a fresh-process counter-2 fallback. Those are not verified hardware power cuts. The player-position test introduced at `f40e20e8` is pending native CI until its exact-head result is inspected.

## Unresolved reviewer questions

- Can a reproducible emulator fault injector force `ProgramFlashSectorAndVerify` to fail during a controller-initiated Save, then witness actual `TrySavingData` return `0xFF` and the error UI, without conflating host fault injection with game logic?
- Which revision-10 `svc_WriteSector` guarantees are external to this pinned source and how should an expansion tool negotiate them?
- Can sector-ID bounds be proven for arbitrary corrupted inputs before the unchecked array access, or must the boundary be explicitly hardened?
- How do asynchronous mapped-file visibility and host fsync/power-loss semantics differ from real Flash chip durability?
- Are the complete upstream source files independently reviewed beyond the selected functions? **Not yet; no approvals.**

## Real TrySavingData no-Flash return via pinned IWRAM fault (2026-10-28; pending CI)

Pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` `src/load_save.c` blob `8b723dd044c6024b3671bb890b25b56a53f99ec5` declares `COMMON_DATA bool32 gFlashMemoryPresent` and initializes it through `CheckForFlashMemory`. `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c` first guards `TrySavingData`: if `gFlashMemoryPresent != TRUE`, it sets `gSaveAttemptStatus=SAVE_STATUS_ERROR` and returns `SAVE_STATUS_ERROR` before `HandleSavingData`.

A new native probe watches actual compiled `TrySavingData` entry after controller Save navigation, writes zero to the pinned **IWRAM bool32** immediately before that instruction, and restores the original TRUE at the genuine caller-return PC. It requires entry/return 1/1, R0 `0xFF`, unchanged game-written counter1 Flash and physical SHA, zero Flash mutation, and two rejected invalid-address controls. This is explicitly a **host RAM fault injection**, NOT input-only saving, real Flash hardware failure, or proof of physical power-loss durability. Unexpected callsites fail closed. Runtime **pending exact-head CI**, independent approvals zero, Phase 1 FAIL_INCOMPLETE.

## 2026-10-28 CI-negative-control repair and save-attempt-status extension (pending CI)

[CI #40622610025](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40622610025) failed after successful pinned builds and earlier probes: the invalid object-events address control invoked the native probe without arguments, so argc validation rejected it before RAM-address validation. The repaired control supplies eight arguments, checks exit code 2 and the intended address diagnostic, and verifies a matched valid-address case reaches schedule loading. This is a harness defect, not a FireRed runtime result.

Pinned FireRed `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c` declares `COMMON_DATA u16 gSaveAttemptStatus`, distinct from load-time `gSaveFileStatus`. The native probe now resolves the compiled symbol, samples the 16-bit attempt status at the genuine `TrySavingData` caller-return PC and verifies restoration of `gFlashMemoryPresent`. The runner adds a matched counter-1 no-injection positive Save and an in-range wrong-symbol negative control targeting the compiled `gSaveBlock1Ptr` variable, which must reject before any RAM write. These additions remain **pending exact-head CI**. The host IWRAM fault is not a hardware Flash failure. Phase 1 `FAIL_INCOMPLETE`, zero independent approvals.

## Player-avatar initialization dependency closure — new native trace pending CI

Pinned `src/field_player_avatar.c` blob `ef086dda3a6bf2d175861d6a7be1831790208ecb` defines `InitPlayerAvatar`, `ClearPlayerAvatarInfo` and `SetPlayerAvatarStateMask`; `InitPlayerAvatar` spawns the player ObjectEvent, sets `isPlayer`, records the object ID and applies `PLAYER_AVATAR_FLAG_CONTROLLABLE | PLAYER_AVATAR_FLAG_ON_FOOT`. Pinned `include/global.fieldmap.h` blob `e2828ec0cb1439718e830fbef4366770b3b77b1c` defines controllable bit 5 (0x20), `preventStep` at avatar offset +6 and the ObjectEvent bitfields. Pinned `player_step` checks `preventStep` before dispatching `MovePlayerAvatarUsingKeypadInput`. The earlier [failed movement CI #40617145827](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40617145827) observed 192 nonzero direction calls but avatar flags zero and no SaveBlock1 position movement; this **does not** prove why flags were zero.

The new native probe records actual compiled-ELF entries to the three avatar initialization/state functions, frames with controllable bit set and frames with `preventStep` nonzero, alongside existing player ObjectEvent/camera telemetry. The movement assertion remains fail-closed; no synthetic fixture repair is made without runtime evidence. This is a partial function-level dependency trace, not complete-file approval or a player x/y roundtrip claim.

## 2026-10-28 source-proven map-load vs return-to-field dependency (pending exact-head CI)

[Exact-head CI #40628329334](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40628329334) verifies the independent **save-error fault path**: genuine `TrySavingData` returned `0xFF`, `gSaveAttemptStatus=255`, RAM flag restored, Flash unchanged, and a matched non-injected save succeeded. The run still failed the intentionally strict player movement assertion. Its native output: `InitPlayerAvatar=0`, `ClearPlayerAvatarInfo=1`, `SetPlayerAvatarStateMask=0`, player ObjectEvent active frames=0, controllable frames=0, `player_step` nonzero directions=192, and no x/y movement. This is now direct evidence of missing avatar initialization in the synthetic fixture's continue path, not a controller-key timing problem.

Pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` `src/overworld.c` blob `339014da46ae8543143edc99ab72bf7496203a0d` distinguishes `LoadMapInStepsLocal` **case 4** (`InitObjectEventsLocal` -> `ResetObjectEvents` -> `InitPlayerAvatar` -> `SetPlayerAvatarTransitionFlags` -> `TrySpawnObjectEvents`) from `ReturnToFieldLocal` **case 0** (`ResumeMap` -> `ReloadObjectsAndRunReturnToFieldMapScript` -> `SetCameraToTrackPlayer`), which does **not** create a player avatar. `CB2_ContinueSavedGame` chooses between `CB2_LoadMap` when `UseContinueGameWarp()` is true and return-to-field otherwise. The synthetic PalletTown fixture does not yet establish which game-authored persistent preconditions make that choice. The new probe therefore traces compiled `CB2_LoadMap`, `LoadMapInStepsLocal` and `InitObjectEventsLocal` alongside existing avatar symbols; it does not mutate RAM or relax x/y roundtrip assertions. The next experiment must establish a valid game-authored map-load/warp state or a genuine new-game path before claiming movement. This is not a complete-file approval; Phase 1 remains `FAIL_INCOMPLETE`.
