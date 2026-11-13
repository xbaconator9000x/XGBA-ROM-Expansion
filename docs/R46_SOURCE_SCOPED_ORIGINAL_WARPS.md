# R46 — Original three-ROM source-scoped navigation and warp routing

**13 November 2026 · implementation and private source verification.**

R45 confirmed **real original-ROM-derived graphics** loaded into a *homebrew*
ARM7 map-viewer cartridge in patched native mGBA. It did **not** make
Team Rocket Edition or Heart & Soul maps playable within original Emerald's
overworld. R46 builds the **engine-facing original map/warp routing layer**;
it must not be described as proof that the original engine is already running
cross-world navigation.

## Direct examination of the user's THREE ACTUAL original GBA files

The following read-only private trial parsed original map layouts, original
8-byte warp records, destination references, source identities and numeric map
holes from each complete source ROM. No game bytes or extracted map/warp tables
were published to this public GitHub repository.

| Original ROM | Populated maps | Map slots | Zero-pointer holes | Original warp records |
| --- | ---: | ---: | ---: | ---: |
| Emerald (16 MiB) | 518 | 518 | 0 | 1,313 |
| Team Rocket Edition 3.06 (32 MiB) | 1,778 | 1,778 | 0 | 4,399 |
| Heart & Soul v2.0.6 (32 MiB) | 560 | 1,495 | 935 | 1,434 |
| **Total** | **2,856** | **3,791** | **935** | **7,146** |

**Actual original warp destination classification (source remains unchanged):**

- **7,006** directly resolvable source-local warp references
- **96** dynamic/sentinel destinations, whose original script behavior still
  needs interpreter/engine support
- **40** destinations with an unavailable or special target warp index
- **4** destinations with missing or inactive original target maps
- **69** original warp entry coordinates outside the simple rectangular bounds
  check, requiring further compatibility/semantic inspection; do not
  automatically reclassify them as corrupted game data
- **969 pairwise same-numeric-map-ID collisions** across sources. These match
  the previous R41 enumeration: 201 three-way shared numeric IDs contribute
  603 pairwise collisions, plus 366 two-way shared identities

The 96/40/4/69 cases are **compatibility work**, not evidence that the
original games are broken. R46 deliberately rejects unresolved cases until
their original semantics are interpreted safely.

Read-only original SHA identities were rechecked against R41:
Emerald `a9dec84dfe7f62ab2220bafaef7479da0929d066ece16a6885f6226db19085af`,
Rocket `5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca`,
Heart & Soul `cdfb9e1f83f72c05cb47af40fdf5635567b1973bcb759e070ad0971f67a49191`.

## Implemented engine ABI

The new `integration/common/xgba_r46_source_warps.h` is freestanding
C11 and is compatible with a GBA-native game build. It adds:

- unique stable world/map key `(source<<16)|(original_group<<8)|original_map`
- lookup preserving original numeric IDs and legitimate absent map slots
- source-local original warp record traversal with destination source
  *inherited*, never guessed from colliding map numbers
- atomic destination and arrival-coordinate validation; no partial position
  mutation on failure
- **explicitly authorised portal** transitions between sources, not invented
  implicit links from the original ROMs
- source-labelled, checksummed portable location record with corruption and
  wrong-world rejection; this does *not* overwrite original Emerald Flash

`integration/common/xgba_r46_paged_warps.h` adds a bounded **16 KiB guest
scratch-cache** reader that can request immutable `r46.map.NNN` and
`r46.warp.NNN` data from a patched XGBA provider as needed. The actual
2,856 map descriptors occupy **45,696 bytes** and 7,146 warps **57,168
bytes**, so storing the full **102,864-byte** index in 256 KiB of guest
EWRAM would collide with the original Emerald heap. Native paged lookups
leave it in external storage, with the caller responsible for the arena lease
and SHA-verified provider callback. The index is **7 external 16 KiB
resource shards** (three map pages + four warp pages), including short final
pages. No entire index is resident in guest EWRAM.

`tools/xgba_r46_source_warp_index.py` creates those private binary
index shards from the owner's original ROM files, using the R34 validated
Emerald-family map parser. Private source data stay private; public CI
tests the same ABI against authored synthetic fixtures.

## Test scope — do not overclaim

- Native host C11 + AddressSanitizer + UndefinedBehaviorSanitizer regression:
  correct colliding keys, Emerald refusal to warp into Rocket by accident,
  deliberate Rocket → HnS portal, Rocket source-native transitions and
  checksum rejection
- Freestanding C11 compile regression and 16 KiB on-demand page reader
- Synthetic source identity/holes/warp binary serialization tests
- Actual user-owned ROM read-only 2,856-map / 7,146-warp extraction
- **Not yet performed:** an original Emerald character stepping onto an
  imported Rocket or HnS warp and physically traversing another world's
  original tileset, collision grid, script/event engine, NPCs and battles
- **Not yet performed:** original three-world progress saved/restored in
  genuine Emerald Flash while retaining original-party/inventory state

This is an enabling engine component for the next **original Emerald
overworld integration**, not a finished three-game release or another
substitute for a playable build.
