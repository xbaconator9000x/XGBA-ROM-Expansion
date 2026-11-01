# Phase 1 mGBA Matrix whole-file semantic evidence — 2026-11-01

**Disposition: `NEEDS_REVIEW`. No semantic receipt or approval was created.** This is a source-grounded review of the complete pinned `src/gba/cart/matrix.c` translation unit and a record of bounded build/native evidence. It does not establish an XGBA implementation, complete upstream consumer closure, distribution clearance, or semantic congruence.

## Immutable identity and original dossier

| Evidence | Verified identity |
| --- | --- |
| Upstream repository/revision | `mgba-emu/mgba`, `fd9dc5c2cbf234365068855851107e762fc6211b` |
| `src/gba/cart/matrix.c` Git blob / SHA-256 | `9ccbe883235b98bcf56cd609015e7b4003aa832c` / `6e47afc6992d3631d67f89cb201d7fe9784ef8a9e8dcb305c1ab5de48550ef8f` |
| Source byte length / lines | 4,243 bytes / 134 lines |
| Original PR2 dossier archive SHA-256 / Git blob | `c47d1fea819e7df59f67bfe8d1bc4dc2650483d03563957145f7331ed099005b` / `143c373f9aae5b9cb24af39abb7d8244362d23b5` |
| Canonical dossier SHA-256 for `matrix.c` | `8998fbe6e0afc9b9a566c1891055f7526949b728356c125504d163eab97529aa` |
| Original pinned queue SHA-256 / Git blob | `b2e418f75645714ad780d004203dc3ce67189eb956db0cfd48f670997b8afb5d` / `777901c5f714764978de3f0623abd35ec21889f7` |
| Queue rows / dossier reconciliation | 14,834 / exact canonical `matrix.c` dossier match |

The source was retrieved from the immutable upstream revision and independently checked against both its Git blob and SHA-256. The original compressed dossier archive and queue were read through the repository's pinned-evidence verifier; the dossier's source blob and pinned revision match the source, and its canonical digest matches the queue row. The original dossier records `semantic_signoff: false`; neither index reconciliation nor source identity is treated as semantic review.

## Attributable native evidence

The existing `.github/workflows/compiled-mgba-semantics.yml` executed on PR2 head `c3a1816c73cc49c66d1e3fa24814f17f6bae0bd5`:

