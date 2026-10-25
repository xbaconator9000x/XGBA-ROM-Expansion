# Phase 1 v2.5 — compiled variant, hardware staging and native save semantics

**Mapping gate: FAIL_INCOMPLETE.** The full source inventory remains valid; 0 / 14,834 independently accepted whole-file semantic dispositions. This milestone includes reproducible *source- and compiler-backed* findings, not an unlimited ROM implementation.

## Latest completed source/compiled results

| Dimension | Verified evidence | Limit |
| --- | --- | --- |
| Pinned Git source manifest | **14,834** tracked files, all Git canonical bytes verified | Not all semantically interpreted |
| Source/config files | **4,685** source/config entries scanned and hash checked | Static syntax does not prove runtime behavior |
| Historical/candidate mapping register | **29,068** checked original and source-referenced candidate records | Candidate-only entries not independently approved |
| Module review packets | **163** dossiers covering all 14,834 tracked files | Every module still pending signoff |
| Function review packets | **39,530** functions across **1,716** source files | **31,043** are from AST-error files; no path-complete verification |
| Field + battle opcode slots | **213 + 248 = 461** mapped handlers | Pointer and branch-dependent behaviors require further review |
| Native maps | **425** compiled map sources, nine intentional cross-map clones verified | Arbitrary compiled ROM reimport unsupported |
| Compiled mGBA | **173** pinned headless compilation units | Emulator still unmodified |
| Compiled Porymap | **213** compiled translation units including generated Qt sources | Other forks/compilers may differ |
| Pinned FireRed compiler variants | Both original agbcc and modern GCC ELF builds succeeded; **12/12** combined symbol/layout constraints passed | Only these two pinned configurations |
| Critical compiled symbols | **11/11 tested symbol addresses differ** between classic and modern; all retained expected table byte lengths | Hardcoded patch offsets cannot be shared |
| ROM/audio/tile lifecycle | **13** source-anchored contracts passed | No external resource runtime tests |
| Graphics memory | **12** hardware/buffer/allocator source contracts passed; 16 KiB scratch, 1,024 4bpp OBJ tiles, 96 KiB VRAM | Unlimited storage is not unlimited resident RAM or VRAM |
| Native game saves | **17** source-anchored geometry/checksum/slot contracts passed; 32 × 4 KiB flash sectors allocated | External game state must use an independent format |

## Critical compatibility consequences

1. **Build-specific linker fingerprints.** Modern GCC moves the field script table, battle command table, sprite tables, song table, map groups/layouts and IWRAM save pointers. A plugin must identify the exact source/binary ABI rather than apply fixed addresses across builds.
2. **Separate external storage from native execution memory.** mGBA can expose an external package but unchanged CPU fetch, DMA, GPU, audio and SRAM readers cannot address unlimited bytes directly. Every staged resource needs a lifetime and validation contract.
3. **Preserve legacy save format without claiming free sectors.** FireRed has two rotating 14-sector slots plus four special sectors filling 128 KiB; a sidecar must follow valid slot/counter fallback and not overwrite native sectors.
4. **Don't repurpose vanilla script opcodes.** All 461 vanilla script handler slots are known; NOP opcode zero is used by real source and is not a free escape opcode.

## Reproduction and evidence

- [v2.4 permanent six-pipeline archive](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.4).
- [Classic and modern FireRed successful build](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40186901429).
- [ROM/audio/DMA and graphics source contract job](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40187261073).
- [Native save and graphics source contract job](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40187741794).
- [Resource lifecycle findings](RESOURCE_LIFETIMES_v23.md), [native save geometry and sidecar constraints](SAVE_SECTOR_AND_SIDECAR_SEMANTICS_v25.md).

The build-specific ABI fingerprint validator, six-pipeline v2.5 packaging, and source-wide final semantic approvals are distinct remaining work. **Do not mark Phase 1 complete** based on passing compiler builds or the creation of review dossiers.
