# Phase 1 — pinned mGBA ROM reuse boundary and 32 MiB alias proof (2026-11-01)

**Status: source-grounded architecture constraint; NOT an implementation, semantic approval, native run, expanded-ROM test, or hardware compatibility claim.** This note supplements `reuse-first-dependency-license-matrix-20261101.md`. It does not replace the pinned upstream source, modify mGBA, relax any review gate, or enter Phase 2.

## Exact pinned source evidence

Source repository: [mgba-emu/mgba at `fd9dc5c2cbf234365068855851107e762fc6211b`](https://github.com/mgba-emu/mgba/tree/fd9dc5c2cbf234365068855851107e762fc6211b). All four files carry or are part of the original mGBA MPL-2.0 source; preserve upstream attribution and applicable notices if adapted.

| File | Git blob SHA-1 | Relevant original lines and observation |
| --- | --- | --- |
| [`include/mgba/internal/gba/memory.h`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/memory.h#L27-L89) | `0aad912613e726560d06bbdbf6061986e69e5842` | Regions `0x08..0x0D` are ROM0/ROM1/ROM2 plus extended halves; `GBA_SIZE_ROM0 = 0x02000000` (32 MiB), `BASE_OFFSET=24`. |
| [`src/gba/gba.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/gba.c#L425-L484) | `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e` | `GBALoadROM` clamps original ROMs larger than `GBA_SIZE_ROM0` to a 32 MiB mapping and sets `pristineRomSize = GBA_SIZE_ROM0`; non-power-of-two mapping also uses 32 MiB. |
| [`src/gba/gba.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/gba.c#L553-L578) | same | `GBAApplyPatch` returns without applying a patch when `patchedSize > GBA_SIZE_ROM0`. |
| [`src/gba/memory.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L338-L349) | `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc` | Active instruction region for all six ROM region selectors points to the **same** `memory->rom` and `romMask`. |
| [`src/gba/memory.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L425-L434) | same | ROM 32-bit data loads index `memory->rom` with `address & (GBA_SIZE_ROM0 - 4)`; byte loads at lines 701–713 use `address & (GBA_SIZE_ROM0 - 1)`. |
| [`src/gba/core.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/core.c#L60-L72) | `6bfc518bb8899205c07d1d0fc091a287cb42f874` | Core memory-map descriptors expose three **32 MiB waitstate windows**, not three independently addressable banks. |

## Source-derived collision and size boundary

For ordinary cartridge reads with offset `x` where `0 <= x < 0x02000000`, the original ROM address mask yields:

```text
(0x08000000 + x) & 0x01FFFFFF = x
(0x0A000000 + x) & 0x01FFFFFF = x
(0x0C000000 + x) & 0x01FFFFFF = x
```

For example, ROM reads at `0x08001234`, `0x0A001234`, and `0x0C001234` select the same underlying ROM byte offset `0x1234`, though waitstate timing and special cartridge/EEPROM cases differ. The six ROM regions therefore **do not** provide 96 MiB of distinct conventional ROM storage. This is an address-mask/source proof, not an emulator execution result.

The original loader truncates an ordinary ROM larger than 32 MiB; the patch application path rejects a patch whose resulting ROM exceeds 32 MiB. An oversized ROM accepted by some other host tool does not establish that the pinned mGBA can execute all of it.

## Reuse-first decision and concrete acceptance obligations

**Reuse unchanged:** mGBA ARM decoder/interpreter, standard 32 MiB cartridge semantics, timing, and existing GBA save/debug infrastructure as an evidence baseline. Do **not** rewrite a second emulator merely to expand resources.

**Do not assume:** changing a linker script, enlarging an input file, adding a host-side allocation, or treating `0x0A/0x0C` as additional ROM banks solves expansion. They do not bypass the original source-level mask and loader cap. Do not conflate host-only resource access with hardware cartridge addressability.

**Smallest justified future engineering options (not implemented in Phase 1):**
1. A versioned, explicitly bank-switched cartridge contract with defined selection mechanism and correct CPU fetch, data loads, DMA, prefetch/cache, reset, savestate, debugger, checksum, patch and persistence behaviour; **hardware feasibility remains unproven**.
2. A host-only sidecar/resource virtualisation design, clearly labelled emulator-specific and not claimed as stock-GBA-compatible.
3. A build-time split/streaming strategy constrained by the original hardware address window and proven FireRed consumer/producer contracts.

**Required future proof before claiming success:** exact original-source-to-compiled loader and memory trace; deterministic alias/boundary and 32 MiB/32 MiB+1 load/patch tests; bank identity across CPU, DMA and debugger; savestate/restart and save persistence; native emulator execution; and, only if claimed, real hardware/Flash tests. Keep each evidence tier separate. Review MPL-2.0 obligations for any changed upstream files and license compatibility of combined distributions.

**Reviewer status:** this document is an analyst architecture handoff, `NEEDS_REVIEW`, not a per-file whole-source Copilot receipt. It does not alter the three existing `COPILOT_REVIEWED/PASSED` records or the historical `FAIL_INCOMPLETE` gate and 0/338 P0, 0/14,834 total legacy approvals.
