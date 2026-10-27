# Phase 1 P0 — Porymap map-group save strips FireRed connection-order provenance

**27 October 2026 · PINNED SOURCE AND AUTHORED-INPUT TRACE · NOT APPROVED.** Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`; FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. This is a distinct **project-level serialization dependency** following the earlier native connection ABI and compiled generator investigations. It is not a demonstrated Qt round trip, ROM-byte difference, or runtime fault. **Phase 1: FAIL_INCOMPLETE; independent whole-file approvals: 0/14,834.**

## Pinned source identity and ownership

| Repo | Exact file | Git blob SHA-1 | Relevant source anchors |
| --- | --- | --- | --- |
| Porymap | `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | 1923–2050 reader; 876–912 writer; 1474–1486 global save |
| Porymap | `src/editor.cpp` | `34112f6355b13d9381de7188624c36e5efeba151` | 83–110 current/all save |
| Porymap | `include/config.h` | `539c5f3d416d22d847020cd324726b33725e5437` | 301–320 reset/default; 396 config field |
| Porymap | `src/config.cpp` | `9264f99bb18e0a725ef023f514c00df529d1d28d` | 1011–1012 config override; 1119 serialization |
| FireRed | `data/maps/map_groups.json` | `8c382f504d208286161903244772c93138cd7662` | complete authored group and order arrays |
| FireRed | `tools/mapjson/mapjson.cpp` | `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5` | 458–485 optional sort and generated includes |
| FireRed | `map_data_rules.mk` | `b32b85a91d9460642345ca983c37d165e820741f` | 22–23, 30–31 generated map assembly dependency |

All source identities above are from exact pinned commits, not floating upstream branches. These are *partial-file dependency traces*, **not** new complete-file analyst review candidates.

## MGR-001 — ordinary editor save is a map-group metadata rewrite

Porymap's `ProjectConfig::reset` sets `preserveMatchingOnlyData = false` (config.h:320), unless overridden by the `preserve_matching_only_data` setting (config.cpp:1011–1012). On project read, `Project::readMapGroups` consumes `group_order` and each named group array, then **removes `connections_include_order`** from the remaining custom JSON object when that flag is false (project.cpp:1923–2050, specifically 2044–2050). The map-group writer reconstructs the group arrays and appends only the retained `customMapGroupsData` (876–912); it does not reconstruct the removed connection-order field.

This is reachable through **Save Current**, not just an explicit map-list edit: `Editor::save(currentOnly=true)` calls `Project::saveMap` for the current map and then `Project::saveGlobalData` (editor.cpp:91–109). `saveGlobalData` unconditionally calls `saveMapGroups` (project.cpp:1474–1481). **Save All** also invokes the same global writer (project.cpp:1315–1326). Thus, subject to a successful open and write and the default setting remaining false, an ordinary save will serialize `map_groups.json` **without** its original `connections_include_order` metadata.

This is **source-level conditional serialization evidence**, not a Qt save/reopen observation. A configured `preserve_matching_only_data=true` changes the outcome. The writer's `OrderedJsonDoc::dump` result is not checked locally (project.cpp:908–911); write failures and partial writes require separate validation.

## MGR-002 — actual pinned FireRed data constrains the binary-risk claim

The pinned authored JSON has **43 groups, 425 unique maps, 63 explicitly ordered connection-include names and 362 omitted names**. Crucially, comparing the authored arrays establishes that **the 63 ordered names already occur in exactly the same relative order in the flattened `group_order` arrays**. Their first and last zero-based positions in the flattened list are **188 and 253**; there are 191 omitted names before or interleaved through that span. No relative pair of the 63 names is inverted.

FireRed's `generate_connections_text` sorts all 425 names only when `connections_include_order` is nonempty (mapjson.cpp:458–485). With the key absent, it emits includes in flattened group order. This changes the **generator's selected ordering path and textual include placement**, and loses the explicit source-order provenance. However, for this exact pinned JSON the 63 ordered maps' relative sequence is invariant. The prior full-generator debug-iterator abort on the partially specified order is also avoided in the *absent-order* branch, but this does not establish an appropriate fix.

**Do not claim that removing the key necessarily changes the compiled `maps.o` or ROM for this pin.** Earlier modern `maps.o` equivalence testing covered an *expanded* order list, not this default-Porymap stripped-key round trip. The 362 omitted names must not be assumed to be semantically inert for every future input or build variant without checking their emitted assembler and pointer consumers. The project metadata loss is real under the traced condition even when a particular native binary happens to remain equivalent.

## MGR-003 — implications for authoritative project/ROM merges

The `connections_include_order` field is **source provenance**. It must be tracked independently from the 425 group/index map identities, the 63 maps with non-null native connection lists, and the per-map connection array order. A merge that accepts a rewritten Porymap project as authoritative should preserve the original field when it is semantically meaningful, or flag intentional loss; it must not silently infer that absence means no authored ordering ever existed.

For the pinned data, an explicit order-list removal preserves the 63 relevant names' relative order, but the field itself is not round-trip invariant. For future or modified source JSON where the explicit order differs from flattened group order, the transformation can change native connection-list placement. That future-input statement is a conditional consequence of the pinned generator, **not an observed failure**.

## Reproducible witness and required gates

`tools/phase1_porymap_mapgroups_roundtrip.py` now checks **15 exact Git blob identities**, **34 guarded source anchors and 34 fail-closed in-memory mutation controls** across the map-groups metadata path, mirrored dirty/save scope and signed-offset boundary, plus the complete pinned JSON cardinality/order relationship. [Exact-head CI #40428373090](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40428373090) **passed** at `957c88e7ef2b203df8e856d4e561bafae40555d5` ([artifact #12699779954](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40428373090/artifacts/12699779954)). It writes `audit-output/porymap_mapgroups_roundtrip.json`. The separate `.github/workflows/phase1-porymap-mapgroups-roundtrip.yml` checks out both immutable upstream commits and preserves the witness artifact. The JSON transformation is **explicitly a model** of Porymap's guarded removal/append path, not an executed Qt editor.

To close this subsystem: (1) execute Porymap Qt open → Save Current → reopen with the default and preservation-enabled setting, including on-disk JSON comparison; (2) build FireRed with the actual original and stripped-key JSON under both original agbcc and modern compiler variants, compare generated includes, `maps.o` and linked ROM pointer bytes; (3) exercise mirrored connections, duplicate directions, saved edits on a different map and map-group reorder; (4) verify exact native runtime direction selection and source metadata preservation in editor/ROM import; (5) obtain independently authenticated **whole-file** reviews. Existing tests or this source checker cannot sign off those gates.

**Disposition: cross-tool serialization metadata loss established from pinned source; pinned active connection order invariance established from authored arrays; Qt round trip, stripped-key compiled comparison, runtime and independent reviews OPEN. Phase 1 remains FAIL_INCOMPLETE.**
