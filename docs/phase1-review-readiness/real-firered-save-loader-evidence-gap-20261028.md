# Phase 1 P0 independent evidence review: real FireRed save-loader reachability (2026-10-28)

**Disposition: SOURCE-VERIFIED REVIEW FINDING, NOT AN INDEPENDENT SEMANTIC APPROVAL. Gate: FAIL_INCOMPLETE.**

This packet is deliberately separate from the main Phase 1 worker's [draft PR #24](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/24) and does not edit that branch. The independent review was posted as a **COMMENT, not APPROVE**. No emulator or FireRed source code was modified.

## Exact identities and observations

- Actual source-built FireRed/mGBA probe: [CI #40525408728](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40525408728), job `122263516059`, exact branch head `b6f0cee6a4b5ec25c2eb39eaf4340b65e8da10d8`. The job passed.
- FireRed source revision: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Entire pinned `src/save.c` (964 lines), Git blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`; pinned `include/save.h`, Git blob `87fb9b615b434b58823d15688056695acda9feab`. The guard verifies complete blob identities, not just line snippets.
- [Nine observed result records](../../tests/evidence/phase1_real_rom_probe_40525408728.json) transcribed from the job's JSON log lines; the validator compares every case to the observed values and rejects duplicates, missing cases, fabricated status/counter values, changed source/commit identities and approval claims.

All nine cases advanced at least 180 real emulator frames. All nine also reported **`save_status=0` and `save_counter=0`**, including the valid-slot and corrupted-slot fixtures. The 128-KiB file-backed Flash program/reload test genuinely persisted byte `0x5A` at offset `0x40` using **host-driven** bus commands; this does not establish that FireRed's own save routine executed.

## Pinned source contract and critical evidence gap

In `include/save.h`, `SAVE_STATUS_EMPTY=0`, `SAVE_STATUS_OK=1`, `SAVE_STATUS_INVALID=2`, and `NUM_SECTORS_PER_SLOT=14`.

In `src/save.c`:
- `GetSaveValidStatus` (lines 466–582) checks both slots, selects the latest counter, and uses `locations[gSaveDataBufferPtr->id].size` in both slot loops (lines 487 and 515) **before validating that the ID is below 14**.
- `CopySaveSlotData` (lines 440–464) similarly uses `locations[id].size` and `locations[id].data` (lines 454 and 458) without a local range check.
- `LoadGameSave` (lines 803–831) invokes `TryLoadSaveSlot` on normal loading and then writes `gSaveFileStatus=result` (line 820). `TryLoadSaveSlot` invokes the two functions above.
- The generated `malformed_id14` fixture intentionally contains ID 14. The unchecked indexing is a **source-level risk if the loader reaches the malformed sector**; no crash or out-of-bounds read was observed in this test. It is not an established runtime exploit or a confirmed save-corruption bug.

The nine frame probes contain **no entry/return trace for `LoadGameSave` or its callees**. Unchanged status/counter values therefore cannot distinguish an unexecuted loader from an executed loader that leaves those values unchanged. In particular, a successful frame run is not a negative safety test of the malformed-ID path. The save-loader/recovery gate remains **unverified**, even though the emulator boot and host-driven Flash persistence gates passed.

## Required independent-review handoff

1. At the same exact pinned source/compiled ELF, obtain an executed entry/return trace for `LoadGameSave(SAVE_NORMAL)`, `TryLoadSaveSlot`, `GetSaveValidStatus` and `CopySaveSlotData`. Instrumentation must not alter the save logic being assessed.
2. With loader execution confirmed, assert `SAVE_STATUS_OK` and the expected counter on complete fixtures; explicitly distinguish incomplete/invalid slot recovery from fresh-save initialization.
3. Test malformed ID 14 with a bounds-aware witness or instrumented runtime, capture fault/rejection/continuation and validate older-slot fallback. Do not infer this from 180-frame completion.
4. Verify a genuine FireRed-initiated Flash write, a cold restart and successful in-game load, rather than treating host bus commands as a game save.
5. Obtain a separate independent whole-file disposition tied to the exact source blobs and all dependencies. Do not count this packet as prepared or approved without reconciliation into the authoritative review register.

**Accounting:** inventory 14,834/14,834 (100%); independent approvals 0/14,834 (0.0000%); previously registered substantive baseline 113/14,834 (0.7618%, subject to register reconciliation); historical machine triage 14,721 distinct identities. This packet adds **zero** to those counts. No Phase 2 implementation.
