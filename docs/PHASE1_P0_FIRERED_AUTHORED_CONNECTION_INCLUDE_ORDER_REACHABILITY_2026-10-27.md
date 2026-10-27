# Phase 1 P0 — authored connection-include order reaches invalid iterator arithmetic

**27 October 2026 · SOURCE-GROUNDED PINNED-INPUT WITNESS · NOT APPROVED.** FireRed pin: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. This dossier strengthens the existing whole-file `mapjson.cpp` candidate by joining the comparator to the **actual pinned authored input and ordinary build consumer**. It does not establish a full-generator crash, a ROM/runtime failure, a Qt editor defect, or an independent whole-file approval. Phase 1: `FAIL_INCOMPLETE`, independent approvals `0/14,834`.

## Immutable source identities and anchors

| Pinned FireRed path | Git blob SHA-1 | Relevant anchors |
| --- | --- | --- |
| `tools/mapjson/mapjson.cpp` | `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5` | 436–484 (`generate_groups_text`, `generate_connections_text`), 489–587 (other generated groups/IDs and `process_groups`) |
| `data/maps/map_groups.json` | `8c382f504d208286161903244772c93138cd7662` | `group_order`, all named group arrays, `connections_include_order` |
| `map_data_rules.mk` | `b32b85a91d9460642345ca983c37d165e820741f` | 1–33 (generated `connections.inc`, `groups.inc` and `maps.o` dependencies) |
| `data/maps.s` | `fc88d8fc2521e92db22264bf6cf33966fda977ba` | 1–14 (`data/maps/connections.inc` assembler inclusion) |
| `asm/macros/map.inc` | `83ef472c926ce767c9133ab9bd6922280b38bb2d` | 3–8 (map constant split into group/index bytes) |

All blob identities and the authored JSON counts below were read from the **exact upstream commit**, not current upstream `main`. These files are inputs to this cross-file trace, not newly independent-reviewed complete files.

## ORD-001 — missing-order branch is reachable from ordinary pinned authored data

`generate_connections_text` first flattens every map listed under `group_order`, then reads `connections_include_order`. When that array is nonempty it calls `std::sort` over **all** map names. For either comparison operand not found in the optional order list, the comparator evaluates:

```cpp
connections_include_order.begin() + numeric_limits<int>::max()
```

The pinned `map_groups.json` contains **43 groups and 425 distinct listed map names**; its `connections_include_order` contains **63 distinct names, all present among those 425**, leaving **362 authored map names absent** from the optional order. There are no duplicate map names in the flattened groups and no duplicate order entries. Therefore this is **not merely a hypothetical malformed user input**: the ordinary pinned input satisfies the sort condition and supplies many omitted operands. Advancing a vector iterator by `INT_MAX` when the vector has only 63 elements is outside its valid iterator range; subsequent comparisons cannot be certified under standard C++ iterator rules.

This is a **source-level reachability finding**. It is **not** evidence that the release build crashes or that an actual ROM was miscompiled. The existing isolated debug-iterator fixture at `tools/fixtures/mapjson_partial_connection_order_debug.cpp` reproduces the expression, not the full pinned `mapjson` executable. Do not conflate its debug-iterator assertion with observed production failure.

## ORD-002 — exact output affected, and output *not* affected

`process_groups` invokes `generate_connections_text` and writes `data/maps/connections.inc`. `map_data_rules.mk` declares that file as a `maps.o` prerequisite and runs `mapjson groups firered` from `map_groups.json`; `data/maps.s` includes the resulting assembler file. Thus the sorting path is on the ordinary **build-time producer → generated assembler include → native object** chain, not on the in-game connection lookup path.

The sort controls the **order of per-map `connections.inc` includes**, potentially changing placement and pointer addresses of compiled connection records. It does **not** reorder the connections *within* an individual map: that separate per-map generator iterates the map JSON connection array in authored order (same `mapjson.cpp`, 188–209). Nor does it change map group/index IDs: `generate_map_constants_text` independently assigns `map_index | (group_index << 8)` from the unsorted `group_order` and each group's map list (521–557). A future fix to the comparator must not accidentally change those two separate semantic orders.

**Interoperability obligation:** treat group/index ID assignment, per-map connection entry order, and global include/link placement as **three distinct provenance channels**. Never infer stable authored connection IDs from incidental ROM addresses, and never mistake a global include-order correction for a per-map connection reordering.

## Reproduce the authored-input witness without compiling or changing upstream

From a clean checkout at `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`:

```sh
git rev-parse HEAD
git hash-object tools/mapjson/mapjson.cpp
git hash-object data/maps/map_groups.json
git hash-object map_data_rules.mk
git hash-object data/maps.s
python3 - <<'PY'
import json
from pathlib import Path
j = json.loads(Path("data/maps/map_groups.json").read_text())
names = [name for group in j["group_order"] for name in j[group]]
order = j["connections_include_order"]
assert len(j["group_order"]) == 43
assert len(names) == len(set(names)) == 425
assert len(order) == len(set(order)) == 63
assert not set(order).difference(names)
assert len(set(names).difference(order)) == 362
print("groups=43 maps=425 ordered=63 omitted=362")
PY
```

Expected upstream blob hashes are in the table. The census assertions are **not** a substitute for an independent whole-file review. A fixture or checker that assumes these exact counts must be updated and re-reviewed when the pinned source revision changes, not silently reused against a new pin.

## Fail-closed acceptance requirements

1. Compile and execute the **actual pinned** `mapjson groups firered` command on a disposable output directory with the unmodified authored JSON, both with ordinary compiler settings and debug iterators/sanitizers; capture compiler version, exit status, stderr and generated include SHA-256. Do not claim this step has been run.
2. Establish a **defined** total comparator order for omitted names, including a deterministic tie-breaker if stable binary layout is required; review proposed behaviour separately. This is a review obligation, **not** an authorization to change upstream or implement Phase 2.
3. Diff generated `connections.inc`, `groups.inc`, `map_groups.h` and per-map connection entries before and after any eventual fix; prove group/index constants and per-map connection order remain invariant.
4. Verify assembler and linked native map pointer/layout bytes for original and modern FireRed build variants. Preserve the separate Porymap source-project and mirrored-connection identities from `PHASE1_P0_PORYMAP_FIRERED_CONNECTION_ABI_2026-10-27.md`.
5. Have an independent reviewer inspect the entire affected source file and consumers; feed only authenticated approvals through the real mapping gate. **No review signoff or approval credit is recorded here.**

**Disposition: P0 authored-input reachability established at source level; actual full-generator execution, compiled-byte comparison, runtime/editor interoperability and independent review remain OPEN. Phase 1 stays `FAIL_INCOMPLETE`; no Phase 2 work.**
