# Phase 1 analyst whole-file candidate register — 27 October 2026

**Status: review preparation only.** The authoritative [Phase 1 mapping gate](../../semantic-snapshots/current/phase1_mapping_gate.json) is `FAIL_INCOMPLETE` with **0/14,834 independent whole-file approvals (0.0000%)**. This document is a manual, source-identified inventory of analyst-prepared candidates; it is **not** a gate input or a reviewer-signoff registry.

## Exact source-identity register

| Stable review identity (repository / pinned path) | Analyst candidate | State |
| --- | --- | --- |
| `pret/pokefirered:src/rom_header.s` | [0001](0001-firered-rom-header.md) | pending independent review |
| `pret/pokefirered:include/gba/syscall.h` | [0002](0002-firered-gba-syscall.md) | pending independent review |
| `pret/pokefirered:src/reset_save_heap.c` | [0003](0003-firered-reset-save-heap.md) | pending independent review |
| `pret/pokefirered:constants/version.inc` | [0004](0004-firered-version-constants.md) | pending independent review |
| `mgba-emu/mgba:src/gba/serialize.c` | [0005](0005-mgba-gba-serialize.md) | pending independent review |
| `pret/pokefirered:src/crt0.s` | [0006 FireRed](0006-firered-crt0.md) | pending independent review |
| `mgba-emu/mgba:src/gba/cart/matrix.c` | [0006 mGBA](0006-mgba-matrix.md) | pending independent review |
| `pret/pokefirered:constants/misc_constants.inc` | [0007](0007-firered-misc-constants.md) | pending independent review |
| `mgba-emu/mgba:include/mgba/internal/gba/cart/matrix.h` | [0008](0008-mgba-matrix-header.md) | pending independent review |
| `huderlem/poryscript:emitter/chunk.go` | [0009](0009-poryscript-chunk.md) | pending independent review |
| `pret/pokefirered:ld_script_modern.ld` | [0010](0010-firered-modern-linker.md) | pending independent review |
| `pret/pokefirered:config.mk` | [0011](0011-firered-config.md) | pending independent review |
| `pret/pokefirered:include/gba/defines.h` | [0012](0012-firered-gba-defines.md) | pending independent review |
| `pret/pokefirered:include/constants/trainer_tower.h` | [0013](0013-firered-trainer-tower-constants.md) | pending independent review |
| `pret/pokefirered:include/cereader_tool.h` | [0014](0014-firered-cereader-abi.md) | pending independent review |
| `pret/pokefirered:ld_script.ld` | [0015](0015-firered-legacy-linker.md) | pending independent review |
| `pret/pokefirered:ld_script_rev10.ld` | [0016](0016-firered-rev10-linker.md) | pending independent review |
| `pret/pokefirered:include/gba/gba.h` | [0017](0017-firered-gba-umbrella.md) | pending independent review |
| `pret/pokefirered:include/gba/multiboot.h` | [0018 FireRed](0018-firered-gba-multiboot.md) | pending independent review |
| `pret/pokefirered:include/gba/isagbprint.h` | [0019 FireRed](0019-firered-gba-debug-print.md) | pending independent review |
| `huderlem/porymap:src/core/bitpacker.cpp` | [0015](0015-porymap-bitpacker-impl.md) | pending independent review |
| `huderlem/porymap:include/core/bitpacker.h` | [0016](0016-porymap-bitpacker-header.md) | pending independent review |
| `huderlem/porymap:src/core/block.cpp` | [0017](0017-porymap-block-impl.md) | pending independent review |
| `huderlem/porymap:include/core/block.h` | [0018](0018-porymap-block-header.md) | pending independent review |
| `huderlem/porymap:src/core/blockdata.cpp` | [0019](0019-porymap-blockdata-impl.md) | pending independent review |
| `huderlem/porymap:include/core/blockdata.h` | [0020](0020-porymap-blockdata-header.md) | pending independent review |

| `huderlem/porymap:include/core/tile.h` | [0021](0021-porymap-tile-header.md) | pending independent review |
| `huderlem/porymap:src/core/tile.cpp` | [0022](0022-porymap-tile-impl.md) | pending independent review |
| `huderlem/porymap:include/core/metatile.h` | [0023](0023-porymap-metatile-header.md) | pending independent review |
| `huderlem/porymap:src/core/metatile.cpp` | [0024](0024-porymap-metatile-impl.md) | pending independent review |
| `huderlem/porymap:include/core/mapconnection.h` | [0025](0025-porymap-mapconnection-header.md) | pending independent review |
| `huderlem/porymap:src/core/mapconnection.cpp` | [0026](0026-porymap-mapconnection-impl.md) | pending independent review |

| `pret/pokefirered:asm/macros/map.inc` | [0027](0027-firered-map-assembly-macros.md) | pending independent review |
| `pret/pokefirered:include/constants/map_scripts.h` | [0028](0028-firered-map-script-types.md) | pending independent review |
| `pret/pokefirered:include/constants/event_bg.h` | [0029](0029-firered-background-event-constants.md) | pending independent review |
| `pret/pokefirered:include/constants/event_objects.h` | [0030](0030-firered-object-event-constants.md) | pending independent review |

| `pret/pokefirered:map_data_rules.mk` | [0031](0031-firered-generated-map-build-rules.md) | pending independent review |

**Count: 37 distinct pinned upstream whole-file identities prepared / 14,834 = 0.2494%**, compared with 0.0000% independently approved. Automated file inventory: **14,834/14,834 = 100%**. This count covers only the candidate documents explicitly registered above, **not** the 14,834 machine-generated dossiers, 338 P0 review candidates, or other standalone technical investigation notes. The separate standalone `docs/PHASE1_WHOLE_FILE_CANDIDATE_FIRERED_CRT0_2026-10-27.md` analyzes the *same* `src/crt0.s` and must **not** be counted as an additional file.

