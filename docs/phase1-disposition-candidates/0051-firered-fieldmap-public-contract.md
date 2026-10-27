# Analyst whole-file candidate 0051 — FireRed field-map and collision interface

**ANALYST-PREPARED ONLY; no independent review.** Pinned source [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/fieldmap.h](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/fieldmap.h), Git blob SHA-1 `639e329a9a0f721abd7e40001228859cb9466005`. All **57 authored lines** inspected (58 split lines including final newline).

## Complete-file disposition

| Lines | Source semantics |
| --- | --- |
| 1–4 | Include guard and global type dependency |
| 6–13 | Primary/total tile and metatile capacities **640/1024**, primary/total palette capacities **7/13**, max and virtual map data size **0x2800** |
| 15–23 | **8** tiles per metatile; map buffer border offset **7**, derived width **15** and height **14** for view/border coverage |
| 25–26 | External backup map layout `VMap` and `Route1_Layout` declarations |
| 28–44 | Map-grid ID/behavior/layer/elevation/collision read/write, border selection, camera, connection map lookup, tint and metatile attribute APIs |
| 45–55 | Impassability setter, camera movement, VRAM/palette transfers, map initialization and saved-game initialization |
| 56–57 | Camera focus setter/getter and guard closure |

The numeric capacities and buffer offsets are **source constants**, not a claim of safe arbitrary map size or expanded runtime memory. Collision, metatile behavior, layer type and elevation are separate interfaces; an editor's JSON mask cannot be assumed equivalent to the native packed grid representation.

## Dependencies and open evidence

The implementation in pinned `src/fieldmap.c`, native `MapLayout` and `MapConnection` structures, `mapjson` generated data, Porymap's packed metatiles and FireRed save/reload are required consumers. Check `MAX_MAP_DATA_SIZE` bounds, camera/border coordinates, native collision and layer bits, ROM/map object generation, both compiler variants and emulator behavior. No implementation-level, compiled or runtime certification or independent review. **Phase 1 FAIL_INCOMPLETE.**
