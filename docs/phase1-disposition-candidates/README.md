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

| `pret/pokefirered:tools/mapjson/mapjson.cpp` | [0032](0032-firered-mapjson-generator.md) | pending independent review |
| `pret/pokefirered:tools/mapjson/mapjson.h` | [0033](0033-firered-mapjson-fatal-interface.md) | pending independent review |

| `pret/pokefirered:tools/mapjson/Makefile` | [0034](0034-firered-mapjson-build-makefile.md) | pending independent review |
| `pret/pokefirered:tools/mapjson/json11.h` | [0035](0035-firered-json11-api-header.md) | pending independent review |
| `pret/pokefirered:tools/mapjson/json11.cpp` | [0036](0036-firered-json11-parser-implementation.md) | pending independent review |
| `pret/pokefirered:make_tools.mk` | [0037](0037-firered-make-tools-build-graph.md) | pending independent review |

| `pret/pokefirered:include/gba/types.h` | [0038](0038-firered-gba-types-abi.md) | pending independent review |
| `pret/pokefirered:include/gba/flash_internal.h` | [0039](0039-firered-flash-internal-contract.md) | pending independent review |
| `pret/pokefirered:include/gba/macro.h` | [0040](0040-firered-gba-dma-cpu-macros.md) | pending independent review |
| `pret/pokefirered:data/maps.s` | [0041](0041-firered-maps-assembly-root.md) | pending independent review |
| `pret/pokefirered:data/map_events.s` | [0042](0042-firered-map-events-assembly-root.md) | pending independent review |
| `pret/pokefirered:data/maps/map_groups.json` | [0043](0043-firered-authored-map-groups.md) | pending independent review |
| `pret/pokefirered:data/maps/SaffronCity/map.json` | [0044](0044-firered-saffron-city-map-json.md) | pending independent review |
| `pret/pokefirered:data/layouts/layouts.json` | [0045](0045-firered-authored-layout-table.md) | pending independent review |
| `pret/pokefirered:data/script_cmd_table.inc` | [0047](0047-firered-script-command-dispatch-table.md) | pending independent review |
| `pret/pokefirered:src/script.c` | [0048](0048-firered-script-interpreter-runtime.md) | pending independent review |
| `pret/pokefirered:include/script.h` | [0049](0049-firered-script-context-abi-header.md) | pending independent review |
| `pret/pokefirered:include/event_data.h` | [0050](0050-firered-event-data-api-header.md) | pending independent review |
| `pret/pokefirered:include/fieldmap.h` | [0051](0051-firered-fieldmap-public-contract.md) | pending independent review |
| `pret/pokefirered:include/overworld.h` | [0052](0052-firered-overworld-api-header.md) | pending independent review |
| `pret/pokefirered:include/field_control_avatar.h` | [0053](0053-firered-field-input-api-header.md) | pending independent review |
| `pret/pokefirered:include/config.h` | [0054](0054-firered-build-variant-config.md) | pending independent review |
| `pret/pokefirered:include/gba/io_reg.h` | [0055](0055-firered-gba-io-register-contract.md) | pending independent review |
| `pret/pokefirered:constants/gba_constants.inc` | [0056](0056-firered-assembly-gba-constants.md) | pending independent review |
| `pret/pokefirered:src/gpu_regs.c` | [0057](0057-firered-gpu-register-buffer-runtime.md) | pending independent review |
| `pret/pokefirered:include/gpu_regs.h` | [0058](0058-firered-gpu-regs-public-api.md) | pending independent review |

**Count: 63 distinct pinned upstream whole-file identities prepared / 14,834 = 0.4247%**, compared with 0.0000% independently approved. Automated file inventory: **14,834/14,834 = 100%**. This count covers only the candidate documents explicitly registered above, **not** the 14,834 machine-generated dossiers, 338 P0 review candidates, or other standalone technical investigation notes. The separate standalone `docs/PHASE1_WHOLE_FILE_CANDIDATE_FIRERED_CRT0_2026-10-27.md` analyzes the *same* `src/crt0.s` and must **not** be counted as an additional file.

## 27 October — corrected duplicate and script interpreter ABI closure

Candidate [0028](0028-firered-map-script-types.md) and [0046](0046-firered-map-script-type-constants.md) cover the **same exact pinned** `include/constants/map_scripts.h` blob (`1353de360cf1e00b6efbb26ec59c4822c99b59bf`). Both documents remain available; only 0028 is registered as the distinct source identity. The prior claim of **52 distinct** files actually represented **51**. Three new distinct whole-file candidates (0047–0049) cover the native script dispatch table, interpreter implementation and public context header, bringing the corrected register to **54**. The new [integrity checker](../../tools/phase1_review_register_integrity.py) and CI workflow fail on duplicate identities, missing documents or incorrect totals. This is analyst preparation only: **0/14,834 independent approvals, FAIL_INCOMPLETE**. Exact-head CI remains to be verified.

## 27 October — source-verified field map, event and warp interfaces

Four additional **distinct** complete-file candidates (0050–0053) cover the pinned event-variable/flag header, native fieldmap collision and buffer constants, overworld warp/callback ABI, and field-input bitfields and dive trigger. Their exact upstream Git blobs were fetched and read in full. Source declarations are not executable reachability, compiled ABI equivalence, runtime certification or independent approval. **58/14,834 = 0.3910% analyst-prepared; 0/14,834 = 0.0000% approved; 100% inventoried; FAIL_INCOMPLETE.** The register integrity checker must pass at the new head before CI is claimed.

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

