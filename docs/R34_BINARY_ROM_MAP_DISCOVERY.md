# R34 — Binary-only Emerald-family map discovery and complete structured map extraction

**VERIFIED / MERGED · 12 November 2026.** [PR #96](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/96) · [merged code `781e42b`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/781e42b95e4f394acae8c6e8833164113248bf0b). **4/4 exact-head workflows successful**, including 13/13 original synthetic ROM tests, repository privacy audit, actual FireRed Flash cold restart and actual original Emerald four-battle regression. [Public synthetic-binary CI #43192543372](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43192543372). Real Team Rocket ROM data and derivative assets were inspected and exported **privately only**; they are not embedded in GitHub CI tests or artifacts.

**Scope:** Begin importing source-game data directly from an existing
modified binary GBA ROM, without requiring its decompilation sources or
hardcoding its internal map table offset.

The importer inspects a private user-owned ROM read-only, validates the
GBA header, finds ROM-addressed **map group table literal references**,
then validates every header in the candidate group table, its layout,
map grid/border, event arrays, connections and tileset descriptors using
the documented original Emerald structure. This is not a header/title-only
engine identification. Candidates fail closed on malformed pointers,
inconsistent groups, invalid dimensions, out-of-bounds arrays or ties.

For an accepted binary, **ALL** validated original maps are catalogued,
with **original (group,number) identities preserved**. The optional local
export packages every fixed-length map header, layout, border and grid,
map events and fixed event arrays, map connections and tileset descriptors
into many existing SHA-256-checked XGBA v1 sidecars. There is no curated
hand-picked map list. Each exported segment retains an original ROM
offset, length, (group,map) and a stable binary resource key. Outputs
belong to the user's machine; copyrighted source bytes or ROM files
must NOT be committed to this public repository or uploaded into CI.

## Exact user-supplied private binary experiment (12 November 2026)

Against one **privately supplied unofficial English Team Rocket Edition
3.06 GBA image** (not uploaded or published), local read-only structural
inspection succeeded, finding **75 map groups, 1,778 original map
headers, 1,666 distinct map-layout pointers, 9,410 object-event records,
4,399 warps, 1,378 coordinate events, 2,923 background events, and 567
map connections**. All 1,778 candidate headers passed the scanner's
structural pointer/array checks. The map table had 19 independent ROM
pointer references in the inspected binary.

A complete opt-in export then wrote **16,854 fixed-length map-related
source segments (3,495,580 raw copied bytes) into 66 XGBA v1 shards**.
Every shard was re-read using the SHA-256 checking reader. The original
input ROM was not changed. **These are structural validation results,
not evidence of runnable Team Rocket gameplay or of correct semantics
for every event script.** The source ROM's hash, asset contents, and
all produced shards remain private and are not public test fixtures.

## Important compatibility limitations

The script entry-point **pointers** are recognised, but variable-length
custom script bytecode is **not** decoded or copied. Tileset descriptors
are exported, but their referenced graphics/palette blocks are not
safely bounded by generic pointers, so those bytes are **not** claimed
as exported. Pokémon species, moves, abilities, trainer tables, custom
battle effects, world flags, Fly travel and persistent cross-game save
state remain outside R34. The input binary layout is an
**Emerald-family structural candidate**, not verified executable
interoperability. Some modified games may use other map layouts; this
scanner should refuse unrecognised formats rather than guess.

## Local usage

Inspect a user-supplied binary without changing it:

    python3 tools/xgba_r34_binary_maps.py /private/TeamRocket.gba --out /private/scan.json

Extract every identifiable fixed-length map structure into local sidecars:

    python3 tools/xgba_r34_binary_maps.py /private/TeamRocket.gba \
      --source-id rocket --export /private/rocket-map-sidecars

The output is versioned and SHA-256-bound to the **exact source ROM**;
it is a separate binary source namespace from Emerald and Heart & Soul.

Public [synthetic ROM tests](../tests/test_xgba_r34_binary_maps.py) exercise
13 cases including full-byte roundtrips, structural bounds, original map
ID stability, relocated table discovery, corruption, false-positive
rejection and prevention of overwriting the user's ROM.
[CI workflow](../.github/workflows/xgba-r34-binary-map-import.yml).

**No public native triple-game traversal or cross-ROM battle has been demonstrated.**
