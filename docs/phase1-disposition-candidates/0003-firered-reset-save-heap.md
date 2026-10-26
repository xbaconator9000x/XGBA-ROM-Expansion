# Phase 1 semantic disposition candidate 0003 — FireRed save-reload entrypoint

**Review state: PENDING_INDEPENDENT_REVIEW. This is a whole-file analyst candidate, not an approval, gate input or independent signoff.**

## Exact source identity

- Repository: `pret/pokefirered`
- Pinned commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`
- Entire file: [`src/reset_save_heap.c`, lines 1–27](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/reset_save_heap.c)
- Exact Git blob SHA-1: `745270dc7415b869c302daaa7b9c2b2e5b2865f1`
- [Pinned seven-file dependency trace](../PHASE1_P0_FIRERED_RELOAD_SAVE_RAM_LIFETIME_2026-10-27.md) and [reproducible source checker](../../tools/phase1_firered_reload_save_lifetime.py).

## Whole-file inventory and semantics

The entire 27-line file contains seven direct includes (`global.h`, `gflib.h`, `m4a.h`, `load_save.h`, `save.h`, `new_game.h`, `overworld.h`) and exactly one exported function, `void ReloadSave(void)`. It contains no conditional compilation, static data, other functions or inline assembly.

`ReloadSave` preserves `REG_IME` in a local `u16`, disables interrupts, invokes `RegisterRamReset(RESET_EWRAM)`, clears the display forced-blank bit and restores IME. It then sets `gMain.inBattle = FALSE`, rebinds save pointers, resets menu/party globals and save counters, loads `SAVE_NORMAL`, defaults SaveBlock2 only for `SAVE_STATUS_EMPTY` or `SAVE_STATUS_INVALID`, restores sound mode from SaveBlock2, initializes the heap, and installs `CB2_ContinueSavedGame`. The normal-load return value is not checked in this function.

**Source-only dependency classes:** BIOS/HLE reset mask; EWRAM save blocks versus IWRAM live pointers; flash and serialized game load; global/heap invalidation; audio option; overworld continuation; direct link-error recovery and revision-10 RFU reload wrapper. These are documented with exact source hashes in the linked trace. In particular, `ReloadSave` is not a fresh boot and its no-flash handling cannot be inferred from the EMPTY/INVALID fallback.

## Expansion impact and unverified conditions

- The EWRAM reset destroys the previous save-block backing memory, while pointer variables and interrupt state have different declared lifetimes. External-bank state cannot be assumed to survive this transition.
- The function restores IME before pointer rebinding and deserialization. The source does not prove interrupt delivery or absence in this interval.
- A failed `LoadGameSave` return is not directly examined. The separate `SAVE_STATUS_NO_FLASH` branch and subsequent continue callback require actual runtime recovery tests before any safety claim.
- Source-level linkage and ordering are not compiled address checks or a cross-emulator certification. Other upstream files' full-file dispositions remain pending.

## Independent reviewer obligations

1. Verify exact file bytes, include closure, symbols and entire 27-line scope independently.
2. Verify all seven included header contracts, call targets, variant macros and ABI/stack/IME preservation against compiled artifacts.
3. Exercise EWRAM-only reset, flash-absent and corrupt-save cases on pinned emulator and, where applicable, real BIOS/hardware, recording observations without generalizing beyond those configurations.
4. Review link-error and revision-10 RFU entry paths and continuation map/warp branches; assess pointer validity and external-resource implications.
5. Record a real independent reviewer identity, date, rationale and verdict; only then consider gate ingestion.

**Reviewer identity/verdict: none. Gate contribution: 0. Phase 1: FAIL_INCOMPLETE; independently approved 0/14,834.**
