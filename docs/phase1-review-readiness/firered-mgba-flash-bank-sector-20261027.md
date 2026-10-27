# Phase 1 P0 — pinned FireRed → mGBA Flash bank, sector and erase ABI

**27 October 2026. Status: COMPILED HOST-FUNCTION WITNESS PENDING EXACT-HEAD CI / FAIL_INCOMPLETE.**
This packet is source-grounded, does not execute a FireRed ROM or full mGBA emulator, and grants no whole-file or independent approval. It is stacked on the existing Flash-identification draft PR #18, not a replacement for that packet.

## Immutable upstream inputs

| Source | Exact revision | Git blob | Function bodies compiled |
| --- | --- | --- | --- |
| `pret/pokefirered/src/agb_flash.c` | `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` | `08aeed1638e214a3cad8b28d103964ab24342fba` | `SwitchFlashBank` |
| `pret/pokefirered/src/agb_flash_mx.c` | same | `b4f710f36449c46946294d0df3d61d493d5c0d1f` | `EraseFlashChip_MX` |
| `mgba-emu/mgba/src/gba/savedata.c` | `fd9dc5c2cbf234365068855851107e762fc6211b` | `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` | `GBASavedataWriteFlash`, `_flashSwitchBank`, `_flashErase`, `_flashEraseSector` |

The Python harness downloads these immutable sources, checks Git blob SHA-1 (including the Git blob prefix), extracts **definitions rather than forward declarations**, checks source anchors, compiles the exact six function bodies into a C11 host fixture with UBSan, and runs positive/negative controls. It intentionally substitutes the GBA physical save bus, timing scheduler, VFile and memory-block callback. Stub definitions are explicit in `tests/phase1_firered_mgba_flash_bank_sector.c`.

## Producer → consumer → save representation

1. FireRed `SwitchFlashBank(bankNum)` emits the physical unlock sequence `0x5555←AA, 0x2AAA←55, 0x5555←B0, 0x0000←bank`. Its physical `FLASH_WRITE` macro is mapped to mGBA's actual `GBASavedataWriteFlash` for this fixture.
2. mGBA's state machine consumes those writes, accepts bank-selection data only at offset zero and only for values 0 or 1, and calls `_flashSwitchBank`. A 512-Kbit chip selecting bank 1 changes type to Flash1M; backing VFile remapping is **not tested** because the fixture uses `vf=NULL`.
3. The host test programs a distinct byte in each of the 32 physical 4-KiB sectors across two 64-KiB banks, then checks all 32 bytes. It tests sector erase isolation across banks, whole-chip erase, invalid bank selection, the write-unlock requirement, dirty marking and erase timing scheduling.
4. The actual FireRed `EraseFlashChip_MX` emits the six-command chip erase sequence into the same pinned mGBA write state machine. Its GBA wait-state register, RAM-relocated status reader and Flash timer are explicit host stubs; the fixture checks the requested phase 3 and expected 0xFF status byte.
5. mGBA's `FLASH_COMMAND_PROGRAM` implementation directly assigns `currentBank[address] = value`. The fixture checks this model permits overwriting 0x00 with 0xFF without an intervening erase; this is a **source implementation observation**, not a claim about physical Flash chips or about the FireRed game using that sequence.

## Evidence and negative controls

`python tools/phase1_firered_mgba_flash_bank_sector.py --output phase1-evidence/firered-mgba-flash-bank-sector.json`

The script requires three exact upstream blobs and rejects eight in-memory source mutations: FireRed bank command, mGBA bank range, program destination, bank pointer shift, chip erase fill value, sector erase extent and sector erase timing and the FireRed chip erase command. The compiled C harness asserts 32-sector programming and targeted bank/erase outcomes. Results are archived by `.github/workflows/phase1-firered-mgba-flash-bank-sector.yml`. Do **not** treat a prior green PR #18 workflow as proof for this new branch; exact-head CI must pass.

## Unresolved dependency edges and negative evidence

- FireRed `ReadFlash` / `VerifyFlashSector` / `ProgramFlashSector_MX` / `EraseFlashSector_MX` are not compiled into this join. Full save-slot sector checksums, 14-sector recovery, Trainer Tower special sectors, write timeout and retry handling are not demonstrated.
- Full mGBA `GBAMemoryStore8`, ROM-header override, VFile mapping, save-file flush/reopen, savestate restore and GUI execution are not included.
- The stub timing scheduler checks the requested cycle constant, not elapsed emulated CPU cycles. UBSan is host-side only.
- A bank switch to an invalid value is rejected by the pinned mGBA consumer in this function-level test; other emulator versions and hardware are untested.
- ROM expansion, multi-gigabyte backing storage, interoperability with Porymap and editor round-trip remain unproven.

## Batch manifest and accounting

Dependency-connected source set: FireRed `src/agb_flash.c`, `src/agb_flash_mx.c` → mGBA `src/gba/savedata.c` → banked 128-KiB Flash representation. Adjacent unresolved owners: FireRed `src/agb_flash_mx.c`, `src/load_save.c`, mGBA `src/gba/memory.c`, `src/gba/overrides.c`, `src/gba/serialize.c` and VFile backends.

Both upstream files were already indexed. **New unique machine-processed files: 0; target shortfall: 1,000.** Historical machine-triaged pool: **14,721/14,721**. Registered analyst-prepared complete-file candidates: **113** (inherited baseline; no new registered reviews here). Independent approvals: **0**. All Phase 1 gates: **FAIL_INCOMPLETE**. Phase 2: **untouched**.
