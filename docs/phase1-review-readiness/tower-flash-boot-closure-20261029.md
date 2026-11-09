# Phase 1 — pinned FireRed Trainer Tower special-sector Flash boot prerequisite closure

**SOURCE ONLY / FAIL_INCOMPLETE / independent approvals 0/14,834.** This is a separate new six-file dependency investigation, not original-agbcc ARM sector30/31 execution, not a source patch and not physical Flash.

## Immutable source identity and partial per-file scope

Original `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`:

- `src/save.c` blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`: `TryReadSpecialSaveSector` and `TryWriteSpecialSaveSector` validate IDs 30/31 before calling original Flash routines. Their payload/sentinel logic was previously exercised in host C, not ARM/mGBA.
- `src/agb_flash.c` blob `08aeed1638e214a3cad8b28d103964ab24342fba`: `ReadFlash` and `VerifyFlashSector` depend on `gFlash->romSize`, bank switching and copied RAM-resident Thumb core; `ProgramFlashSectorAndVerify` invokes the original `ProgramFlashSector` function pointer and verification, with three attempts. `StartFlashTimer` uses initialized timer state and `gFlashMaxTime`.
- `src/agb_flash_1m.c` blob `e249fab9a350f3263e7df5f20ff301a6d008e3db`: `IdentifyFlash` identifies Flash and installs `gFlash`, `ProgramFlashSector`, `WaitForFlashWrite`, `gFlashMaxTime` and other original callbacks.
- `src/load_save.c` blob `8b723dd044c6024b3671bb890b25b56a53f99ec5`: `CheckForFlashMemory` invokes `IdentifyFlash` then `InitFlashTimer` on success.
- `src/main.c` blob `542b0f5d16dd93107523d11163bfcb70a42b707a`: `InitFlashTimer` calls `SetFlashTimerIntr(2, *func)`.
- `src/cereader_tool.c` blob `395be0bcbed8454e645a9f5670cde3024eda508e`: original Trainer Tower save/load functions call the sector30 then sector31 wrappers sequentially.

## Smallest compatible reuse path

For genuine original-agbcc ARM/mGBA sector transactions, **reuse the stock game boot Flash detection and timer initialization**, original `ProgramFlashSectorAndVerify` / `ReadFlash` and mGBA's existing Flash bank implementation. Do not directly enter sector30/31 routines after a bare mGBA reset and mistake uninitialized `gFlash` / function pointers for a transaction defect. A test-only controlled entry must either run original boot initialization or explicitly record any substituted precondition; neither is yet verified. No replacement Flash engine or writer is justified.

## Fail-closed evidence and reviewer questions

New checker pins six whole-source blobs, extracts eleven original function bodies, verifies dependency anchors and call ordering, and rejects one targeted mutation for every scoped anchor. These are **partial-function review records**, not whole-file semantic dispositions. Reviewer must independently establish exact original boot path, Flash identification success in pinned mGBA, IRQ/timer semantics, RAM Thumb relocation and power-interruption limitations before native transaction claims. Separate original-agbcc linked stub direct-entry and host-driven mGBA sector writes do not close this gap.

Licensing and asset notices for FireRed, original agbcc and mGBA must be reviewed separately before redistribution. All eight Phase 1 gates remain FAIL_INCOMPLETE; no independent signoff or Phase 2.
