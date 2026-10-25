# Phase 1 pinned native mGBA bank, peripheral, DMA and savestate regression — executable closure record

**Date:** 2026-10-26 (Australia/Brisbane). **Scope:** source-pinned baseline mGBA behaviour characterization only. **Result: 25 / 25 checks PASS; 0 failed.** The broader Phase 1 gate remains **FAIL_INCOMPLETE**, with **zero independently approved whole-file semantic dispositions**. No XGBA runtime or unlimited ROM architecture has been compiled, implemented or demonstrated.

## Primary reproducible evidence

- [Successful GitHub Actions CI run #40203666311](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40203666311)
- Pinned mGBA source commit: `fd9dc5c2cbf234365068855851107e762fc6211b`, checked via detached `git rev-parse HEAD` plus exact Git blob hashes for `src/gba/memory.c`, `src/gba/cart/matrix.c` and `src/arm/arm.c`.
- Committed C fixture: [`tests/mgba_bank_boundary.c`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/blob/main/tests/mgba_bank_boundary.c)
- Executed test source SHA-256: `6d7f590a2f4d53ec154184f16dd35748febdb70e979f5a8eb65f6b544e57dde1`. This file was compiled against the native mGBA library using *the same private compile definitions* as mGBA itself.
- Machine-readable CI `compiler-evidence/mgba-native-boundary-result.json`: `positive_checks_passed=25`, `positive_checks_failed=0`, `native_probe_exit_code=0`, `external_XGBA_banking_implemented=false`.
- Full downloaded workflow evidence archive SHA-256: `5517b53f6a6d11674139969d4572f98e955e876a62bb3edecd792882698f8129`; JSON outcome SHA-256: `1c3e44cb87900fb7e0c4b8007d7115f8e86c39f3da61af4eca558cf25060c46c`; native runtime log SHA-256: `3187cc36975857579b358ce1686bac7c3d6e98c3a85c939b92feb7aab83bee76`.
- CI saved the logs, full compiler database, dependency results and pinned source hash evidence as the `xgba-phase1-mgba-compiled-semantic-evidence` artifact.

## Native behaviours now exercised successfully

| Contract area | Executed evidence | Status |
| --- | --- | --- |
| Standard unmodified ROM path | Conventional 32 MiB non-M cartridge, ARM fetch/data, Thumb fetch/data | BASELINE_NATIVE_PASS |
| Native Matrix opt-in | 64 MiB synthetic image marked `M` at 0xAC exposes native 16 MiB cartridge aperture | BASELINE_NATIVE_PASS |
| Native Matrix bank translation | Distinct external physical pages mapped to the same permitted virtual slot; ARM and Thumb fetched expected bytes on explicit refetch | BASELINE_NATIVE_PASS |
| Native virtual-window guards | Invalid 8 KiB virtual-window mapping and zero-size mapping rejected | BASELINE_NATIVE_PASS |
| 16-bit ROM2_EX peripheral arbitration | No EEPROM uses ROM bytes, EEPROM overrides ROM, 32-bit access takes distinct path | BASELINE_NATIVE_PASS |
| e-Reader and EEPROM priority | e-Reader register overrides cartridge bytes; EEPROM takes priority over e-Reader for 16-bit ROM2_EX when both predicates apply | BASELINE_NATIVE_PASS |
| DMA3 EEPROM transfer | Native immediate 16-bit DMA3 reads EEPROM and writes 0x0001 into EWRAM, clears DMA enable after completion | BASELINE_NATIVE_PASS |
| Matrix local savestate | Native 16-slot metadata serialization/deserialization restores physical bank backing and ARM/Thumb refetches | BASELINE_NATIVE_PASS |
| Whole GBA savestate | `GBASerialize`/`GBADeserialize` restores the selected bank after intentional mutation, and ARM/Thumb data reads match restored bank | BASELINE_NATIVE_PASS |

**DMA scheduler analysis:** A single direct `mTimingTick` was initially insufficient because mGBA keeps a deferred `reroot` queue. The test was corrected to take bounded native scheduler turns. Recorded run: scheduled DMA3 event at cycle 3, first native tick promoted the deferred queue, the second serviced a unit, the third completed DMA; EWRAM destination was `0x0001`, `activeDMA=-1`, DMA enable cleared. No emulator DMA callback or cartridge code was patched.

## Two confirmed native limitations — NOT closed as safe XGBA implementations

1. **Stale CPU prefetch after native Matrix remap.** The runtime fixture observed `native_remap_leaves_prefetch_stale_until_refetch=true`. Explicit ARMWritePC/ThumbWritePC reloads matched backing-bank data afterward. Future XGBA must define and test atomic bank-switch boundaries, prefetch invalidation or deferred switch semantics and ARM/Thumb/DMA coherence. A green baseline test is *not* proof that unsafe live remapping is fixed.
2. **Out-of-bounds physical mapping accepted by native Matrix.** The runtime fixture observed `native_matrix_accepts_physical_range_past_end=true`. Pinned `_remapMatrix()` does not validate `paddr + mapped_bytes` against total backing length or verify the `VFile` seek/read return codes. Future XGBA must use checked-width arithmetic, fail closed on missing/short backing banks, and not modify mapping state on rejection.

These are identified implementation and negative-regression obligations for any opt-in XGBA bank controller; they remain OPEN until a real design/implementation and failing-native/passing-XGBA negative controls exist. The Phase 1 semantic record accurately maps them without proceeding prematurely to Phase 2.

## Unclosed higher-order interoperability and full Phase 1 gates

- Real XGBA extension activation and opt-in negotiation; emulator/device/ROM-format versioning.
- Program flow while an instruction is already prefetched, transitions across 16/32 MiB mirrors, simultaneous DMA/peripheral accesses and interrupt interleavings, e-Reader EEPROM state sequences, live debugger/rewind save-state compatibility.
- Multiple emulator implementations, hardware/flashcart compatibility, editor asset generators, and end-to-end engine regression.
- Independent whole-file dispositions and full semantic-gate acceptance remain mandatory. Native characterization tests do not constitute external review signoff.

**Decision:** mark the nine original native test, five peripheral, four Matrix local state and seven further fixture-level checks as PASS only in their precise executed contexts, not universal engine compatibility. Preserve the source-pinned artifacts and keep Phase 1 `FAIL_INCOMPLETE` until the independent disposition and remaining mapping gates pass.
