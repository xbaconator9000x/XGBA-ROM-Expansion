# R26 — generation-checked EWRAM borrow, pin and release

**Status: MERGED and VERIFIED.** Original source-built Emerald **17/17 native** and portable source lease contract **PASS** at tested head `93aa67d9e75792cc5a2100379f2668e9bbc1f3e2`, merged main [`77e418f`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/77e418ffa10eb4052822817212935d5a769aecb1). [Native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43072910123) · [Eight original LCD PNGs and JSON proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43072910123/artifacts/13880215862).

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

## Executed results

- Original-game source pins: Emerald `731ad5bfd6e6f265508d0efcca0ba42f9dcf5881`, patched native mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`.
- [Exact-head 17/17 original Emerald native R26 + portable lease C tests](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43072910123); 8 map borrows, 8 opponent borrows, 16 attempted phase switches rejected, 8 arena generations and no remaining pins.
- [Eight original 240×160 LCD PNGs and `proof.json`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43072910123/artifacts/13880215862); GitHub Actions ZIP has finite retention, not yet permanently committed as media.
- [R23 four-battle regression](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43072910132), [R24 Emerald boundary regression](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43072910184) and [consolidated source/Flash/battle gate](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43072911064) all pass at the same tested head; R17–R22 also pass.
- Not tested by R26: persistent renderer DMA leases, third simultaneous map cache/eviction, savestate rollback during in-flight transfer, stock emulator or physical GBA.
