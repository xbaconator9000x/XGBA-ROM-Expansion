# RHH 1.17.2 source map and tileset pages

This work is deliberately restricted to RH-Hideout `pokeemerald-expansion`
`expansion/1.17.2` at `79dd436920845ebc145577649de624f65298c209`.
It is compiled independently as Emerald, FireRed and LeafGreen; the other
XGBA world-integration branch and private game assets remain untouched.

## Authentic asset acquisition

`tools/xgba_expansion_map_pages.py` reads the original `data/layouts/layouts.json`
and exact `data/layouts/*/map.bin` from the pinned source checkout, preserving
the original 1-based `gMapLayouts` identity and every map word. An optional
full-size, indexed 4bpp PNG is packed in GBA 8x8 tile order. Only an exact
512-tile Emerald or 640-tile FRLG **primary** tileset is accepted; shorter
secondary PNGs are *not* silently zero-filled or called complete. Resources
are divided into verified 16 KiB pages with SHA-256 manifest entries; the
final page may be shorter. No user ROM data is stored in GitHub.

For the source-built game ROM from the reversible adapter, for example:

```sh
python3 tools/xgba_expansion_map_pages.py \
  --source upstream --target emerald --layout LAYOUT_LITTLEROOT_TOWN \
  --primary-png data/tilesets/primary/general/tiles.png \
  --output /tmp/xgba-private-source-pages
```

For FireRed/LeafGreen use `LAYOUT_PALLET_TOWN` and
`data/tilesets/primary/general_frlg/tiles.png`. These examples are
**source packaging gates**, not proof of native map or tile rendering.

## Normal game integration

The reversible source adapter injects into the actual RHH
`InitMapLayoutData`, `CopyTilesetToVram` and
`CopyTilesetToVramUsingHeap` paths. It binds verified original layout
IDs as `rhh.m.<layoutId:04x>.<page:02x>`,
`rhh.p.<layoutId:04x>.<page:02x>`, and
`rhh.s.<layoutId:04x>.<page:02x>`. The resident 16 KiB
page is copied synchronously into the original map grid or BG VRAM before
reuse. FRLG's 20 KiB primary graphics can span 16 KiB + 4 KiB.

On an invalid or missing page, the map grid is restored from the original
ROM copy, or the entire original graphics loader runs. Tileset external
VRAM writes require `DISPCNT_FORCED_BLANK` and never leave a queued DMA
pointer into the single reusable page. Unsupported oversized layouts,
dynamic layout identities and incomplete source tilesets use the native
source fallback. Map IDs, tile IDs and original resource definitions
are not rewritten.

## Acceptance boundary

- Source-adapter and sidecar packing unit tests check real loader placement,
  pointer invalidation, bounds, source identity, byte preservation, large
  FRLG tiling, unsupported paths and restoration.
- The CI ARM job compiles all three original upstream games, derives real
  map/primary tileset resources locally, validates manifests and discards
  private temporary pages.
- This **does not yet prove a gameplay map was rendered from an external page**.
  Missing evidence includes native transitions into the selected layouts with
  enabled/disabled comparisons, secondary tileset parity, battle resources,
  original Flash cold save/restart, LCD/GIF evidence of those interactions
  and subsequent cache churn.

No private ROM, build output, save, source map data, tileset binary or
user-owned artwork should be uploaded to public GitHub.
