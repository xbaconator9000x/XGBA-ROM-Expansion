# XGBA: mixed ROM/external assets and future virtual memory

**Status:** Architecture + 26 executable planner tests on the R15 draft branch. Actual native R14 navigation and external secondary tilesets were previously proven. An expanded GBA EWRAM bus, larger PPU/VRAM, general multi-pack streaming, and normal in-game save/restart recovery are NOT yet proven.

## Physical GBA limits

| Resource | Genuine hardware | XGBA current compatibility contract |
| --- | --- | --- |
| CPU-visible ROM | 32 MiB window per mirrored wait-state region | Keep normal ROM code and direct ROM pointers inside 32 MiB |
| EWRAM | 256 KiB (0x02000000–0x0203FFFF) | Linker-checked, shared heap-tail reservation plus save/engine scratch |
| IWRAM | 32 KiB | Remains unchanged |
| Tile-mode BG VRAM | 64 KiB | Existing tiles/map blocks count toward the budget |
| Tile-mode OBJ VRAM | 32 KiB | Existing native object tiles count toward the budget |
| Palette RAM | 512 bytes BG + 512 bytes OBJ | Each palette remains a finite native slot |
| OAM | 1 KiB | Hardware sprite attributes remain finite |

References: [GBATEK](https://mgba-emu.github.io/gbatek/) and [mGBA's memory constants](https://github.com/mgba-emu/mgba/blob/master/include/mgba/internal/gba/memory.h).

This is the actual hardware contract, not an attempt to emulate extra memory. BG/OBJ split differs in bitmap display modes, so those modes require a distinct memory profile.

## Mixed indoor room, including an asset at byte 67,987,873,254,192

The game can reference original ROM collision and tile data, a sidecar tile at logical offset 74, another at logical offset 67987873254192, and still more animations in separate resource packs.

**A 64-bit external storage address is not an EWRAM or VRAM address.** A stable (pack ID, resource ID, logical offset) is resolved by the host to a validated file shard or cache object. A tile at logical offset 67987873254192 might occupy 2 KiB in a particular pack file starting at physical offset 8192: no sparse multi-terabyte file is necessary. Signed 64-bit host file seeks are validated separately from unsigned 64-bit logical ranges. This mapping is a planner contract, not yet a runtime multi-pack resolver.

For every scene, register what must coexist: already visible native BG/OBJ tiles, palettes, OAM, ROM-resident objects, retained EWRAM data and temporary fetch/decompression buffers. Source origin does not reduce target VRAM consumption. If two objects must be rendered concurrently, their native footprints must be accounted for concurrently. A shared staging buffer may be reused only after the previous consumer no longer needs it.

## Mixed gym-leader battle

Three Pokémon can originate from three different locations: one from original ROM, one from external pack A, one from pack B many terabytes away in logical address space. Moves and animations can originate from pack C. However, only currently needed sprite frames, active battle effects and their palettes need native GPU residency.

The R15 mixed-source tests exercise these simultaneous sets, real per-pool capacity checks, 64-bit logical address boundaries, and bad-asset rejection. The runtime still needs native sprite/tile address allocation, DMA, palette ownership, prefetch timing and collision-free frame transitions, followed by original FireRed LCD evidence. The planner does not claim those have been implemented.

## Scene changes, saves and resets

Maintain an asset lifetime and generation/epoch model. A normal indoor/outdoor transition must explicitly retain, release, relocate or load resources. On hardware reset, EWRAM/VRAM/palette contents become invalid; their backing data has to be fetched or reconstructed even if immutable source data remains cached on the host. Native ROM pointers can remain mapped, but raw old EWRAM/VRAM addresses are not savegame identities.

A normal FireRed save should persist a stable map/party state and versioned resource identities; cold re-entry must reacquire the right external bytes. Missing or mismatched packs should lead to controlled refusal or recovery instead of corrupting the game. R14's bounded native fixture still halts if required map data is missing; safe user-facing recovery is a future integration requirement.

## Could we expand EWRAM or VRAM?

**Option A — expand virtual asset storage, cache and prefetch (current preferred strategy).** Use host disk/RAM as a virtually unlimited backing store while retaining the actual GBA 256 KiB EWRAM and 96 KiB VRAM limitations in the native guest. Load just the working set needed for a scene or animation. This is the approach compatible with the existing demonstrated FireRed engine.

**Option B — opt-in extended guest EWRAM (future emulator extension).** A modified emulator could map a new region or expose bank switching via an explicit MMIO API. This requires revisiting CPU address decoding and mirroring, DMA, pointer lifetimes, save-state serialization, heap ABI and cold boot behaviour. It cannot be assumed to work on ordinary mGBA or physical GBA. The safer initial experiment is a versioned extra-memory aperture instead of silently changing existing GBA address meanings.

**Option C — opt-in expanded guest VRAM/PPU (separate research project).** A larger host byte array alone will not let the original GBA PPU draw extra tiles or palettes. The actual renderer uses restricted tile-ID widths, base blocks, object allocations, palette indexes, OAM and display registers. Beyond those limits requires extending both guest rendering conventions and the emulator PPU, GPU snapshots and savestate behaviour. Proof must be a real native FireRed render with verified LCD output, not an allocated buffer.

These options are not interchangeable. Increased host storage is proven. Guest EWRAM and VRAM expansion remain unimplemented hypotheses until their own native acceptance tests pass.

## Reusable acceptance gates

1. Verify ROM and resource identities, SHA-256, 64-bit virtual offsets, actual file mappings and bounded transfers.
2. Compute every simultaneously resident asset and audited pre-existing engine reservation, separately for EWRAM, BG/OBJ VRAM, palette and OAM. Fail before build on overcommit.
3. Reuse buffers only when the lifecycle guarantees the old user has released the bytes. Budget transient buffers and engine save-copy scratch.
4. Validate linker allocations and actual native VRAM allocator usage. Reset invalidates guest caches and pointers; rebuild lazily or on demand.
5. Test normal FireRed save/close/continue, cross-map/battle transitions, pack loss/mismatch and frame integrity with native execution.
6. Archive verified screenshots, exact CI head, machine-readable checks and scope. Never label planner-only tests as expanded hardware or live streaming proof.

The R15 shared memory planner covers steps 1–3 at the modelling level. Actual engine integration and steps 4–6 require separate native demonstrations.
