# R27 — large-map geometry and capacity stress

**Status:** development / exact-head CI required before claiming original-game pass.

## What R27 really tests

The original pinned Emerald `src/fieldmap.c` has a fixed
`sBackupMapData[MAX_MAP_DATA_SIZE]` of **0x2800 (10,240) u16 cells**, and
copies map data into a connection/border grid with **15 extra columns and
14 extra rows**. Large external files do not remove this runtime cap.
Each synchronous XGBA v1 provider request is still limited to **16,384
bytes** of protected physical EWRAM. Large maps can independently breach
either limit.

Two positive stress shapes, **64×64** and **128×32**, each have 4,096
metatile cells (8,192 bytes grid). With the **complete original Petalburg
secondary tileset** and original resource header/border, each requires
**13,636 bytes**, within one XGBA transfer. Original backup-grid
requirements are **79×78=6,162** and **143×46=6,578** u16 cells,
respectively. The pinned original Emerald renderer, collision/map grid,
BG VRAM and real D-pad input must be executed through the existing
native mGBA integration; the host independently reads and verifies
*every one of the 4,096 cells*, the entire exact resource SHA and
decompressed external tile graphics before/after movement. Full 240×160
original mGBA LCD frames must be captured, not synthetic screenshots.

These are **synthetic stress shapes derived from original 20×20
Littleroot metatiles**, not historic shipped 64×64 Pokémon Emerald
maps. The game's actual original engine renders them. Its original
20×20 ROM data and Petalburg tileset are removed from the ROM in the
test fixture and supplied from >32 MiB external storage.

## Hard refusals

- **96×96** and **128×64** exceed the original internal backup-grid
  bound and must be rejected before either guest pointer is exposed.
- An otherwise valid 64×64 map with an oversized secondary tileset
  must be rejected before transfer, even if map *geometry* fits.
- An exact **16,384-byte** request is allowed under the existing R24
  contract, but **16,385 bytes** must fail closed.
- Invalid, wrapped or boolean dimensions must not enter the planner.
  All capacity maths is performed before allocation/CPU rendering.

## What remains unverified

R27 alone does **not** provide arbitrary gigantic connected maps,
chunked asset streaming, a dynamic backup-grid, three-or-more
simultaneously connected maps, remote sidecar latency, or safe
continuation after a deferred DMA transfer is already in flight.
These need separate original-game native proofs, explicit residency
policies and retained original R23–R26 regression checks.

## CI evidence

On successful exact-head CI, record source commit, pinned original
Emerald/mGBA versions, per-shape real map bytes and backup-grid
capacity, C-side guest-proof fields, 4 genuine LCD PNG frames and
native full-grid verification. Never mark an unrun scenario as
passed. [Workflow](../.github/workflows/xgba-r27-huge-map-stress.yml).
