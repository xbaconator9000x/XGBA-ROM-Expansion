# Phase 1 P0 — Porymap connection ownership → FireRed compiled map-connection ABI

**27 October 2026 · SOURCE-GROUNDED CROSS-REPOSITORY TRACE · NOT APPROVED.** Pinned Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`; pinned FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. **Gate: FAIL_INCOMPLETE; independent whole-file approvals: 0/14,834.** This maps authoring → generated assembler → native consumers, not compiled byte validation, a Qt editor round trip, or a runtime crash.

## Exact upstream Git blob identities

| Repository | Path | Git blob SHA-1 | Relevant source anchors |
| --- | --- | --- | --- |
| Porymap | `src/core/mapconnection.cpp` | `d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4` | 19–49, 97–169 |
| Porymap | `src/core/map.cpp` | `47b279919bd4afcc76b88f9eeecd459b3452989f` | 322–381, 393–429 |
| Porymap | `src/core/editcommands.cpp` | `684d98c7ea8b2c600a5fb8888831b95723e741f3` | 571–785 |
| Porymap | `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | 488–500, 1314–1326, 1387–1403 |
| Porymap | `src/editor.cpp` | `34112f6355b13d9381de7188624c36e5efeba151` | 90–115, 1291–1333 |
| FireRed | `tools/mapjson/mapjson.cpp` | `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5` | 155–159, 188–209 |
| FireRed | `asm/macros/map.inc` | `83ef472c926ce767c9133ab9bd6922280b38bb2d` | 4–8, 138–153 |
| FireRed | `include/global.fieldmap.h` | `e2828ec0cb1439718e830fbef4366770b3b77b1c` | 177–197 |
| FireRed | `src/fieldmap.c` | `41567772299000ba5855419e5c39ad9373a34c20` | 129–170, 631–719 |
| FireRed | `src/overworld.c` | `339014da46ae8543143edc99ab72bf7496203a0d` | 706–734 |

All ten file identities were fetched from their **exact pinned upstream commits**. Source anchors are 1-based. Reproduce with `git show <pin>:<path> | git hash-object --stdin` and compare to this table; do not substitute current upstream `main`.

## CONN-001 — authored JSON is not the runtime record

Porymap `Project::loadMap` takes each `connections[]` JSON object, removes `direction`, `offset`, `map`, resolves the target constant to a map name and retains remaining fields as custom data (project.cpp:488–500). `Project::saveMap` writes the three known fields plus custom data back to `map.json` (1387–1403). This is **source-level field preservation**, not byte-for-byte JSON round-trip proof.

FireRed's pinned `mapjson` generator emits one textual `connection direction, offset, map` directive per array item, followed by a signed 32-bit count and a pointer to the list (mapjson.cpp:188–209). The assembler `connection` macro writes direction as 1 byte, 3 bytes of padding, a **4-byte offset**, two map-ID bytes and 2 padding bytes (map.inc:138–153): **12 bytes per native entry**. The map-ID macro writes group = high byte and map number = low byte (map.inc:4–8). The corresponding C structure declares `u8 direction`, `u32 offset`, `u8 mapGroup`, `u8 mapNum` (global.fieldmap.h:177–188). Signed Porymap `int` offsets therefore require exact 32-bit bit-pattern preservation across assembler emission and native signed uses; this trace does **not** verify compiled `.4byte -N` bytes or arbitrary out-of-range input.

**Compatibility obligation:** preserve JSON source identity, array ordering, unknown per-connection fields, exact target-map constant, direction and signed offset separately from the 12-byte native record. Validate that group/number fit the two emitted bytes and that offsets have a well-defined signed 32-bit representation; do not reconstruct authoring metadata from ROM alone.

## CONN-002 — authored connections can be excluded from the native header

FireRed `generate_map_header_text` writes a null `MapHeader.connections` pointer when the connections array is absent/empty **or** the map's `connections_no_include` field is `TRUE` (mapjson.cpp:155–159), even though `generate_map_connections_text` independently emits entries when a non-null JSON array exists (188–209). The C header stores a pointer to `MapConnections` at offset `0x0C` (global.fieldmap.h:185–197).

**Compatibility obligation:** distinguish authored connections, generated-but-unreferenced lists and reachable runtime lists. A ROM importer cannot infer that a missing header pointer means no authored connections exist. Verify the effective `connections_no_include` flag, source JSON and emitted pointer together. No compiled map-header check was performed here.

