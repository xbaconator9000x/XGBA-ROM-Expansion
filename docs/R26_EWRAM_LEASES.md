# R26 — generation-checked EWRAM borrow, pin and release

**Stage:** implementation submitted, awaiting exact-head R26 CI; never label
native evidence as passing until both portable and original Emerald jobs pass.

## Problem

R20–R23 correctly track WORLD/BATTLE phase ownership of one linker-protected
16 KiB Emerald EWRAM arena, but that original owner/epoch pair has **no
borrow count**. If a loader attempts a phase switch while another routine
is still reading compressed sprites or map bytes, a bare epoch update can
make an old pointer unsafe. R25 protects native host MMIO writes against
armed DMA source aliases, but does not govern game CPU consumers.

## Implementation

New portable `integration/common/xgba_ewram_lease.h`: owner, monotonic
generation, eight individually tracked borrow slots, serial-bearing
owner/generation tokens. Owner changes reject with `XGBA_LEASE_BUSY`
while any pin lives. Duplicate release and stale tokens fail closed.
Generation/serial overflow and slot exhaustion fail closed rather than
silently wrapping. There is no new arena and no return of the existing
protected 16 KiB to Emerald's allocator.

Original Emerald `XgbaR20ClaimWorldArena` and
`XgbaR20ClaimBattleArena` now use this gate. World map and opponent sprite
asset-loading paths borrow the corresponding owner during their source MMIO
and descriptor construction, validate, and release. Old R23 proof ABI fields
and external resource IDs remain unchanged; the new guest proof counters
are appended.

Under the **R26-specific original-game fixture**, each of eight map-pack
loads and eight opponent compressed-graphic loads tries a forbidden phase
switch while holding its own borrow. The game must observe
`XGBA_LEASE_BUSY`, then release before legitimate phase transitions.
The genuine game must still finish its original four double battles, three
overworld returns, 8 overworld pack requests and 8 compressed graphics
requests. The host reads only appended game-authored proof fields and
independent original-game EWRAM/BG VRAM proofs.

**Limits:** These are *scoped source-loader* leases. It does not yet pin a
renderer pointer for the full time an asynchronous VRAM DMA might need it,
nor provide a three-map cache, dynamic heap reclamation, or general-purpose
CPU-store protection. Remaining work: pin/release at the actual renderer
DMA/decompressor callbacks and a real third-map eviction/reacquisition test.

## Evidence gates

* Portable C lease lifecycle test must compile with `-Werror` and pass.
* Pinned original source-built Emerald/mGBA R26 suite (R23 12 original tests
  plus 5 specific R26 borrow checks) must execute successfully at exact head.
* Original R23 and R24/R25 regression jobs must remain green where affected.
* Record the complete native CI SHA, run, 8 genuine LCD captures and proof
  before marking R26 verified. Never cite portable unit tests as native
  emulator proof.
