# XGBA R25 — DMA source lifetime protection and cross-engine regression policy

**Status:** R25 portable and source-built original FireRed/Emerald armed-VBlank-DMA3 tests verified at head `5d729f9af4ab338e44dbae1834643befba692186`; PR #80 awaits merge. Native mid-transfer DMA remains untested.  
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

## Executed exact-head verification (12 November 2026)

| Test classification | Game or implementation | Result and permanent run link |
| --- | --- | --- |
| Genuine ARM-source-built native game | FireRed, original DMA3 VBlank armed, conflicting external resource request, refused without guest EWRAM mutation, disarm and recovery | **15/15 passed**, [native run #43067407151](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43067407151), [two LCD PNGs + machine proof artifact #13876512589](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43067407151/artifacts/13876512589) |
| Genuine ARM-source-built native game | Emerald, same DMA3 VBlank sequence, independent guest and pinned engine build | **15/15 passed**, [same native run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43067407151), [two LCD PNGs + machine proof artifact #13876851400](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43067407151/artifacts/13876851400) |
| Production mGBA MMIO C compiled with lightweight portable host shape | All four channels; fixed/increment/decrement, deferred/active, source physical mirroring, disjoint allowed and recovery | **19/19 cases passed**, plus original R24 unit contract and 256 adversarial malformed ranges; [run #43067407140](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43067407140) |
| Real original engine regressions | FireRed and Emerald R24 complete 16 KiB source/rejection suites | **14/14 each**, [FireRed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43067407094), [Emerald](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43067407279) |
| Real original engine and source guard regressions | FireRed Flash cold restart, Emerald four-battle resource arena eviction and source/memory contract | **3/3 jobs passed**, [consolidated run #43067407092](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43067407092) |

All these runs executed code at source head `5d729f9af4ab338e44dbae1834643befba692186` or an unchanged implementation predecessor. Documentation-only changes made after this head must not be mistaken for re-executed native testing at the new documentation commit.

### What original-game R25 actually proves

- Original FireRed and Emerald code directly programs DMA3 VBlank control, 32-bit source and destination registers: the guest, not the host, arms the DMA.
- A validated game-initiated MMIO transfer targeting the source EWRAM is refused as `XGBA_R7_DMA_BUSY=6` while the deferred DMA3 channel remains armed.
- The entire requested 16,384-byte EWRAM destination and external guard bands survive the refusal; no provider read is performed for that conflicting request.
- After disabling DMA3, the original game can complete the valid 16 KiB resource fetch, and both engines continue their original main loops.
- The native tests use source-pinned mGBA and original compiled FireRed/Emerald, not stubbed CPU or host-injected DMA state.

**Not covered by that proof:** an actively executing DMA transfer interrupted between its beats; concurrent CPU overwrites; active LZ77 decompression; HBlank/repeat/fixed/decrement in original ARM games (those mode checks are presently portable only); high-contention savestate rollback; third-map working-set eviction.

## Architectural follow-through (NOT implemented by the R25 DMA device guard)

1. **Guest CPU/decompression writes and DMA consumption:** this R25 check
   blocks *host MMIO commits only*. It does not prevent the original game
   from overwriting an asset source through a normal CPU store, nor does it
   prove that guest-side map-to-battle arena ownership is safe during DMA.
   Implement explicit guest-side `borrow/pin/release` semantics for those
   buffers, with forced eviction refused until all consumers retire.
2. **Truly in-flight DMA integration:** the original-game **armed, deferred VBlank** case has now passed in both engines. Next schedule a source lease while a transfer is already making forward progress (multiple beats), and prove actual DMA destination bytes and source stability across a commit attempt. Do not equate an armed yet-unscheduled channel with a mid-beat transfer.
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

- The R25 original-game **armed, deferred VBlank** DMA refusal is verified. Never claim this is equivalent to true **mid-beat** DMA protection, general guest-side allocation leases or CPU-write safety.
- Never modify a previous milestone's historical proof to relabel later code
  as already tested; preserve original run SHA, source pin and test class.
- Record any failure's proof-state, requested address/capacity, DMA source
  range/control/count and whether provider I/O or EWRAM mutation occurred.
- Original R25 native game-initiated contention and R24 regression gates all passed at the documented exact source head. Preserve run IDs/SHAs and require fresh native acceptance whenever these code paths change. Further lifecycle claims require separate tests.
