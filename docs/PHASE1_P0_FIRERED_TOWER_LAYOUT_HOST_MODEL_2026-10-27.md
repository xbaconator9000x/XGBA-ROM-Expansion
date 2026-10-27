# Phase 1 — Trainer Tower full-set structure and flash split: source-driven host C layout witness

**27 October 2026 · source pinned; host-compiled ABI model only · no independent signoff.**

The pinned FireRed sources [`include/cereader_tool.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/cereader_tool.h) (blob `5cb5a9ebc32db23de07800ccce124bcb28d3ef15`), [`include/pokemon.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/pokemon.h) (blob `414dc41767295aed38f299e8495c5e2f8d25ddc9`), `include/constants/global.h` (`21c781a0d40aa8b303642bbf1eac9ac09ce2b5a9`), `include/constants/trainer_tower.h` (`ea0039ea1408c06b8c968cfde8e2628213b2a0dc`), `include/save.h` (`87fb9b615b434b58823d15688056695acda9feab`), `src/cereader_tool.c` (`395be0bcbed8454e645a9f5670cde3024eda508e`) and `src/save.c` (`36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`) establish the following source-driven layout model.

| Struct or offset | Derived byte count | Basis |
| --- | ---: | --- |
| `BattleTowerPokemon` | 44 | Full pinned member list, 32-bit IV bitfield unit |
| `TrainerTowerTrainer` | 328 | 64-byte prefix and six 44-byte party members |
| `TrainerTowerFloor` | 992 | 4-byte header, three 328-byte trainers, 4-byte checksum at offset 988 |
| `EReaderTrainerTowerSet` | 7,944 | 8-byte header and eight 992-byte floors |
| `SEC30_SIZE` | 3,976 | Offset of `floors[4]`: 8 + 4 × 992 |
| `SEC31_SIZE` | 3,968 | Full set minus first split |
| Special-sector copy count | 4,092 each | `i <= SECTOR_COUNTER_OFFSET - 1`, starting at byte 4 |
| Unused payload padding | 116 / 124 | First and second 4,092-byte special-sector payloads respectively |

This resolves the earlier **annotation-derived** 3,976/3,968 estimate at the level of a **host C compilation model built from actual pinned struct definitions**, not original agbcc or GBA execution. The checker extracts the exact struct declarations from immutable upstream blobs, validates all source anchors and source mutations, compiles the extracted definitions using host `cc`, and checks each expected `sizeof`/`offsetof` value. Compiler ABI agreement with ARM is still an open gate.

**Producer → storage → consumer:** `CEReaderTool_SaveTrainerTower_r` copies 3,976 bytes into the first 4,096-byte temporary buffer and 3,968 into the second, zero-filling each buffer before the special-sector writer copies 4,092 bytes after its four-byte sentinel. `CEReaderTool_LoadTrainerTower_r` reads the two special sectors and reconstructs the set before `ValidateTrainerTowerData` checks floor and aggregate checksums. The producer also replaces `buffer[1]` (the set's `id` byte) with `GetTrainerHillUnkVal()`, while the data validator does not check that ID. That is a **source-visible intentional transformation**, not a proof of a gameplay defect.

**Cross-boundary open edges:** Original agbcc and modern GCC compiled `sizeof`/`offsetof`, actual ARM generated copies, mGBA FLASH1M save/restore and special-sector malformed-input behaviour, editor/sidecar preservation of both payloads, and independent complete-file reviews. A host model cannot certify those behaviours. See [special-sector formats](PHASE1_P0_FIRERED_SPECIAL_FLASH_SECTOR_FORMATS_2026-10-27.md) and [save-counter coherence](PHASE1_P0_FIRERED_SAVE_SLOT_COUNTER_COHERENCE_2026-10-27.md).

**No new whole-file review candidates or independent approvals. Phase 1 remains FAIL_INCOMPLETE. No Phase 2.**
