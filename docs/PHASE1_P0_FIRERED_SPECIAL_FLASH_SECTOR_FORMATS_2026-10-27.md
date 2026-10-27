# Phase 1 P0 — FireRed special flash sectors are not ordinary save-slot sectors

**27 October 2026 · exact-pinned source trace and arithmetic witness · not runtime-certified · no independent approval.** This is a dependency-connected continuation of [native sector ID and map-view tracing](PHASE1_P0_FIRERED_FLASH_SECTOR_ID_AND_MAPVIEW_2026-10-27.md) and [save-sector/sidecar obligations](SAVE_SECTOR_AND_SIDECAR_SEMANTICS_v25.md). The 14-sector main-slot contract does **not** describe all four special sectors. Phase 1 remains **FAIL_INCOMPLETE**. No Phase 2 changes are authorized.

## Immutable sources and roles

| Repository / exact commit | Path / Git blob | Producer/consumer role |
| --- | --- | --- |
| [FireRed ce6406d8](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982) | include/save.h / 87fb9b615b434b58823d15688056695acda9feab | Physical sector offsets, IDs 28–31, sentinel |
| same | src/save.c / 36b960f375c92711aa49b99bdfe9c6b3a99d6b1c | Standard, Hall of Fame and Trainer Tower readers/writers |
| same | src/hall_of_fame.c / 05c7d75384c2ad8481b6819f71faaf089f683bbf | Hall of Fame producer, persistence, display consumer |
| same | src/cereader_tool.c / 395be0bcbed8454e645a9f5670cde3024eda508e | Trainer Tower producer, split, validation consumer |
| same | include/cereader_tool.h / 5cb5a9ebc32db23de07800ccce124bcb28d3ef15 | Tower structures and annotated offsets |
| same | include/constants/trainer_tower.h / ea0039ea1408c06b8c968cfde8e2628213b2a0dc | Eight-floor and three-trainer bounds |
| [mGBA fd9dc5c2](https://github.com/mgba-emu/mgba/tree/fd9dc5c2cbf234365068855851107e762fc6211b) | src/gba/savedata.c / fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb | Raw flash-file importer, not FireRed sector parser |
| same | include/mgba/internal/gba/memory.h / 0aad912613e726560d06bbdbf6061986e69e5842 | FLASH1M size 0x20000 |

## FSSF-001 — three distinct sector formats share the same 4 KiB physical space

The standard SaveSector structure has 3,968 data bytes, 116 unused footer bytes, a 16-bit ID, a 16-bit checksum, a 32-bit signature and a 32-bit counter. Computed byte offsets: **ID 4084, checksum 4086, signature 4088, counter 4092** (exclusive end 4096). Ordinary main-slot writer HandleWriteSector sets ID 0–13 and writes the computed checksum to the **checksum field** (src/save.c:163–194). Two main save slots occupy sectors 0–27.

**Hall of Fame sectors 28–29 use a different format.** HandleSavingData(SAVE_HALL_OF_FAME) writes two 3,968-byte halves of gDecompressionBuffer via HandleWriteSectorNBytes (src/save.c:660–676). That writer zeroes its 4 KiB buffer, sets the standard signature, but writes CalculateChecksum(data, size) to **sector.id**, not sector.checksum (src/save.c:198–216). The paired TryLoadSaveSector checks **sector.id == checksum** (src/save.c:584–605); LoadGameSave(SAVE_HALL_OF_FAME) loads sectors 28 and 29 (src/save.c:816–829). The ID-as-checksum pairing is **intentional producer/consumer behaviour in the pinned source**, not an accidental comparison mismatch. The cleared buffer leaves the conventional checksum field and counter zero in the produced image, assuming successful write. The Hall of Fame game code invokes save/load (src/hall_of_fame.c:425–467, 749–773).

**Trainer Tower sectors 30–31 use a third format.** TryWriteSpecialSaveSector writes SPECIAL_SECTOR_SENTINEL = 0xB39D as a 32-bit value at **byte 0**, copies caller-provided bytes beginning at **byte 4**, and writes the whole sector (src/save.c:856–883). Its reader tests the first-word sentinel and copies the remaining bytes into a caller buffer (src/save.c:831–855). Neither helper validates a standard footer signature/checksum; CEReaderTool_LoadTrainerTower_r subsequently validates nested floor/set checksums (src/cereader_tool.c:14–42, 69–83). **Do not apply main-slot footer validation to these special sectors.**

## FSSF-002 — the inclusive Trainer Tower loop includes the counter bytes

Both Tower helpers set size = SECTOR_COUNTER_OFFSET - 1 and iterate with **i <= size**, starting at gSaveDataBuffer.data[4] (src/save.c:842–849, 866–878). SECTOR_COUNTER_OFFSET is 4092, so they copy **4092 bytes** (indices 0–4091) into/out of physical offsets **4–4095 inclusive**. This **includes all four bytes of the ordinary counter field**, despite the nearby comment claiming the counter is excluded. The comment is not the serialized length contract.

CEReaderTool_SaveTrainerTower and CEReaderTool_LoadTrainerTower allocate SECTOR_SIZE (4096-byte) temporary buffers (src/cereader_tool.c:62–66, 87–93), so this source trace **does not show a buffer overflow in those callers**. The Tower format uses a four-byte sentinel and up to 4092 payload bytes per physical sector.

The authoring split is SEC30_SIZE = offsetof(EReaderTrainerTowerSet, floors[4]) and SEC31_SIZE = sizeof(EReaderTrainerTowerSet) - SEC30_SIZE (src/cereader_tool.c:7–11). The header annotates a floor checksum at offset 0x3DC (last four bytes), suggesting a 992-byte floor and **3,976 / 3,968** bytes in the two halves (eight-byte header + four floors, then four floors). These are **annotation-derived estimates**, not independently compiled ARM sizeof/offsetof values. The pinned static assertion checks the *sum* against SECTOR_COUNTER_OFFSET * 2; compiled per-half and memory-layout checks remain open.

## FSSF-003 — mGBA sees bytes, not these three logical formats

Pinned mGBA GBASavedataSize selects 0x20000 for FLASH1M and GBASavedataLoad copies/streams raw bytes (src/gba/savedata.c:169–226). That function does not identify FireRed main-slot, Hall of Fame or Trainer Tower formats. An XGBA save importer/sidecar must preserve **all 32 physical sectors**, validate according to each sector's purpose, and associate extension state with the validated *main* slot rather than interpreting Hall of Fame checksum-as-ID or Tower sentinel bytes as main-slot IDs. This is a **Phase 1 compatibility requirement**, not an implementation or observed emulator failure.

## Reproducibility and remaining gates

[Source witness](../tools/phase1_firered_special_sector_formats.py) checks eight exact Git blobs, producer/consumer source expressions, counter-offset arithmetic and fail-closed single-anchor mutation controls. [Dedicated workflow](../.github/workflows/phase1-firered-special-sectors.yml) checks out both immutable upstream commits and uploads a JSON artifact. **Do not claim CI PASS until the workflow completes.** It is source/annotation evidence only, not an ARM binary, mGBA save-load session, malformed-save runtime test or independent whole-file review.

Next: compile pinned original/modern FireRed to establish actual Tower sizeof and offsetof; execute Hall of Fame and Trainer Tower save/load through an emulator; test malformed special-sector inputs and main-slot fallback; verify exact-head CI. This dossier adds **no whole-file candidate or approval**. Inventory **14,834/14,834**; independently approved **0/14,834**; Phase 1 **FAIL_INCOMPLETE**.
