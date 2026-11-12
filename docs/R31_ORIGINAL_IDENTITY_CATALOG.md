# R31 — source-derived original map identity catalogue (implementation and acceptance)

**Implementation branch:** `phase3/r31-original-identity-catalog-20261112`.

## Invariant: never renumber the ROM's maps

The real game's `mapGroup`, `mapNum`, `gMapGroups` and `gMapLayouts`
are the authority. An R31 entry is only a mapping from an **original**
identity to a separately named, SHA-256 checked sidecar resource. Selected
external resources do not require editing the base game's map IDs, warps,
scripts, save location fields or original map table. Unselected maps continue
through the original Emerald `gMapGroups[group][map]` lookup.

The native acceptance fixture source-generates its ROM-resident catalogue
from the pinned original Emerald `data/maps/map_groups.json`,
`data/maps/<map>/map.json`, `data/layouts/layouts.json`, actual original
map grids and borders, and four explicitly selected external packs. It
validates lengths, original geometry, connection references, external
resource names and the existing 16 KiB EWRAM / two 8 KiB physical slots.
No source map is silently reindexed or moved. Its binary-search secondary
index is **not** a new map number; it only maps original identities to
internal resource descriptors.

R31 also generates preferred already-selected neighbours from original
connection graph edges for safe two-slot prefetch. It replaces R30's
Littleroot/Route101/Oldale/Route102 lookup branches in the R31 native guest
integration with a generic identity resolver, while keeping prior R19–R30
modes available. Native acceptance keeps R30's seven true Emerald D-pad
positions, byte-for-byte source/EWRAM/backup-grid comparisons, seven
actual LCD PNGs, and disabled-provider zero-source-read witness.

**Limits:** Source-driven generation is currently an original decomp-built
Emerald adapter, not automatic discovery of unknown binary ROM hacks.
Universal already-modified ROM patching, arbitrarily large simultaneous
neighbour sets, arbitrary tiled resources, stock emulators and physical
hardware are not established. The number of external catalogue entries is
independent of the two fixed physical cache slots but the existing RAM
and map-engine geometry restrictions still apply.

## Source and executable checks

- [Guest resource resolution](../integration/emerald/xgba_r19_connected_maps.inc)
- [Portable identity lookup](../integration/common/xgba_original_map_catalog.h)
- [Source-derived catalogue generator](../tools/xgba_r31_map_catalog.py)
- [Portable strict-C identity tests](../tests/test_xgba_r31_original_catalog.c)
- [Source-metadata negative cases](../tests/test_xgba_r31_catalog_generation.py)
- [Original source-built Emerald twelve-case acceptance](../tests/test_xgba_r31_emerald_catalog.py)
- [Native CI workflow](../.github/workflows/xgba-r31-original-identity-catalog.yml)

Native proof status and exact-head CI links must be added only after
successful execution; the presence of this code alone is **not** acceptance.
