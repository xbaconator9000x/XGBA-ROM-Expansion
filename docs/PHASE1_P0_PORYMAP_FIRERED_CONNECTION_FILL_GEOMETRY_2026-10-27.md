# Phase 1 P0 — map-connection offset crosses editor, generator and native fill geometry

**27 October 2026 · EXACT-PINNED CROSS-TOOL SOURCE TRACE + SYNTHETIC GEOMETRY · NOT APPROVED.** FireRed pin `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; Porymap pin `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. This documents an unresolved **source-level geometry precondition**, not a claim that any of the 63 stock compiled connections violates it. Independent approvals **0/14,834**, Phase 1 **FAIL_INCOMPLETE**.

## Pinned source-to-native ABI

| Exact pinned source | Git blob SHA-1 | Anchors and role |
| --- | --- | --- |
| Porymap `include/core/mapconnection.h` | `40713d3a26157fce7a36465858e8273c78dc12f6` | 17, 35–36, 62: signed `int` connection offset |
| Porymap `src/core/mapconnection.cpp` | `d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4` | 155–169: setter and mirrored negation |
| Porymap `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | 1390–1399: serialized `connectionObj["offset"] = connection->offset()` |
| FireRed `tools/mapjson/mapjson.cpp` | `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5` | 188–209: textual `connection direction, offset, map` generation |
| FireRed `asm/macros/map.inc` | `83ef472c926ce767c9133ab9bd6922280b38bb2d` | 137–153: `.4byte offset` native representation |
| FireRed `include/global.fieldmap.h` | `e2828ec0cb1439718e830fbef4366770b3b77b1c` | 91–107: signed layout dimensions; 177–189: native `u32 offset` and connection-list ABI |
| FireRed `src/fieldmap.c` | `41567772299000ba5855419e5c39ad9373a34c20` | 103–112: virtual map dimensions; 129–190: connection initialization/copy; 192–345: cardinal clipping |

**Serialization boundary:** Porymap stores the offset as a signed C++ `int`, writes it as a JSON number, FireRed's generator emits it as assembly text, and the assembler encodes the offset as a four-byte word. The native `MapConnection` field is `u32` despite signed authoring. `InitBackupMapLayoutConnections` copies it into a local `u32 offset` and passes that to cardinal helpers taking `s32 offset`. Negative authored values rely on the target compiler's unsigned-to-signed conversion behaviour when the value exceeds `INT_MAX`. **Do not normalize away the signed offset or assume the C type declaration alone proves portable signed semantics.**

## GEO-001 — the cardinal fill functions do not reject disjoint offsets

`InitMapLayoutData` creates a `(mapWidth + 15) × (mapHeight + 14)` virtual buffer and asserts its total area does not exceed `0x2800`. The subsequent cardinal fill functions are responsible for clipping connected-map rows/columns into that buffer. The area assertion is **not a connection-overlap validation**.

For `FillSouthConnection` (fieldmap.c:192–229), choose a **synthetic** current map width 20, connected width 20 and authored offset +40. The source computes `VMap.Xsize = 35`, `x = offset + 7 = 47`, then `width = VMap.Xsize - x = -12`. It passes that negative width to `FillConnection` (173–190), which constructs a destination pointer and calls `CpuCopy16(src, dest, width * 2)` for each of seven rows. The same synthetic widths with offset -40 produce `x2 = 33` (past the 20-cell connected row) and `width = -13`. An offset 0 control produces `x = 7`, `x2 = 0`, `width = 20`.

The analogous `FillWestConnection`/`FillEastConnection` branches (272–345) can compute negative **height** for sufficiently disjoint vertical offsets. A negative height causes the `for (i = 0; i < height; i++)` copy loop not to execute, but `FillConnection` still forms its source/destination pointers first; this is a separate pointer-precondition issue, not proof of a large DMA/copy. For `FillNorthConnection`, `y2 = connectedHeight - 7` (231–269) is negative when the connected map is shorter than seven cells. West similarly computes `x2 = connectedWidth - 7` (272–306).

**Classification:** source-level conditional invalid geometry, with a transparent arithmetic witness. It is **not** a full compiled GBA call, runtime crash, out-of-bounds write observation or a finding about stock authored offsets. The precise effect of a negative byte count depends on the selected `CpuCopy16` implementation and ABI; that edge is not yet closed.

## GEO-002 — interoperability obligations

1. A JSON/editor round trip must preserve the *signed authored offset* independently of the native four-byte representation, and must not infer a connection's identity from its physical ROM pointer. The earlier mirrored `INT_MIN` negation finding is a **different** boundary.
2. Validate overlap and source/destination clipping separately for south, north, west and east, including short neighboring maps and disjoint offsets. A valid virtual-map area alone does not prove these calls safe.
3. Audit the **actual 63 pinned compiled connections**, their target layout dimensions, and reciprocal offsets before asserting stock reachability or safety. Account for `connections_no_include` suppression and maps without native connection pointers.
4. Compile and inspect `CpuCopy16` call conventions under original agbcc, revision10 and modern GCC; test representative invalid/valid offsets only in a disposable harness, not by modifying authored production maps.
5. Run Porymap Qt save/reopen and mGBA map-edge transitions, with source-project JSON and generated object bytes compared independently. Obtain independent whole-file review before approval.

**Reproduce the source-anchored synthetic witness:** `python3 tools/verify_firered_connection_fill_geometry.py --self-test` exercises the geometry model and a negative source-anchor mutation. With the exact pinned FireRed and Porymap checkouts, `python3 tools/verify_firered_connection_fill_geometry.py --firered upstream/pokefirered --porymap upstream/porymap` additionally verifies both commit IDs, six Git blob hashes and producer/consumer anchors, emitting `audit-output/connection_fill_geometry.json`. The [source checker](../tools/verify_firered_connection_fill_geometry.py) is wired into [fieldmap boundary CI](../.github/workflows/phase1-fieldmap-save-boundary.yml), but **latest-head CI execution has not yet been confirmed**. No compiled/runtime result is implied.

**Reproduce arithmetic only (synthetic, not compiled):**

```python
def south(offset, connected_width=20, current_width=20):
    virtual_width = current_width + 15
    x = offset + 7
    if x < 0:
        x2 = -x
        x += connected_width
        width = min(x, virtual_width)
        x = 0
    else:
        x2 = 0
        width = connected_width if x + connected_width < virtual_width else virtual_width - x
    return x, x2, width

assert south(0) == (7, 0, 20)
assert south(40) == (47, 0, -12)
assert south(-40) == (0, 33, -13)
```

**Disposition: source ABI and synthetic geometry preconditions mapped; authored-data census, compiled copy semantics, editor and runtime gates OPEN. No new whole-file candidate or approval.**
