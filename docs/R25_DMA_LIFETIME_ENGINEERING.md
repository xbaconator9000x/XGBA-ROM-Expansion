# XGBA R25 — DMA source lifetime protection and cross-engine regression policy

**Status:** implementation under review; do not label verified until exact-head CI is green.  
**Base:** R24 verified in `main` (FireRed 14/14, Emerald 14/14).  
**Scope:** patched native mGBA production MMIO device, independent of FireRed/Emerald guest source.

## Root cause driving this work

The first Emerald R24 source-built test failure was **not proven EWRAM corruption**.
Its host harness read the game's 16 KiB validation record while the guest state
was still `1` (running). Diagnostic run
[43050781586](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43050781586)
showed a valid `0x4000` limit, a recorded initial request and no provider
refusal yet. The follow-up fix
[`f5256cad`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/f5256cad704f5648f518a1438f2a5a5841036ac8)
waits on an explicit guest terminal state (`3` success; `0xE24` error) for
up to 8,000 additional native frames. The final exact-head Emerald R24 CI
[43051443181](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43051443181)
passed 14/14, as did FireRed
[43051443138](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43051443138).

This is **completion ordering**, distinct from R20's genuine BG VRAM
restoration-order mismatch and R14/R19's actual EWRAM pressure. Do not classify
a guest still executing as having corrupted memory. Every future harness must
record `NOT_READY`, `COMPLETE`, `GUEST_ERROR`, and `TIMEOUT` distinctly.

## R25 implemented protection

Actual `integration/mgba/xgba_mgba_device.c` now checks **all four pinned
mGBA DMA channels** immediately before provider I/O and again before the final
EWRAM copy. An enabled DMA source (including an armed HBlank/VBlank/repeat
channel), or an actively serviced channel, is a **live reader**. The proposed
MMIO write is refused if its destination overlaps either the configured or
current DMA source footprint. Width (16/32 bit), increment, decrement and
fixed-source modes, and channel 3's 65,536-element maximum count are
considered using 64-bit endpoint arithmetic. **Mirrored EWRAM** is explicitly handled: pinned native mGBA aliases the 256 KiB backing store throughout CPU region `0x02xxxxxx`, and DMA ranges that wrap the physical buffer are compared modulo 256 KiB.

This is deliberately conservative: a wider source footprint may defer an
otherwise legal write, but an overlapping live DMA source must never silently
be overwritten. A new status `XGBA_R7_DMA_BUSY = 6` distinguishes this from
a missing resource, corrupt SHA or bad address. All previous MMIO addresses,
statuses 0–5, 16 KiB resource maximum and existing R24 tests are unchanged.
A host-side diagnostic `rejected_dma_aliases` counter records refused
commits, while provider reads and guest EWRAM bytes must stay unchanged.

No host-injected DMA or graphics is substituted for original game execution.

## Validation matrix (status does not auto-promote)

| Scenario | New R25 portable test | Original-game native DMA proof |
| --- | --- | --- |
| DMA0 immediate increment source overlaps requested buffer | Implemented | Not yet run |
| DMA1 repeat fixed-source HBlank, source pinned before first beat | Implemented | Not yet run |
| DMA2 VBlank decrement source footprint | Implemented | Not yet run |
| DMA3 repeated/current source differs from original source | Implemented | Not yet run |
| Active DMA transfer despite control register being cleared | Implemented | Not yet run |
| Non-overlapping DMA in IWRAM / disjoint EWRAM remains permitted | Implemented | Not yet run |
| Original R24 7 refusals + 256 adversarial cases intact | Compiled and run in R25 portable harness | R24 regressions must be green |
| Reuse after DMA disarmed / finished | Implemented | Not yet run |

The 19-case portable matrix also checks mirrored-source increment, decrement, wrap, full physical coverage and truly disjoint mirrored sources.

New workflow: [`.github/workflows/xgba-r25-dma-source-lifetime.yml`](../.github/workflows/xgba-r25-dma-source-lifetime.yml).
It compiles **the real production device C source** with an isolated GBA memory
shape. This is **not native mGBA DMA emulation** and cannot replace real original
FireRed/Emerald runs. The existing R24 native workflows are required as
regressions when the production MMIO device changes. Capture exact head,
passing job IDs, test counts and actual artifacts before upgrading this
status.

## Architectural follow-through (NOT implemented by the R25 DMA device guard)

1. **Guest CPU/decompression writes and DMA consumption:** this R25 check
   blocks *host MMIO commits only*. It does not prevent the original game
   from overwriting an asset source through a normal CPU store, nor does it
   prove that guest-side map-to-battle arena ownership is safe during DMA.
   Implement explicit guest-side `borrow/pin/release` semantics for those
   buffers, with forced eviction refused until all consumers retire.
2. **Native in-flight DMA integration:** use pinned real source-built Emerald
   and FireRed to arm DMA from an external-resource staging address and request
   a conflicting resource before completion. Verify guest MMIO busy status,
   exact source bytes, DMA destination bytes, completion/disarm recovery and
   unchanged redzones. Keep game-initiated DMA separate from host test state.
3. **Repeated and aliasing DMA:** exercise HBlank/VBlank, audio FIFO and
   decrement/fixed-source configurations, including savestate rollback mid-DMA.
4. **Three-map cache eviction:** exercise 3+ simultaneous map packs, valid
   generation invalidation, deterministic evictions and reacquisition before
   renderer access. Existing R23 is *map-vs-battle phase* eviction, not a
   general third-map LRU proof.
5. **Clear completion protocol:** instrument every native test with terminal
   state and bounded progress trace, not a fixed frame-count assumption.
   Distinguish runner dependency/network faults from game/runtime failures.

## Acceptance rules

- Never claim R25 native in-flight DMA is verified based on portable unit
  testing or R24 game runs without DMA contention.
- Never modify a previous milestone's historical proof to relabel later code
  as already tested; preserve original run SHA, source pin and test class.
- Record any failure's proof-state, requested address/capacity, DMA source
  range/control/count and whether provider I/O or EWRAM mutation occurred.
- Advance only after exact-head R25 portable CI **and** native FireRed/Emerald
  R24 regression gates pass. Native DMA contention requires its own genuine
  acceptance run before it may be reported as proven.