## CONN-003 — mirror links are semantic relationships, not stable object IDs

Porymap `areMirrored` requires opposite directions, opposite offsets and reciprocal map names; `findMirror` returns the **first** matching target-map connection and explicitly warns that duplicates do not have stable source-to-mirror pairing (mapconnection.cpp:19–42). Edit-command constructors snapshot the current `mirrorConnectingMaps` setting; offset/direction/target edits propagate through the located mirror (editcommands.cpp:571–695; mapconnection.cpp:123–169). Add/remove commands capture mirror pointers and re-resolve when a prior pair no longer matches (editcommands.cpp:703–783).

**Compatibility obligation:** an XGBA project merger must not treat mirror inference as a stable ID. Preserve authored connection object identity and duplicates; represent any inferred mirror association as ambiguous unless an authoritative ID/provenance exists. Test duplicate reciprocal edges and edited target/direction/offset before claiming a lossless refresh.

## CONN-004 — live ownership and save scope differ

`Map::addConnection` permits normal cardinal additions but, for duplicate `dive`/`emerge` directions, tracks the extra object for deletion while omitting it from the active `m_connections` list (map.cpp:328–357). `Map::loadConnection`, used for JSON imports, appends directly and does not apply that duplicate-direction suppression (350–357). `Project::saveMap` serializes **active** `getConnections()`, not the owned-object set (project.cpp:1387–1403). `Editor::save(currentOnly=true)` saves the current map plus global data; `Project::saveAll` iterates all loaded maps (editor.cpp:90–108; project.cpp:1314–1326). Mirrored edits may modify a different loaded map. `Map::pruneEditHistory` marks connection undo commands obsolete when changing maps (map.cpp:412–429).

**Compatibility obligation:** capture both maps' changes and save scope before asserting mirrored edits are durable; distinguish imported duplicate dive records from newly added suppressed duplicates. Do not infer an observed lost save or unsaved-data bug from these source paths alone.

## CONN-005 — native consumers do not share one selection rule

`InitBackupMapLayoutConnections` iterates the header's list and handles only cardinal directions for adjacent-map filling (fieldmap.c:129–170). `GetIncomingConnection` selects the **first** matching direction whose coordinate falls in the target span (686–719). In contrast, `GetMapConnection` in overworld.c:706–718 returns the **first** matching direction without a coordinate predicate; `SetDiveWarp` uses it for dive/emerge (720–734). The native connection's `u32 offset` is passed into signed geometry/position computations (fieldmap.c:149, 192 onward, 631–652), requiring representation-sensitive review. `GetIncomingConnection`'s local null checks are under `#ifdef UBFIX` (fieldmap.c:690–696), while the overworld getter directly reads `gMapHeader.connections->count` (overworld.c:706–710). This is a **conditional caller-precondition and build-variant obligation**, not evidence of a reachable null dereference.

**Compatibility obligation:** preserve connection ordering, directional uniqueness assumptions, cardinal versus dive/emerge handling, geometry and `UBFIX` variant selection. Reject/flag duplicates and missing pointers where a proposed transformation cannot prove equivalent native selection.

## Required fail-closed gates before compatibility certification

1. **Source gate:** verify all ten pinned blobs and exact call sites; independently review complete files, not just these selected functions. Do not increment independent approvals from this dossier.
2. **Compiler gate:** assemble a controlled negative-offset, duplicate-direction, `connections_no_include` and empty-list fixture in original and modern FireRed variants; inspect actual header pointers, list count, 12-byte entries, padding and map group/number bytes.
3. **Qt editor gate:** open/save/reopen paired maps with mirror toggle on/off, duplicate reciprocal links, duplicate dive/emerge, target change and a current-map-only save; compare both JSON source trees and in-memory active connections. Test save/reload after map switch and obsolete undo history.
4. **Runtime gate:** trace cardinal border traversal and dive/emerge selection on the compiled fixture; cover ambiguous directions, signed offsets, missing lists, build flags and coordinate bounds.
5. **Interoperability gate:** preserve stable source IDs, custom JSON fields, explicit `connections_no_include` provenance and two-map transaction boundaries; fail closed on ambiguous mirror pairing or nonrepresentable offsets.

**Disposition:** P0 semantic dependency documented; compiled/runtime/editor validation **NOT RUN**; whole-file independent reviews **NONE**; Phase 1 **FAIL_INCOMPLETE**; Phase 2 **NOT STARTED**.