| Provenance | Value |
| --- | --- |
| Actions run / attempt | [#41294215462](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41294215462) / 1 |
| Event / workflow | `push` / `Phase 1 compiled mGBA source semantics` |
| Job / observed result | `124811555123`, `compile-pinned-mgba` / completed `SUCCESS` |
| Native artifact ID / ZIP SHA-256 | `13078003924` / `c06e967795a186bcd6329f3fcbe92aed003ea8e0e03504a0098a9ed0c05bee67` |
| Test fixture | `tests/mgba_bank_boundary.c`; Git blob `b0900bb2ef5932d2d4d299143c2a5249297cd929`; SHA-256 `5c0486fb61699782849bc32776ce375e946b8cd1d7b6cf8efc02c7b4645ab743` |
| Fixture suite | `native_matrix_vfile_fault_controls_v7` |
| Native output SHA-256 | `954fcc63a2a89f32cffee51d725358d77692298d43f4c6b8b150479c6d90a780` |
| Classification | `PASS_PINNED_NATIVE_MGBA_REGRESSION_ONLY`; `NATIVE_EVIDENCE_ONLY` |

The pinned build ran 37 named assertions, all with exit code 0, including Matrix ARM/Thumb refetch, reset, state round-trip, in-bounds mapping, short-read/seek-failure injection, invalid virtual-window and zero-size controls, plus ordinary DMA and ROM boundary controls. Six additional observations are explicitly hazardous:

- `native_remap_leaves_prefetch_stale_until_refetch=true`
- `native_savestate_CRC_mismatch_only_warns=true`
- `native_savestate_external_bank_payload_change_unverified=true`
- `native_matrix_short_read_commits_mapping=true`
- `native_matrix_seek_failure_commits_mapping=true`
- `native_matrix_accepts_physical_range_past_end=true`

In particular, the short-read and failed-seek tests reproduced mapping metadata being committed despite failed/partial backing I/O; the past-end test reproduced acceptance of a physical range extending beyond the backing file. Successful execution proves those observations for the pinned native build and exact fixture, not that the behaviors are safe or compatible. It does not constitute a safe-congruence pass or XGBA runtime test.

## Whole-file source interpretation

The following covers every function in the 134-line source file. Function locations refer to the pinned source.

| Function | Source-grounded behavior | Evidence still needed for a target disposition |
| --- | --- | --- |
| `_remapMatrix` (lines 16–38) | Validates virtual address, size and virtual-window end; computes 512-byte mapping slots and writes mapping metadata; then seeks and reads through `romVf` without checking either return value. It does not validate the requested physical range against backing length. | Atomic mapping behavior on failed/short I/O; physical-range and arithmetic boundary contract; complete consumers and intended XGBA equivalent. The native fault controls reproduce failure behavior, not an acceptable contract. |
| `GBAMatrixReset` (40–50) | Clears mapping slots, sets a 4-KiB size, and invokes two remaps for default physical/virtual regions. | Whether reset is atomic on backing failure and whether CPU prefetch is invalidated across all execution modes. |
| `GBAMatrixWrite` (52–81) | Stores command; remaps on `0x01`/`0x11`; masks physical and virtual address registers; rejects zero input size and stores size in 512-byte units; logs unsupported commands/offsets. | Full register-value, overflow, partial-state and compatibility contract, including all valid/invalid inputs not exercised by the fixture. |
| `GBAMatrixWrite16` (83–98) | Merges each halfword with the register's current high half and delegates to the 32-bit write path. | Complete partial-write behavior and side effects for every register path. |
| `GBAMatrixSerialize` (100–114) | Stores command, physical/virtual address, size, and 16 mapping slots; logs if the configured mapping maximum differs from 16, but still loops over 16. | State format compatibility and the invariant that the maximum remains 16. |
| `GBAMatrixDeserialize` (116–134) | Sets a temporary 512-byte size; restores 16 physical mapping entries and remaps each through `_remapMatrix`; then restores saved command/address/size fields. Remaps inherit unchecked VFile I/O and backing-range behavior. | Whole restore validation/rollback, exact ROM/backing identity, and interaction with the outer state CRC policy. |

This is a source interpretation, not a proof of behavioral equivalence. There is no XGBA-side implementation or contract in this evidence set against which to compare all functions and register paths.

## VFile provider and direct/indirect consumer trace

The fixture does not select a production file backend by path. `tests/mgba_bank_boundary.c` creates its synthetic cartridge with `VFileFromConstMemory` (line 401). At the pinned revision:

| Source | Git blob / SHA-256 | Relevant behavior |
| --- | --- | --- |
| `src/gba/core.c` | `6bfc518bb8899205c07d1d0fc091a287cb42f874` / `47a213e3f4de2299c8859822459a82ef1ae7784b0341ba49d9dd1433b8339596` | `_GBACoreLoadROM` (623–643) dispatches a normal ROM to `GBALoadROM(core->board, vf)` after the optional ELF and multiboot checks. |
| `src/gba/gba.c` | `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e` / `e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b` | `GBALoadROM` (425–440) retains the caller-supplied VFile pointer as `gba->romVf`; the Matrix reset probe uses its `size`, `seek`, and `read` callbacks (297–304). The selected provider is therefore determined by the caller, not by `matrix.c`. |
| `src/util/vfs/vfs-mem.c` | `048194e2dd2d0b3b395a852d2092c694663c88a2` / `6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b` | `VFileFromConstMemory` (62–87) installs `_vfmSeek` and `_vfmRead`; `_vfmSeek` (154–187) bounds the offset and `_vfmRead` (224–234) clips to available bytes. These are the concrete callbacks wrapped by the native fixture. |
| `src/util/vfs/vfs-fd.c` | `2535bd0fb76740745ae038d5523ead28658f1035` / `0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44` | The separate FD provider (`VFileFromFD`, 66–100) installs `_vfdSeek`/`_vfdRead`; on POSIX they delegate to `lseek`/`read` (119–127). It is not the provider used by this in-memory fixture. |

At runtime the Matrix call is indirect through the `VFile` function pointers in `matrix.c:36–37`. The fault wrapper swaps those callbacks only on the exact retained test VFile and delegates normal operations to its original memory-provider methods. This proves callback behavior for this provider and test condition; it does not identify which provider every frontend passes in production.

The direct consumers remain reset (`gba.c:297–304`), selected cartridge writes (`memory.c:811–817, 930–943`), and conditional state handling (`serialize.c:91–93, 236–238`). A newly added focused test exercises the indirect DMA path: with DMA3 channel enabled for one immediate 32-bit unit, source `GBA_BASE_ROM0 + 0x1200` (the active mapped bank) and destination EWRAM, `dma.c:259–294` dispatches the source through `cpu->memory.load32`; `memory.c:44–46` binds that callback to `GBALoad32`. This is a Matrix-backed DMA read witness, not a test of every timing mode, DMA channel, peripheral arbitration, or source/destination interaction.

The additional deserialize-fault witness saves the active Matrix metadata, starts the memory VFile at offset zero, then injects failure for each of the 16 seeks made by `GBAMatrixDeserialize`'s remap loop. It records that the reads continue and the mapping metadata is restored despite failed seeks. This is a reproduced error-path behavior, not a safe restore result. Both v8 cases require exact named PASS records; the deserialize observation is separately required by the fail-closed native gate. The v8 suite is awaiting its exact-head Actions execution; no result is inferred from the prior v7 run.

## Build, dependency and consumer boundary

At the pinned revision `src/gba/CMakeLists.txt:8` includes `cart/matrix.c`. The headless configured build compiled 173/173 source units and selected 364 pinned headers, with 3,126 transitive preprocessor header edges. This proves membership and configured-build compilation only; it is not every mGBA configuration, consumer, frontend final link, or runtime path.

Source inspection identifies these direct consumer candidates:

- `src/gba/gba.c:297–304` probes the ROM identifier through VFile and calls `GBAMatrixReset` when it sees `M`.
- `src/gba/memory.c:811–817, 930–943` routes selected 32-/16-bit cartridge-port writes to `GBAMatrixWrite` / `GBAMatrixWrite16`.
- `src/gba/serialize.c:91–93, 236–238` calls Matrix state serialize/deserialize when Matrix size is nonzero.
- `src/gba/dma.c:259–323` performs transfers via generic CPU memory load/store interfaces and maintains ROM-range address behavior. The new one-unit DMA3 case exercises a Matrix-mapped 32-bit source through that indirect path, but does not close other DMA modes or peripheral interactions.
- `_remapMatrix` calls `romVf->seek` and `romVf->read` through VFile function pointers. The callback implementations and all runtime providers are not closed by object-symbol matching.

The artifact inspected one static library and recorded 2,305 undefined symbol references: 394 code-symbol candidate edges and 11 data/other candidate edges, with 1,900 unresolved or unattributed rows (902 without an in-archive provider, 846 without unique consumer-source attribution, 152 without provider-source attribution, and zero exceeding provider-enumeration limits). Matrix-related records include a `gba.c -> GBAMatrixReset` candidate and a Matrix-to-`mLog` candidate; `GBAMatrixWrite`/`GBAMatrixWrite16` have ambiguous `memory.c.o` attribution, `GBAMatrixSerialize`/`GBAMatrixDeserialize` have ambiguous `serialize.c.o` attribution, and `memset` plus a logging-category provider lack source attribution. These are compiler/linker evidence candidates, not proven executed calls. Frontend/platform final-link resolution, indirect callback closure, and the complete dependency/consumer closure remain `NOT_ESTABLISHED`.

## License and unresolved objections

Pinned `LICENSE` is MPL-2.0 (Git blob `14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e`, SHA-256 `fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85`); `matrix.c` carries an MPL-2.0 notice. The repository README describes a source-pinned research/test environment and says no XGBA unlimited-ROM runtime has been implemented or released. It does not establish whether a future product distributes covered source, an executable containing covered software, both, or neither. No legal conclusion is made; project-specific distribution clearance remains `NOT_ASSESSED`.

Unresolved semantic objections include the six prior observed hazards, the new deserialize failed-seek behavior, Matrix-specific DMA/peripheral arbitration outside the narrow one-unit read case, complete source and runtime consumer closure, full register/state compatibility, and the absence of an XGBA semantic counterpart. The current native tests establish some behaviors but do not discharge these objections.

## Fail-closed disposition

`src/gba/cart/matrix.c` remains `NEEDS_REVIEW`. No `COPILOT_REVIEWED/PASSED` or `UPSTREAM_VERIFIED/PASSED` receipt was added. Reasons:

- `DEPENDENCY_CONSUMER_CLOSURE_NOT_ESTABLISHED`: configured build and partial symbol attribution do not establish all direct, indirect, callback, or final-link consumers.
- `TARGET_SEMANTIC_COUNTERPART_MISSING`: no XGBA mapping proves whole-file and register-path congruence.
- `SUBSTANTIVE_NATIVE_HAZARDS_UNRESOLVED`: executed tests reproduce unchecked mapping, backing-I/O, prefetch, and state-identity behavior.
- `LICENSE_DISTRIBUTION_CLEARANCE_NOT_ASSESSED`: project distribution facts are unavailable.

Synthetic fixtures and successful CI remain evidence only; they never mint a semantic receipt. Historical external-review approvals remain 0/14,834 (0/338 P0), and the authoritative Phase 1 gate remains `FAIL_INCOMPLETE`.
