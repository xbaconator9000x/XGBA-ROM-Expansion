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

| `huderlem/porymap:src/core/bitpacker.cpp` | [0015](0015-porymap-bitpacker-impl.md ) | pending independent review |
| `huderlem/porymap:include/core/bitpacker.h` | [0016](0016-porymap-bitpacker-header.md ) | pending independent review |
| `huderlem/porymap:src/core/block.cpp` | [0017](0017-porymap-block-impl.md ) | pending independent review |
| `huderlem/porymap:include/core/block.h` | [0018](0018-porymap-block-header.md ) | pending independent review |
| `huderlem/porymap:src/core/blockdata.cpp` | [0019](0019-porymap-blockdata-impl.md ) | pending independent review |
| `huderlem/porymap:include/core/blockdata.h` | [0020](0020-porymap-blockdata-header.md ) | pending independent review |

**Count: 21 distinct pinned upstream whole-file identities prepared / 14,834 = 0.1011%**, compared with 0.0000% independently approved. Automated file inventory: **14,834/14,834 = 100%**. This count covers only the candidate documents explicitly registered above, **not** the 14,834 machine-generated dossiers, 338 P0 review candidates, or other standalone technical investigation notes. The separate standalone `docs/PHASE1_WHOLE_FILE_CANDIDATE_FIRERED_CRT0_2026-10-27.md` analyzes the *same* `src/crt0.s` and must **not** be counted as an additional file.

## Collision and acceptance safeguards
Two pre-existing filenames use sequence `0006` for **different** pinned files. The integer alone is therefore **not a unique candidate ID**. Until filenames and references are migrated atomically, identify a candidate by **(upstream repository, pinned commit, exact path, Git blob SHA)**, and use the full filename for links. Do not count the sequence maximum as the number of distinct files or use it as an approval counter. A later registry migration may assign unique sequence numbers, preserving historical links.

A reviewer must separately verify complete-file coverage, exact source hashes, all consumers and relevant variant/error paths, unresolved evidence, and record an authenticated independent verdict before the authoritative gate can count an approval. No candidate above has that verdict. CI passing checks is **not** independent approval.

## CI boundary
The new Poryscript/FireRed source candidate passed [exact-head CI #40379777582](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40379777582) at 3f536c23cbf403d620d1a7fd3f954625694c9543 (17 negative controls); this is source evidence, not independent review. Subsequent documentation commits require their own exact-head checks.

At exact head `9c7b3ca1598e21962aac8d64001e1b06ec2f3774`, four workflows passed: [Poryscript/FireRed #40380386984](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380386984), [save reload #40380386910](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380386910), [savestate/Matrix #40380387051](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380387051) and [layout writers #40380387204](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40380387204). **These passes precede the new 0010–0014 documentation candidates.** Do not infer exact-head CI for later commits until separately verified. None of those jobs constitutes an independent whole-file semantic review.

**Phase 1 remains FAIL_INCOMPLETE; no Phase 2 implementation or independent signoff.**
