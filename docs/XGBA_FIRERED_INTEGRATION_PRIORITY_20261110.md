# XGBA Phase 2 experimental implementation — FireRed first, reusable GBA architecture

**Priority authorised 10 November 2026:** cease using complete 14,834-file semantic mapping as a prerequisite for a working prototype. Reuse GBATEK, pret/pokefirered, mGBA Matrix, Hex Maniac Advance pointer models and XGBA's existing pointer-contracts. Keep older evidence, pins, histories and review gates unchanged; do not falsify the legacy mapping completion state.

**Important generality:** XGBA is an emulator-first general GBA platform. FireRed is the **first adapter/test vehicle**, not the only eventual target. Existing ROM hacks and unknown binary variants remain inspection-only until specifically fingerprinted and tested; see `docs/XGBA_PLATFORM_COMPATIBILITY_SCOPE_2026-10-29.md` on main. No in-place transformation of unknown ROMs.

## New implementation cycle — code, not mapping

R1/R2/R3 have delivered host-side streaming, deterministic packing and staged buffers; 22/22 tests passed at baseline `a0edc50d6ba8241f3a5920e0115bc8dfc6d8c24d`. They are **not independently approved**, nor integrated into FireRed or mGBA.

The next three finite, automatically supervised assignments are:

| Package | Source + tests | Real implementation acceptance |
|---|---|---|
| **R4_FIRE_RED_NATIVE_ADAPTER** | `tools/xgba_resource_firered_adapter.c` + `tests/test_xgba_resource_firered_adapter.py` | Source-backed, opt-in *native C* FireRed adapter for one specific **static graphics resource**. Compile against clean pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` in a temporary checkout, with an explicit ABI and bounded copy into RAM/VRAM. Use real FireRed source symbols/headers rather than guessing addresses. Must demonstrate a real compiled callsite/pointer contract and two negative runtime tests, with an unchanged/no-extension fallback. Do not simply make a Python mock or report source inventory. |
| **R5_MGBA_OPTIN_PROVIDER** | `tools/xgba_resource_mgba_adapter.c` + `tests/test_xgba_resource_mgba_adapter.py` | Isolated opt-in mGBA *native C* provider for R1/R2/R3 resource access, compiled into or directly linked with actual pinned `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b` source. Make a host-provided asset reachable through a versioned handshake; preserve ordinary 32 MiB ROM/Matrix/EEPROM/Flash/DMA paths, verify mismatch/invalid input failures. No modifications to pinned checkout committed upstream. No host-only simulator falsely described as an emulator integration. |
| **R6_FIRERED_MGBA_SMOKE** | `tools/xgba_resource_integration_smoke.py` + `tests/test_xgba_resource_integration_smoke.py` | Build and execute a reproducible FireRed-based **synthetic external-resource demonstration** in actual mGBA headless runtime, with a resource located beyond 32 MiB in the sidecar. Prove one real in-game load/access reaches a bounded live GBA-visible buffer. Verify positive and at least four failure/legacy regression paths. Produce reproducible command, logs and hashes; do not distribute copyrighted ROM bytes. **Stop/declare BLOCKED** if actual compiled game/actual emulator proof is unavailable. |

**Prioritisation:** integrate one low-risk static graphical asset first, where data is copied into a bounded native buffer and is not retained as a script PC, audio track or DMA source. No blanket pointer rewriting, no "infinite ROM pointer" claims. Keep original GBA CPU ROM address-space constraints. Specific source-backed pointer/lifetime issues are investigated only when the relevant integration touches them. Resource IDs are never raw CPU pointers.

**Source reuse:** `docs/PHASE1_P0_FIRERED_MAP_SCRIPT_POINTER_ABI_2026-10-26.md`, `docs/FIELD_POINTER_ROLES_v22.md`, `docs/RESOURCE_LIFETIMES_v23.md`, `docs/PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md`; `pret/pokefirered`, mGBA, and Hex Maniac Advance. Check licensing before reusing third-party implementation code; no unlicensed copying. No paid APIs beyond included Copilot Pro capacity, $0 billed overages.

## Completion estimate: two distinct denominators

**First playable expanded FireRed demonstration: ~25% as of 10 Nov 2026**, an approximate milestone estimate, not a validated time forecast. Model: existing hardware/decomp baseline 10%; host sidecar/pack/bridge 20% (15 credited pending review); FireRed runtime hook 20%; mGBA opt-in integration 20%; actual playable expanded demo 20%; compatibility/regression 10%. Remaining steps are disproportionally difficult and may require revision of this percentage.

**Reusable general GBA expansion platform:** much less complete, and *not* 25% just because FireRed groundwork exists. Other engines, existing modified ROM hacks, editor/patcher interop and Android support remain out of scope of the first demo. Do not invent a precise completion percentage for the general platform without a defined acceptance matrix.

**Completion gate:** neither R4 nor R5 is "delivered" merely because source text exists; actual native compile/test checks must pass. R6 cannot receive a pass without real runtime evidence from executable mGBA. GitHub gate status is `DELIVERED_AWAITING_INDEPENDENT_REVIEW` only; external whole-file semantic approvals remain zero. No auto-merge, no editor compatibility promises, no unstated hardware claims.
