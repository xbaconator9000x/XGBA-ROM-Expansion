# Phase 1 — original-agbcc ARM Trainer Tower sector 30/31 experiment (2026-10-29)

**EXPERIMENTAL / NOT VERIFIED UNTIL EXACT-HEAD CI / FAIL_INCOMPLETE / independent approvals 0/14,834.**

## Dependency-connected scope and immutable source identities

This is a new execution experiment, distinct from the previously GREEN host C wrappers, synthetic host-driven mGBA Flash bus, original-agbcc Trainer Tower stub, and six-file source-only Flash initialization closure. It must not be reported as successful until an exact-head Actions transcript proves execution.

- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`: original `TryWriteSpecialSaveSector` and `TryReadSpecialSaveSector` bodies, sectors 30/31 and 4,092-byte payload.
- `src/load_save.c` blob `8b723dd044c6024b3671bb890b25b56a53f99ec5`: `CheckForFlashMemory` calls original `IdentifyFlash` then `InitFlashTimer`.
- `src/agb_flash_1m.c` blob `e249fab9a350f3263e7df5f20ff301a6d008e3db`: `IdentifyFlash` initializes original Flash callbacks and `gFlash`.
- Original agbcc `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9` and original FireRed Makefile/preproc/GNU ARM linker, unchanged.
- Original mGBA `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`, unchanged.

## Test and fail-closed boundaries

The test-only native harness loads a pristine source-built FireRed ROM, configures emulated Flash1M, directly enters the **original linked** `CheckForFlashMemory` ARM routine, checks original `gFlashMemoryPresent` and `gFlash` globals, then directly enters the original linked sector30/31 writer and reader ARM routines with 4,092-byte synthetic EWRAM buffers. It checks sentinel, full payload, bank1 physical offsets `0x1e000`/`0x1f000`, sector isolation and invalid sector29 rejection. No host Flash commands are issued. Exact-head CI is required for every positive assertion and mutation rejection; a failed/timeout run remains negative evidence.

**Important limitation:** Direct-entry is not natural stock gameplay, original full boot or original e-Reader ingestion. Emulated Flash1M is a test-only hardware configuration; successful `CheckForFlashMemory` must be observed, not assumed. No persistent .sav restart, hardware power cut, real Flash device, real GUI or general transaction atomicity is proven. If the original routines require other boot state, record that as a genuine prerequisite rather than substituting a replacement Flash engine.

## Partial per-file reviewer handoff

`src/save.c`: reviewer must inspect full sector guard, source/destination copy lengths, sentinel, return status, and all Flash callsites. `src/load_save.c`: verify original detection/IRQ initialization and caller ordering. `src/agb_flash_1m.c`: verify chip ID and callback table selection, including default fallback and timer semantics. `src/agb_flash.c`, `src/main.c`, mGBA `src/gba/savedata.c`: unresolved whole-file and runtime boot dependencies; prior partial source dossiers are not whole-file approvals. License obligations for FireRed, agbcc and mGBA must be separately assessed before redistribution.

All inventory, semantic, compiler/linker, runtime, save/asset, editor and regression gates remain **FAIL_INCOMPLETE**; zero independent approvals. No Phase 2 or upstream patch.
