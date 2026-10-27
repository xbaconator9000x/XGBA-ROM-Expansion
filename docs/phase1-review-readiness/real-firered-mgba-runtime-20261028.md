# Phase 1 P0 — real pinned FireRed cartridge / mGBA runtime save probe (2026-10-28)

**Status: EXPERIMENTAL / FAIL_INCOMPLETE.** The workflow must finish at the exact branch head before any runtime claim can be made. A passing frame probe is not equivalent to a verified native in-game save/reload.

## Immutable source and dependency closure

- FireRed: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. Native build uses `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9`.
- Emulator: `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`. Build `mgba-perf` and link a separate probe against the compiled pinned `libmgba`.
- Relevant FireRed save producer/consumer: `src/save.c`, `src/load_save.c`, `include/save.h`, flash bank/timer implementation and startup initialization. Source blobs for `src/save.c` and `include/save.h` are explicitly verified before compilation.
- Relevant emulator owners: `src/gba/core.c`, `src/gba/gba.c`, `src/gba/savedata.c`, `src/gba/overrides.c`, `include/mgba/core/core.h`, `include/mgba/internal/gba/savedata.h`, and file-backed VFS implementation.
- Producer → file: source-built FireRed cartridge header, compiled save-sector serialization, Flash 128 KiB file, emulator savedata command bus. Consumer → startup save-status read and physical Flash reload. The probe reads `gSaveFileStatus` and `gSaveCounter` using addresses from the **same compiled FireRed ELF**, not assumed offsets.

## Test matrix and honest limitations

The workflow constructs six 128 KiB deterministic Flash fixtures: empty, valid slot 0, both slots valid, an out-of-range sector ID 14, mixed counters in slot 1, and a damaged newer slot with intact older slot. The zero-filled payload is synthetically checksum-valid, not an authentic player save. It also constructs a header-mutated ROM with a recalculated GBA header checksum and preserves an unchanged-header control.

The actual emulator is asked to execute 180 frames for each fixture. The Flash program/verify probe uses **host-driven cartridge-bus writes while the real ROM is loaded**; it checks the file on disk and a second emulator instance. That is a real emulator savedata-persistence test, **not proof that FireRed's own SaveGame code successfully executed**. A 180-frame startup probe alone cannot prove the game reached save recovery, nor can a synthetic valid sector prove the save is semantically loadable. The `gSaveFileStatus` and `gSaveCounter` observations are diagnostics until tied to a verified save loader execution trace.

**Failure conditions:** any source identity mismatch, ROM compilation failure, emulator build failure, malformed-fixture hang, Flash persistence mismatch, or missing symbol fails CI. Do not classify these as Phase 1 approvals.

## Required follow-on evidence

1. Establish source-built FireRed save-loader entry and return execution (symbol breakpoints or instrumented trace) for each fixture, rather than relying on frame advance alone.
2. Verify exact Flash program/erase behavior **from FireRed instructions**, not only host-driven bus writes.
3. Verify recovery chooses the expected older slot, and prove that malformed sector IDs are rejected or trigger a documented runtime fault. Do not infer either from the host AddressSanitizer witness.
4. Extend to repeated cold boots, actual in-game save creation, and Porymap Qt save/reopen with injected write errors.
5. Review all evidence independently and retain `FAIL_INCOMPLETE` until all inventory, semantic, build, runtime, save, editor and regression gates are satisfied.

## Accounting

Previously machine-triaged source identities: **14,721 / 14,721**. Newly machine-indexed distinct identities: **0**, shortfall against 1,000 target: **1,000**. Registered analyst-prepared complete-file candidates: **113** (subject to authoritative register reconciliation). New registered complete-file reviews: **0**. Independent approvals: **0**. No Phase 2 implementation.
