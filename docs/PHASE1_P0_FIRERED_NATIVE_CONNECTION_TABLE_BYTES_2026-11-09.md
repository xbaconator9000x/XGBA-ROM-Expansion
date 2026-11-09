# Phase 1 P0 — pinned FireRed native connection-table bytes

**9 November 2026 · ARCHIVED COMPILED-OBJECT ANALYSIS · NON-APPROVING.** This closes the direct `.o` table-byte inspection for Package B using the existing modern and classic builds. It does **not** execute the GBA reader, inspect a linked ROM, or certify runtime reachability. Phase 1 remains `FAIL_INCOMPLETE`; independent whole-file approvals remain `0/14,834`.

## Immutable build evidence

Both Actions runs built the exact `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` source, first with authored input and then with only a synthetic completed `connections_include_order`. Their prior tests compared `maps.o` hashes; this follow-up inspected the existing archived object bytes rather than repeating those builds or hash comparisons.

| Variant | Passing Actions run / build commit | Artifact ZIP SHA-256 | Authored `maps.o` SHA-256 |
| --- | --- | --- | --- |
| Modern | [#40421312981](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40421312981), `acd2ab3b99d50982b3aa2d3d296763133ed4a264` | `fd6730336f987426e269093a35c43b31674321226259b95475aab1107a6e10ca` | `1b52f4efdb9c7125e5860af211f8097882f2dadc6ee0d997a020945c1cd4ef98` |
| Classic agbcc | [#40421631854](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40421631854), `b84f8b2dd300123afb82525648e932647a75c899` | `bedfb0bd827a34c9506a3849fbade2f6b691051d40f507ac3187bbd66b93936c` | `90a7e17a223dec05577d3faefc8af46c7fb1ed0ff3f3f3006e468d4154ee07dc` |

Both artifacts report `arm-none-eabi-gcc (15:13.2.rel1-2) 13.2.1 20231009`. The objects are ELF32 little-endian ARM EABI5 relocatable files. The `.rodata` section SHA-256 is identical in both: `d0290086e3ed4266886da22f1d1a2a3e5a7751e6ce09e38c5d1d397690bdc828`.

The checker additionally pins the already-catalogued `data/maps/map_groups.json` input: Git blob `8c382f504d208286161903244772c93138cd7662`, SHA-256 `ce296c9b54c8bb85cc35870b30a533ab017e72107fd40cf471224a42127af79a`. The existing authored global `connections.inc` is SHA-256 `3c2ef81589d9bf09784350da0714a8a07d891c795c00024cdb1da5ea743e98cf`. No new upstream source identity or whole-file receipt is introduced; the related FireRed and Porymap identities remain those already listed in [the connection ABI dossier](PHASE1_P0_PORYMAP_FIRERED_CONNECTION_ABI_2026-10-27.md).

## Extracted representation

`tools/phase1_firered_connection_object_audit.py` reads ELF32 section, symbol, and relocation tables directly with Python's standard library. Given the two extracted archived objects, the pinned map-group JSON, and the archived authored include file, it verifies:

- **63** `MapConnectionsList` tables containing **120** records total; per-table record counts are 17×1, 38×2, 5×3, and 3×4.
- All 120 records occupy exactly **12 bytes**: direction at byte 0; three zero padding bytes; the 4-byte offset word at bytes 4–7 (interpreted by the native geometry readers); map-group and map-number bytes 8–9; two zero padding bytes. All observed direction bytes are 1–4. Every group/number pair decodes through the pinned 43-group, 425-map ordering.
- The ELF address order of the 63 emitted tables matches the authored 63-name active order after filtering the 425 global include directives. This keeps table placement/order distinct from the map-group/map-number bytes stored in each record.
- Every `MapConnections` header contains a positive signed count followed by an `R_ARM_ABS32` relocation whose section-relative addend points to its list. The header-to-list extent equals `count × 12`.
- All **425** compiled map-group pointer entries resolve to a map header. At the `MapHeader.connections` field offset `0x0C`, **62** headers have a relocation to a connection header and **363** contain a zero word with no relocation. `SaffronCity` is the deliberate exception with generated data but a null native header pointer: its four-record table exists, while no relocation references its `MapConnections` header. `PalletTown` is a positive pointer control.
- The corresponding 63 table record streams are byte-identical between the modern and classic objects. The full objects differ; this comparison is only about these extracted connection records.

For a concrete record sample, `PalletTown_MapConnectionsList` begins at `.rodata+0x7D660`; its header is at `.rodata+0x7D678`. The header bytes are `02 00 00 00 60 D6 07 00`: count 2 and a relocated list pointer addend of `0x7D660`. Its two 12-byte entries are:

```text
02 00 00 00 00 00 00 00 03 13 00 00
01 00 00 00 00 00 00 00 03 27 00 00
```

In the pinned group ordering, group byte `03` and map-number bytes `13`/`27` decode to `Route1` and `Route21_North`; they are not offsets into the global connection-table sequence. The table header's count controls iteration; the entries do not have a terminator record.

## Reproduction and mutation checks

Download and verify the two artifacts listed above, then extract them. With paths to the extracted files and the pinned JSON:

```sh
python3 tools/phase1_firered_connection_object_audit.py \
  --variant modern \
  --object /path/to/modern/maps-authored.o \
  --connections-include /path/to/modern/connections-authored.inc \
  --map-groups /path/to/map_groups.json \
  --compare-object /path/to/classic/maps-authored.o
```

The run over these archived objects passed **nine fail-closed in-memory mutations**: truncated record; invalid direction; nonzero padding; unresolved map ID; reversed include order; missing table-pointer relocation; wrong relocation type; expected-null pointer with a nonzero word; and expected-nonnull pointer with no relocation. `tests/test_phase1_firered_connection_object_audit.py` adds synthetic unit controls for record decoding, malformed records, order changes, and null pointers. These are checker controls, not mutated FireRed source or ROM runtime tests.

## Reader boundary and remaining gates

The existing pinned source dossier defines `MapConnection` fields at offsets 0, 4, 8, and 9; `MapConnections` count and pointer at offsets 0 and 4; and `MapHeader.connections` at offset `0x0C` (`include/global.fieldmap.h`, blob `e2828ec0cb1439718e830fbef4366770b3b77b1c`). It traces `InitBackupMapLayoutConnections` and `GetIncomingConnection` (`src/fieldmap.c`, blob `41567772299000ba5855419e5c39ad9373a34c20`) and `GetMapConnection` / `SetDiveWarp` (`src/overworld.c`, blob `339014da46ae8543143edc99ab72bf7496203a0d`). Those are source-grounded reader paths, **not executed readers**.

This runner has no `arm-none-eabi-gcc`, `qemu-arm`, `qemu-system-arm`, or mGBA executable; its host `objcopy` also cannot process the archived ARM objects. The archived objects permit direct record and relocation inspection, but no linked-ROM pointer resolution or emulator execution. The precise outstanding boundary is source reader execution against these compiled tables, followed by linked-ROM/runtime validation. No approval or Phase 2 credit is claimed.
