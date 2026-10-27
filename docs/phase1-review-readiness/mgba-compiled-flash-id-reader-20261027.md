# Phase 1 P0 — compiled mGBA Flash ID reader boundary

**Status: exact pinned function compiled under dependency stubs; FAIL_INCOMPLETE.** Not a native mGBA emulator execution, a compiled FireRed ROM, or an independently approved whole-file review.

- Source: `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`
- File: `src/gba/savedata.c`
- Git blob: `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`
- Actual function: `GBASavedataReadFlash` (unmodified function body extracted after exact Git blob verification).
- Reproduction: `python3 tools/phase1_mgba_flash_id_compiled_reader.py --output phase1-evidence/mgba-flash-id-compiled.json`
- Compiler: C11, warnings-as-errors and UndefinedBehaviorSanitizer; `mTimingIsScheduled` and the bank memory are explicitly stubbed.

The 11-case matrix checks: Flash1M ID bytes `62 13`, Flash512 ID bytes `32 1B`, ID-mode address 2 falling through to current-bank data, AUTODETECT ID-mode fallthrough, ordinary bank reads, the settling-sector data-polling bit behaviour for both Q7 values, no settling override for a different sector, and ID reads taking precedence over settling. It joins the separate compiled ROM-header decision matrix in `mgba-compiled-rom-header-override-20261027.md`.

**Important limitation:** the test does not compile `GBASavedataInitFlash`, `GBASavedataWriteFlash`, the real timing scheduler, or mGBA's `GBAMemoryStore8`. It therefore cannot prove that a particular ROM's initial command sequence transitions from AUTODETECT to Flash512, nor that an actual FireRed save is rejected or accepted. The source-level contract in PR #18 describes that conditional risk; a full pinned mGBA runtime ROM boot and savedata persistence test remain required.

No source file receives an independent approval from this fixture. Newly machine-triaged files: **0** (shortfall **1,000** against target); new whole-file analyst candidates: **0**; independently approved: **0**. Existing registered whole-file candidates: **113** unless changed by separately reconciled work. All Phase 1 gates remain `FAIL_INCOMPLETE`; Phase 2 untouched.
