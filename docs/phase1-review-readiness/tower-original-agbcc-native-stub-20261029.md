# Phase 1 — original-agbcc Trainer Tower stock stub in native pinned mGBA

**Status: new test candidate; exact-head native CI required. FAIL_INCOMPLETE, independent approvals 0/14,834.**

## Immutable source and reuse boundary

- FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `src/cereader_tool.c` blob `395be0bcbed8454e645a9f5670cde3024eda508e` and `src/trainer_tower.c` blob `732b3f2ed31ed95d6476b9e111d53f759c448d81`.
- Original `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9`, FireRed Makefile and GNU ARM/preproc.
- Unmodified `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`; reuse existing native mGBA core build/CMake target, not a new emulator or Flash implementation.

Original `ReadTrainerTowerAndValidate` returns FALSE in pinned FireRed source. Existing compiled-stub and compiled-caller tests already establish linked Thumb `movs r0,#0; bx lr` and two direct BL callsites. This investigation **does not repeat their proof as new evidence**; it adds original linked ARM execution inside native mGBA. The host harness loads a pristine source-built FireRed ROM, takes the original ELF symbol address, enters it directly in Thumb mode with test-only LR/SP, and verifies return zero for three different input R0 values with a bounded 32-step budget and unchanged EWRAM marker. It invokes existing compiled disassembly checker rather than reimplementing it.

## Partial per-file reviewer records

- `src/cereader_tool.c` — only the stock stub and dependency on `CEReaderTool_LoadTrainerTower` investigated; not complete-file coverage. Verify whether the stub is reachable in stock gameplay and whether an external-data-enabled variant exists before any claim of support.
- `src/trainer_tower.c` — compiled caller edges to `ReadTrainerTowerAndValidate` previously established; execution of `SetUpTrainerTowerDataStruct` or `StartTrainerTowerChallenge` **not tested here**.
- `src/save.c` — native Flash transaction not tested here. Existing host special-sector and host-driven mGBA bus tests remain distinct; neither establishes original ARM write execution.
- mGBA core/ARM/ROM loader — original native engine used, but complete-file review and hardware equivalence unverified.

## Negative controls and limits

Three original-agbcc native ARM direct-entry cases, sixteen transcript mutations, and seven existing compiled-stub disassembly mutations must fail closed. No patch to upstream source, no synthetic game code substituted for the original stub. This is **synthetic direct CPU entry into original code**, not naturally dispatched gameplay, not e-Reader payload ingestion, not physical Flash and not a two-sector ARM transaction. ROM/ELF binaries remain CI-local; only text JSON/logs are retained. Licensing and original source/asset notices remain separate and require independent review. The source inventory and 14,834 independent disposition approvals are unchanged.

Next: stock gameplay caller execution and original-agbcc ARM special-sector 30/31 Flash transactions, with independently reviewed source and emulator evidence. Do not advance Phase 2.
