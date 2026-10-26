# Phase 1 P0 — FireRed EWRAM-only save reload and RFU continuation lifecycle (27 October 2026)

**Verdict: SOURCE-INSPECTED / FAIL_INCOMPLETE.** This is a new cross-file semantic dependency trace, not proof of a runtime fault, successful recovery, expanded-ROM compatibility, or independent review. Whole-file independent approvals remain **0/14,834**.

## Immutable upstream identity

All observations below refer to `pret/pokefirered` at commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. The [machine checker](../tools/phase1_firered_reload_save_lifetime.py) rejects a different HEAD or any mismatch against these seven Git blob SHA-1 values:

| Pinned path | Git blob SHA-1 | Source role |
| --- | --- | --- |
| [src/reset_save_heap.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/reset_save_heap.c) | `745270dc7415b869c302daaa7b9c2b2e5b2865f1` | Complete `ReloadSave` implementation (27 lines). |
| [src/load_save.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/load_save.c) | `8b723dd044c6024b3671bb890b25b56a53f99ec5` | IWRAM pointers, EWRAM blocks, randomized rebinding and deserialization. |
| [src/save.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/save.c) | `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c` | Counter reset, flash/no-flash and normal-slot loading. |
| [src/new_game.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/new_game.c) | `3768b3ccb98cdad514b858cbc59244f21bedb7b0` | SaveBlock2 defaults and transient-global resets. |
| [src/overworld.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/overworld.c) | `339014da46ae8543143edc99ab72bf7496203a0d` | Continue callback, warp/non-warp branch. |
| [src/link.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/link.c) | `84506bf0e9a2374bbd8b06c6e78e03905927d17a` | Link-error acknowledgement and revision-specific RFU recovery. |
| [src/link_rfu_2.c](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/link_rfu_2.c) | `78087d76fd3b2869b2bedc5b6dc29840e7d7a55a` | Revision-10 RFU wrapper and alternative soft reset. |

## Producer → consumer and lifetime trace

1. **Entry and interrupt mask:** `ReloadSave` saves `REG_IME`, sets it to zero, calls `RegisterRamReset(RESET_EWRAM)`, clears forced blank, and restores the saved IME value **before** it rebuilds game/save state. This is **EWRAM-only** reset at the source call site, not a full-machine reset. The source alone does not establish every BIOS/HLE side effect or the safety of pending interrupts.
2. **Separate storage lifetimes:** `load_save.c` declares `gSaveBlock1`, `gSaveBlock2` and `gPokemonStorage` with `EWRAM_DATA`, but declares their live pointers with `COMMON_DATA` (IWRAM common). `SetSaveBlocksPointers` derives a 4-byte-aligned random offset from a 128-byte movement range, rebinds all three pointers, and updates bag and quest-log pointer consumers. **The old pointers cannot be assumed valid after reset/rebinding.** A source macro classification is not a compiled address proof.
3. **Reload order:** after rebinding, `ReloadSave` clears menu/party/quest globals, resets save counters, invokes `LoadGameSave(SAVE_NORMAL)`, defaults SaveBlock2 only if `gSaveFileStatus` is `EMPTY` or `INVALID`, reads its sound option, resets the heap and selects `CB2_ContinueSavedGame`. It does **not** branch on the return value of `LoadGameSave`.
4. **Normal save load:** `LoadGameSave` returns `SAVE_STATUS_ERROR` early when flash is absent (setting `SAVE_STATUS_NO_FLASH`). On the normal-save branch it calls `TryLoadSaveSlot`, then `LoadSerializedGame` (party/object-event copies) before assigning the result to `gSaveFileStatus`. This sequence **does not establish** valid contents when the slot load fails. The reloader's SaveBlock2-only default for EMPTY/INVALID is a narrow branch; the absent-flash path is a separate unresolved continuation obligation, not a proven exploitable defect.
5. **Continuation:** `CB2_ContinueSavedGame` initializes map/object/script state and chooses either the saved continue-warp route (`CB2_LoadMap`) or the normal field callback route (`CB2_ReturnToField`). The callback is not equivalent to a fresh `AgbMain` boot or a new-game initializer.
6. **Entry-path variant:** `link.c` calls `ReloadSave` on A-button acknowledgement of a wireless type-1 link error. Under `REVISION >= 0xA`, a separate `reloadOrReset` path selects `RfuSoftReset` when Mystery Gift is active and `RfuReloadSave` otherwise. The revision-gated wrapper in `link_rfu_2.c` stops sound, clears callback1 and then calls `ReloadSave`. **These paths must not be collapsed into a single unconditional reset path** in any future engine or editor conversion.

## Expansion compatibility consequences

An external-bank or emulator design must preserve the distinction between reset of EWRAM, retention of IWRAM state, save-pointer rebinding, heap invalidation, serial/RFU recovery and both continue-map branches. A ROM banking proposal cannot assume that loading a save performs a full hardware restart, that ROM addresses are stable across callbacks, or that all link errors return to the title screen. These are *requirements to investigate*, not implemented contracts.

## Fail-closed proof boundary

The new checker requires seven exact Git blobs, validates function-local order and cross-file producer/consumer relationships, and runs **15 mutation controls** that change reset masks, IME restoration, save fallback, pointer storage/rebinding, flash-load path, continuation warp and RFU routing. Its JSON manifest states `FAIL_INCOMPLETE` and zero independent approvals. A passing workflow proves only that these **specific source assertions** held for the pinned revision.

**Unresolved:** compiled memory placement and pointer offsets for all build variants; hardware/HLE `RegisterRamReset` effects; interrupt timing between IME restoration and state rebuild; no-flash/invalid-save continuation; real RFU error-path execution; external bank/save identity and editor round trips; independent full-file dispositions. Do not count this dossier as a completed whole-file review.

**Gate: FAIL_INCOMPLETE. Independent approvals: 0/14,834. Phase 2: not authorized.**
