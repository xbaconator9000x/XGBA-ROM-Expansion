# Phase 1 P0 — compiled mGBA ROM-header override decision boundary

**Status: isolated compiled source-function witness / FAIL_INCOMPLETE.** No native mGBA executable, FireRed ROM boot, full emulator, external save bank or independent approval is established by this packet.

## Exact source identity

- Upstream: `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`
- Function: `GBAOverrideApplyDefaults` from `src/gba/overrides.c`
- Exact Git blob SHA-1: `566968162b29c90167199ef43f3d7a99248798e8`
- Reproduction: `python3 tools/phase1_mgba_override_compiled_branch_matrix.py --output phase1-evidence/mgba-override-compiled.json`
- CI: `.github/workflows/phase1-firered-mgba-flash-identification.yml`, which also runs the prior 11-blob source-contract witness.

The Python checker downloads (or accepts `--source` for) the exact pinned C file, verifies Git blob identity, extracts the **unaltered actual function body**, and compiles it as C11 against small instrumented stubs for its external `GBAOverrideFindConfig`, `GBAOverrideFind` and `GBAOverrideApply` boundaries. A 12-case executable fixture checks branch selection and call order, using UBSan. The stubbed default lookup recognizes `BPRE` only; this is intentionally **not** a test of mGBA's real override database or its application side effects.

## Test matrix and implications

1. Unknown game code with no recognized marker follows ordinary default lookup; it does not force Flash1M in the fixture.
2. Known `BPRE` game code without a recognized marker follows the stubbed default lookup, which supplies Flash1M.
3. Unknown game code with the exact lowercase `pokemon red version` marker at `0x108` and an unrecognized CRC takes the ROM-hack branch: Flash1M, RTC and VBA compatibility.
4. The `pokemon emerald version` marker takes the same branch.
5. `AXVE` at `0xAC` also satisfies the ROM-hack predicate, even with no text marker.
6. A CRC from the pinned known-Pokémon table suppresses the heuristic even if the text marker is present. A separate default lookup may still apply; **CRC membership does not itself guarantee Flash1M**.
7. A known `BPRE` ID and known CRC take the default path, not the ROM-hack branch.
8. A known `BPRE` ID with a recognized marker but unknown CRC takes the ROM-hack path *before* ordinary default lookup.
9. The marker is case-sensitive.
10. A configuration override can change the heuristic's proposed save type, as represented by an explicit stub.
11. The multicart early-return branch preempts the heuristic and chooses SRAM.
12. Null ROM does not invoke override lookup or application.

These are compiled checks of the **actual pinned decision function** under instrumented dependencies, not independent verification of mGBA's real configuration parser, ROM loading order, save-chip state machine or first-write timing.

## Producer → consumer → runtime closure still open

`ROM header (0xAC/0x108) + CRC` → `GBAOverrideApplyDefaults` → `GBAOverrideFindConfig / GBAOverrideFind` → `GBAOverrideApply` → `GBASavedataInitFlash` → `GBASavedataReadFlash` → `FireRed IdentifyFlash`.

The current fixture tests only the central decision function. Before approval, compile or execute the actual dependency implementations and exercise baseline and mutated-header FireRed ROMs in the pinned mGBA runtime, including no override, explicit Flash1M, savedata bank promotion, chip-ID reads, and persisted 128-KiB save data. The FireRed/mGBA flash-ID source packet remains the companion evidence.

## Accounting and gates

This adds **zero** new machine-triaged unique source files (the original 14,721-file machine pool was already exhausted), **zero** complete-file analyst candidates and **zero** independent approvals. The 1,000-file run target therefore has a **1,000-file shortfall**. The authoritative registered prepared-candidate baseline remains **113**, unless independently changed by another worker and reconciled. Every Phase 1 gate stays `FAIL_INCOMPLETE`; Phase 2 is untouched.
