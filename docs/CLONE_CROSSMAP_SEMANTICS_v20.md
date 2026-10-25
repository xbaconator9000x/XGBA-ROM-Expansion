# Semantic contract v2.0 — cross-map object clones and off-layout placements

**Pinned source:** `pret/pokefirered` at `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.

## Source-backed execution chain

- [Original mapjson compiler, `tools/mapjson/mapjson.cpp` lines 245–252](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/tools/mapjson/mapjson.cpp#L245-L252) (Git blob `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5`) emits `clone_event` with the current map's x/y and symbolic target `target_local_id` / `target_map`.
- [Assembler macro `asm/macros/map.inc` lines 41–52](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/asm/macros/map.inc#L41-L52) (Git blob `83ef472c926ce767c9133ab9bd6922280b38bb2d`) uses `OBJ_KIND_CLONE` and writes signed x/y in 16-bit fields and the source map/group selector.
- [Runtime `src/overworld.c` lines 405–434](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/overworld.c#L405-L434) (Git blob `339014da46ae8543143edc99ab72bf7496203a0d`) fetches the referenced source map and object by `targetLocalId-1`, copies the object template, and replaces the *clone instance's* local ID and x/y.
- [Object spawning, `src/event_object_movement.c` lines 1326–1367](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/event_object_movement.c#L1326-L1367) (Git blob `8e82824d376d566dbff5ac863f1013d10ad5ec8b`) resolves a clone back to the source object's template while placing it using the *clone-specific* x/y plus `MAP_OFFSET`.

## Evidence from pinned map compiler and source manifests

[Passing FireRed map audit](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40176887229) verified **425 maps**, **9 clone-event references**, **9 clone events outside nominal source-map bounds**, **9 uniquely resolved target map/local IDs**, and **zero unresolved clone targets**. All off-layout object events were clones, not ordinary objects.

Examples include `CeladonCity` x=-7 to `MAP_ROUTE16`, `Route7` x=-8 to `MAP_CELADON_CITY`, `Route21_North` y=-3 to `MAP_PALLET_TOWN`, and `Route2` y=85 to `MAP_VIRIDIAN_CITY`. See `map-evidence/clone_crossmap_semantics.csv` for all nine blob-linked entries.

## Contract: XGBA-EDITOR-CROSSMAP-CLONES

1. **Preserve** cloned objects' original signed off-layout coordinates. Never clamp them to the local layout or discard them as invalid merely because x/y are outside bounds.
2. Preserve the target map/group/local ID, source and clone identities, script and appearance properties, and the distinction between authoring-time template and on-map cloned instance.
3. A map resize/merge must translate clone-instance coordinates and target references consistently. An exporter must regenerate the equivalent `clone_event` macro rather than flattening the instance into a normal independent object.
4. Treat a missing target object or unresolved map ID as a genuine validation error. Never replace an unknown target with a default object.
5. If importing an arbitrary compiled ROM without corresponding authoring JSON, *inferred* clones need provenance and uncertainty markers before editing.

## Limit

The 9/9 test proves source-level target identities and native map compiler compatibility, **not** runtime object animation or map-editor round-trip fidelity. No whole-file semantic signoffs; Phase 1 remains `FAIL_INCOMPLETE`.
