# Phase 1 P0 — compiled FireRed ↔ mGBA Flash ID function join

**Status: pinned source-function integration under a simulated Flash bus / FAIL_INCOMPLETE.** The test does not run an actual FireRed ROM or native mGBA emulator and is not a whole-file review or independent approval.

## Reproducible pinned source identity

The executable witness `tools/phase1_firered_mgba_compiled_flash_join.py` verifies exact Git blobs and compiles **unaltered source function bodies**:

| Upstream pinned repository | File / function | Git blob |
|---|---|---|
| `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` | `src/agb_flash_1m.c` / `IdentifyFlash` | `e249fab9a350f3263e7df5f20ff301a6d008e3db` |
| same | `src/load_save.c` / `CheckForFlashMemory` | `8b723dd044c6024b3671bb890b25b56a53f99ec5` |
| `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b` | `src/gba/savedata.c` / `GBASavedataReadFlash` | `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` |

The harness connects FireRed's `ReadFlashId` boundary to the two bytes returned by mGBA's actual `GBASavedataReadFlash`, in little-endian order. It stubs the physical GBA save bus, Flash setup descriptors, Flash timer, scheduler and memory bank. It uses C11, `-Werror`, and UBSan.

## Nine scoped positive/negative cases

- mGBA Flash1M + ID command produces Sanyo `0x1362`: FireRed selects its LE descriptor, marks Flash available and initializes the timer.
- mGBA Flash512 + ID command produces Panasonic `0x1B32`: FireRed selects fallback, reports Flash unavailable and does not initialize the timer.
- mGBA AUTODETECT with erased-bank bytes and ID command: no matching descriptor.
- Flash1M with no ID command: ordinary bank data instead of ID, so no match.
- Direct injected Macronix `0x09C2` and Sanyo `0x1362`: both accepted.
- Direct injected `0xFFFF`, `0x0000`, and near-miss `0x1363`: all rejected.

Every case checks the chosen descriptor and function pointers, `gFlashMemoryPresent`, timer initialization count and SRAM wait-state field.

This is stronger than independent source assertions because the three actual functions execute together. **It still cannot prove the full runtime sequencing** from ROM-header detection through mGBA's initial Flash write, nor hardware timing, real bank switching, a FireRed save round trip or any new expanded ROM compatibility.

## Remaining closure and accounting

Unresolved: `GBAOverrideApplyDefaults` → `GBASavedataInitFlash` → `GBAMemoryStore8` → Flash unlock/ID command writes → physical bus → FireRed save recovery, plus ROM build and real emulator execution. The separate compiled header-override and Flash-reader packets cover two earlier isolated boundaries.

Newly machine-processed unique source files: **0**, shortfall from 1,000 target: **1,000**. Newly registered complete-file analyst candidates: **0**. Independently approved: **0**. Previously registered prepared candidates: **113**, subject to later authoritative reconciliation. All Phase 1 gates remain `FAIL_INCOMPLETE`; Phase 2 untouched.
