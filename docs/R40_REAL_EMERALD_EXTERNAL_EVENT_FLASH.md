# R40 — Native original Emerald externally supplied event script and real Flash

**VERIFIED and merged 12 November 2026.** [PR #108](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/108), merged commit [f8eeb37](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/f8eeb37971a4ad7364877bcf67f99d9d7b7fec5f).

## Evidence

- [Exact-head R40 native original Emerald event test](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43231301825): **10/10 passed**.
- [Exact-head consolidated FireRed and Emerald native regressions](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43231301842): both native game jobs passed, plus source/memory assertions.
- [Repository privacy audit](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43231301826): passed.
- The R40 CI artifact contains original 240×160 native Emerald LCD frames and a counts/provenance report, but **no ROMs, saves, extracted assets or user binaries**.

## What is demonstrated in actual GBA execution

1. Build pinned original `pret/pokeemerald` `MODERN=1`, patch only the test adapter in temporary source and restore originals, remove the *original* Littleroot map grid and Petalburg secondary tileset from the executable and load them over the existing XGBA mGBA MMIO bridge. Preserve original EWRAM bounds and existing R18 Flash save.
2. Put a **new nine-byte, authored, fixed-format Emerald script** into the external XGBA SHA-256-checked sidecar, beyond 32 MiB. The script uses original opcodes: `setvar 0x40FE 0x5A39`, `setflag 0x08F0`, `end`. It is **not** precompiled into the Emerald executable.
3. After original Emerald field initialization, copy the resource ID to actual EWRAM, fetch its bytes into EWRAM from the validated external provider, check every opcode/operand byte against the test policy, then call Emerald's **native `RunScriptImmediately`**, which dispatches via its real script command table, not the Python R39 host sandbox.
4. Check that original saveblock `VarGet(0x40FE)` and `FlagGet(0x08F0)` changed, and request original Flash save via its regular `TrySavingData` path. Close the native mGBA process.
5. Reopen in a fresh native mGBA process, call real `LoadGameSave` and `CB2_ContinueSavedGame`, reacquire external map resources and check **the actual in-game flag and variable persisted without reexecuting the external script**.
6. On a *separate first boot*, corrupt the external script file while leaving the signed manifest SHA unchanged. Verify that the provider refuses it, the guest interpreter is not invoked, and the game's save-request counter remains zero. mGBA can still allocate an erased Flash backing file without `TrySavingData`; backing-file creation alone is not interpreted as a saved game.

## Exact technical boundaries

This completes a narrow but *real* prerequisite for mixed-source scripts: original Emerald can consume sidecar bytecode in gameplay and persist the resulting game state across cold boots. It does **not** establish compatibility with independently modified Team Rocket Edition scripts, Heart & Soul engine callbacks, warps, trainer battles, custom tables, custom save layouts, species maps, persistent multiverse parties, or stock emulators.

The user's actual three locally owned BPEE-family ROM files (16 MiB Emerald, 32 MiB Team Rocket Edition, 32 MiB Heart & Soul) also underwent an independent **private host-only** read-only all-byte audit: **80 MiB, 5,120 individually addressable 16 KiB pages, 60,000 deterministic random windows, zero mismatches with a 32 KiB cache**. The audit used the exact user-provided bytes but was **not native execution**, did **not** use R36's full import format, and did not upload any ROM or save. Original game-code headers alone do not prove engine semantic compatibility.

## Next major experiment

Proceed to the user's **actual Emerald + Team Rocket Edition 3.06 + Heart & Soul 2.0.6** three-game integration attempt. Combine R32 full-source imports (Emerald and the public Heart & Soul source) and R36 original ROM binary preservation for private Team Rocket Edition; keep all original data, original numeric identities and source namespaces. Verify collision/conflict reports, native isolated resource fetches, then deliberately attempt cross-world runtime interactions and document incompatibilities. Never claim single-playable-game compatibility until **gameplay** has actually been exercised in a pinned emulator and verified by screenshots, battle/warp/Flash tests.