## 27 October — full mapjson producer and failure interface

Exact pinned blobs `tools/mapjson/mapjson.cpp` (741 lines, 0032) and `tools/mapjson/mapjson.h` (0033) were inspected in full. Source-level producer semantics now cover all four generator modes, generated local IDs, group/layout order, source JSON to assembler records, conditional header omission, and fatal-error behaviour. A **new potential undefined iterator arithmetic hazard** is documented for partial `connections_include_order` lists (generator lines 470–479): an absent name leads to `begin() + numeric_limits<int>::max()` before comparator ordering. This is a source-level hazard, not a demonstrated crash or editor defect; sanitizer fixture and compiled/runtime tests remain open. **39/14,834 = 0.2629% prepared; 0/14,834 = 0.0000% approved; 100% inventoried.**

## 27 October — mapjson parser and incremental tool-build dependency checkpoint

Four new distinct exact-blob whole-file analyst candidates (0034–0037) cover the entire mapjson local Makefile, json11 API header, json11 implementation and root recursive tool dispatcher. The Makefile declares `mapjson.h` but **omits `json11.h`** from executable prerequisites despite both C++ sources including it. An isolated timestamp-controlled GNU Make `make -n` test with a verbatim pinned Makefile reproduced the dependency gap: updating only `json11.h` left `mapjson` "up to date"; updating declared `mapjson.h` scheduled the C++ recipe. This is an incremental dependency defect, **not** a full upstream build or a demonstrated stale ROM. json11's duplicate-key overwrite, typed-default fallback and numeric representation are source-level interoperability obligations, not observed corruption. **43/14,834 = 0.2899% analyst-prepared; 0/14,834 = 0.0000% independently approved; inventory 100%; FAIL_INCOMPLETE.** Exact-head CI for this new commit must be checked separately.

## 27 October — GBA graphics types, save-flash and DMA macro boundaries

Three exact-hash complete-file analyst candidates (0038–0040) cover `include/gba/types.h`, `include/gba/flash_internal.h` and `include/gba/macro.h`. They distinguish graphics/OAM fixed-width fields, save-flash banking versus cartridge ROM mapping, and BIOS/DMA transfer counts. The `DmaCopyLarge`, `DmaFillLarge` and `DmaClearLarge` macros each perform a full first block transfer **before** checking remaining size, making `size >= block` an implicit caller precondition; no reachable runtime failure is asserted. **46/14,834 = 0.3101% prepared; 0/14,834 = 0.0000% independently approved; inventory 100%; FAIL_INCOMPLETE.** Four exact-head CI runs for `6a3da8af` passed prior to this batch. New exact-head CI requires separate verification.

## 27 October — build-variant candidate reconciliation and integrity repair

The exact pinned `pret/pokefirered:include/config.h` file is registered as [0054](0054-firered-build-variant-config.md), making **59 distinct complete-file analyst-prepared identities**. The previous register declaration incorrectly remained at 58 despite this row being present, causing the [register-integrity job #40434589547](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40434589547) to fail its count validation. This checkpoint corrects the declared count only; no reviewer verdict, source identity or authoritative gate is modified. **59/14,834 = 0.3977% prepared; 0/14,834 = 0.0000% independently approved; inventory 100%; FAIL_INCOMPLETE.** CI for this corrective commit requires separate exact-head confirmation.

## 27 October — 60th candidate: GBA I/O register contract

The complete pinned [GBA I/O register header](0055-firered-gba-io-register-contract.md) is analyst-prepared as the **60th distinct whole-file candidate**, with all 683 valued macros partitioned, pinned blob identity, volatile-access and aliasing obligations, and reviewer questions. No compiled, emulator or hardware access-width proof is asserted. **60/14,834 = 0.4045% prepared; 0/14,834 = 0.0000% independently approved; inventory 100%; FAIL_INCOMPLETE.** Exact-head CI remains to be verified.

## 27 October — 61st candidate: assembly hardware constant ABI cross-check

The complete pinned [assembly GBA constants include](0056-firered-assembly-gba-constants.md) is analyst-prepared as the **61st distinct whole-file candidate**, covering 464 `.set` symbols and 158 numeric-equal shared offset aliases against the C I/O header. Asymmetric alias names and compiler/runtime semantics remain review obligations, not claimed defects. **61/14,834 = 0.4112% prepared; 0/14,834 = 0.0000% independently approved; inventory 100%; FAIL_INCOMPLETE.** Exact-head CI must be verified separately.

## 27 October — GPU register buffering and public API closure

Two complete pinned source files, [GPU register manager implementation](0057-firered-gpu-register-buffer-runtime.md) and [public header](0058-firered-gpu-regs-public-api.md), are now distinct analyst-prepared candidates. The implementation exposes a conditional 16-bit buffer boundary hazard for offset 95 and the header has one declaration without an identified definition; neither is claimed reachable in stock gameplay or a confirmed linker/runtime defect. **63/14,834 = 0.4247% prepared; 0/14,834 = 0.0000% independently approved; inventory 100%; FAIL_INCOMPLETE.** Exact-head CI remains to be checked.