## Collision and acceptance safeguards
Multiple filenames now reuse sequence numbers (including `0006` and `0015`–`0019`) for **different** pinned files. The integer alone is therefore **not a unique candidate ID**. Until filenames and references are migrated atomically, identify a candidate by **(upstream repository, pinned commit, exact path, Git blob SHA)**, and use the full filename for links. Do not count the sequence maximum as the number of distinct files or use it as an approval counter. A later registry migration may assign unique sequence numbers, preserving historical links.

A reviewer must separately verify complete-file coverage, exact source hashes, all consumers and relevant variant/error paths, unresolved evidence, and record an authenticated independent verdict before the authoritative gate can count an approval. No candidate above has that verdict. CI passing checks is **not** independent approval.

## CI boundary
The new Poryscript/FireRed source candidate passed [exact-head CI #40379777582](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40379777582) at 3f536c23cbf403d620d1a7fd3f954625694c9543 (17 negative controls); this is source evidence, not independent review. Subsequent documentation commits require their own exact-head checks.

At exact head `9c7b3ca1598e21962aac8d64001e1b06ec2f3774`, four workflows passed: [Poryscript/FireRed #40380386984](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380386984), [save reload #40380386910](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380386910), [savestate/Matrix #40380387051](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380387051) and [layout writers #40380387204](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380387204). **These passes precede the new 0010–0014 documentation candidates.** Do not infer exact-head CI for later commits until separately verified. None of those jobs constitutes an independent whole-file semantic review.

**Phase 1 remains FAIL_INCOMPLETE; no Phase 2 implementation or independent signoff.**

## 27 October — legacy linker pair and umbrella header checkpoint

Three further **distinct** exact-hash candidates were prepared: `ld_script.ld` (0015), `ld_script_rev10.ld` (0016) and `include/gba/gba.h` (0017). Both legacy linker scripts were inspected through all 11 allocated output-section families, symbol includes, fixed graphics address, debug outputs and discard rule. The comparison identifies revision-10 RFU input-object section moves and different DWARF selectors, which are source-level distinctions rather than compiled-address claims. The umbrella header has eight includes and no authored executable definitions. GitHub's exact-commit file response verified each blob identity. No reviewer verdict is asserted.

The preceding `00156d49` commit had four successful PR workflows: [Poryscript #40380990395](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380990395), [savestate/Matrix #40380990451](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380990451), [save reload #40380991212](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380991212), [layout writer #40380990760](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380990760). These passes **predate** this checkpoint; exact-head CI for the current docs commits is not yet asserted. Formal approvals remain **0/14,834 (0.0000%)**, inventory **14,834/14,834 (100%)**. **FAIL_INCOMPLETE.**

## 27 October — concurrent-source register reconciliation

The register now preserves six additional **distinct** Porymap source identities (bitpacker implementation/header, block implementation/header, blockdata implementation/header), whose review documents were verified present, alongside the five new FireRed identities from this batch (legacy linker variants, GBA umbrella, multiboot ABI and conditional debug print). This reconciliation **does not claim** to have independently reviewed the Porymap candidates or their external consumers. It corrects the stale denominator calculation and broken Markdown links without changing the authoritative approval gate. **26/14,834 = 0.1753% prepared; 0/14,834 = 0.0000% independently approved; 14,834/14,834 = 100% inventoried. FAIL_INCOMPLETE.**

## 27 October — Porymap tile, metatile and connection contracts

Six exact-blob source candidates were added: header/implementation pairs for `Tile`, `Metatile`, and `MapConnection`. They cover 16-bit tile packing, configurable metatile attribute masks and mirrored map connections. The metatile coordinate conversion has a **source-level negative exact-multiple boundary discrepancy** (`-16` pixel coordinate maps to `-2` instead of mathematical floor `-1`); runtime/editor reachability is not established. **32/14,834 = 0.2157% analyst-prepared, 0/14,834 = 0.0000% independently approved.** CI for this documentation commit must be checked separately.

## 27 October — map-event assembler and constants checkpoint

Four distinct pinned FireRed source files were read in full, and exact Git blobs were verified: `asm/macros/map.inc` (0027), `include/constants/map_scripts.h` (0028), `include/constants/event_bg.h` (0029), and `include/constants/event_objects.h` (0030). The records distinguish the 24-byte normal/clone templates, 8-byte warp, 16-byte coord, 12-byte background and connection records, one-byte event counters, 32-bit pointers, dynamic graphics selectors and local-ID namespaces. This is **source-level semantic preparation**, not a compiled ABI or runtime verification. No independent reviewer has signed off. **36/14,834 = 0.2427% prepared; 0/14,834 = 0.0000% approved; 100% inventoried.** Exact-head CI after this documentation checkpoint must be checked separately.

## 27 October — generated map-event constants provenance

Pinned FireRed `map_data_rules.mk` (0031) was inspected in full, with Git blob `b32b85a91d9460642345ca983c37d165e820741f`. It proves that `include/constants/map_event_ids.h`, included by candidate 0030, is generated by `MAPJSON event_constants` from per-map JSON sources, rather than being a missing tracked source blob. The object-graphics candidate now links this exact dependency. This is a new source-level build/provenance constraint, not a generated-file content hash or clean-build test. **37/14,834 = 0.2494% prepared; 0/14,834 = 0.0000% approved; 100% inventoried.**
