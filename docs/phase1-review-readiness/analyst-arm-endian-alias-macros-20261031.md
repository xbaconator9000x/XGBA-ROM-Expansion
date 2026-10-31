# Phase 1 P0 full-source analyst handoff — mGBA ARM little-endian aliases

**Status: REVIEW CANDIDATE, NOT APPROVED.** Prepared as a source-grounded analyst handoff via the repository owner's connected GitHub tools, distinct from the Copilot reviewer. This is one new whole-file candidate, not an increment to source-only partial packet counts, external approvals, or the main gate.

## Immutable original identity and coverage

- Target: `mgba-emu/mgba:include/mgba/internal/arm/macros.h` at pinned revision `fd9dc5c2cbf234365068855851107e762fc6211b`.
- Original Git blob: `4832f054611044e63f1e2393fe4072f48004545a`; **484 bytes, 18 lines** including the terminal newline; SHA-256 `196d6bf1210d223dd58930908dcf5d538a7111fe93e0a0b36b45721cd93dbad9`. The complete pinned file was read; the exact 484-byte text was independently checked with SHA-256 and `git hash-object --stdin`, matching the original packet.
- Original machine dossier: `docs/phase1-review-readiness/packet-0000-0099.json`, index **5**, priority P0, dossier SHA-256 `6508e54c65f1b871f5998bb17dbf6204a73e9428e4ff57734e50e0d1e4dbf558`. Packet records 16 candidate incoming includes and one unresolved lexical `mgba-util/common.h` include. **The analyst did not decompress and rehash the original machine-dossier bytes**. The independent reviewer must do so before attestation.
- [Original header](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/arm/macros.h) and [original packet](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/blob/e349407d5e2cdfeb030f976ab716545875e0f3eb/docs/phase1-review-readiness/packet-0000-0099.json).

## Every line of the target

1. Lines **1–5** retain the original Jeffrey Pfau 2013–2014 MPL-2.0 notice. Lines **6–7** begin the `MACROS_H` guard; line **18** closes it. The guard name is generic; a collision with another independently guarded `MACROS_H` header is a source-level integration risk, **not** an observed collision.
2. Line **9** imports `<mgba-util/common.h>`, resolved to pinned `include/mgba-util/common.h` (Git blob `923e93086adfa09c9a55fcc2f0f6fa4d560e5888`). This resolves the lexical include at source-path level; no executed compiler include-path test is claimed.
3. Lines **11–16** define exactly six object-like aliases: `LOAD_64`, `LOAD_32`, `LOAD_16` to `LOAD_64LE`, `LOAD_32LE`, `LOAD_16LE`, and `STORE_64`, `STORE_32`, `STORE_16` to the corresponding `STORE_*LE`. They **do not themselves** perform loads/stores, evaluate arguments, check alignment, validate buffers, or choose host endianness. Line **17** is blank.
4. At pinned `common.h` lines **146–256**, the `*LE` macros implement host-conditional operations. The big-endian path uses byte swaps or PowerPC load/store byte-reversed assembly, with an explicit `#error` for unsupported big-endian configurations (line **232**). The little-endian path at lines **235–240** casts computed addresses to `uint16_t*`, `uint32_t*`, or `uint64_t*` and directly dereferences them. Consequently caller-provided alignment, accessible storage and C effective-type/aliasing assumptions are **source-level preconditions/risks**. No claim of actual runtime misalignment, undefined behavior reproduction, or compiler validation is made.
5. The header does not change the definitions of `LOAD_*BE` or `STORE_*BE` in `common.h`, and its aliases are not themselves a serialized file format specification.

## Incoming dependency evidence and consumer boundaries

A current-upstream GitHub code search supplied 17 candidate paths; **each of the following was separately fetched from the exact pinned revision and found to include the target header**. The original machine packet's count of 16 is a shard-limited lexical count, **not proof that the pinned tree has only 16 consumers**. This is a verified set of 17, **not an exhaustive pinned-tree grep**:

| Pinned consumer | Include line | Representative source-level use |
| --- | ---: | --- |
| `src/gba/sio/gbp.c` | 8 | include verified; no direct six-alias invocation in inspected file |
| `src/gba/cart/matrix.c` | 8 | `STORE_32` lines 101–104, 112 |
| `src/gba/dma.c` | 8 | DMA save/load `STORE_32/16` lines 382–393, `LOAD_16/32` lines 398–406 |
| `src/gba/sharkport.c` | 8 | load/store alias uses observed |
| `src/gba/serialize.c` | 8 | `STORE_32` savestate header lines 28–31; explicit `STORE_64LE` line 32 |
| `src/gba/video.c` | 10 | load/store alias uses observed |
| `src/gba/io.c` | 8 | load/store alias uses observed |
| `src/gba/audio.c` | 8 | load/store alias uses observed |
| `src/gba/bios.c` | 9 | include verified; no direct six-alias invocation in inspected file |
| `src/gba/cart/gpio.c` | 8 | load/store alias uses observed |
| `src/gba/cart/unlicensed.c` | 8 | load/store alias uses observed |
| `src/gba/savedata.c` | 8 | savedata state `STORE_32/16` lines 723, 729–731; `LOAD_32/16` lines 744–746, 754 |
| `src/gba/memory.c` | 9 | BIOS/EWRAM/IWRAM `LOAD_32` lines 386, 397, 400 |
| `src/gba/cart/ereader.c` | 9 | load/store alias uses observed |
| `src/gba/renderers/gl.c` | 11 | sprite OAM `LOAD_16` lines 1809–1812 |
| `src/gba/renderers/software-private.h` | 9 | include verified; no direct six-alias invocation in inspected file |
| `src/gba/renderers/video-software.c` | 9 | `LOAD_*` use observed at line 121 |

These are pinned **source** observations. `src/gba/CMakeLists.txt` lines **2–36** list the relevant GBA core and renderer source files, and lines **58–62** export the groups. The actual feature-gated root CMake configuration, compiler preprocessor expansion, linker selection, host alignment, endianness, effective types, binary layout and native execution were **not** tested. The 17 include edges must not be counted as 17 semantic dispositions.

## Review risks, licensing and test distinctions

- **Semantic risk:** aliases force little-endian interpretation irrespective of host; correct for the GBA representation only under the caller's buffer/format contract. Endianness is implemented by `common.h`, not by this 18-line file. On little-endian builds, the cast-and-dereference implementation may require alignment and effective-type justification. Review consumers and serialized-state structs before claiming portability.
- **Scope boundary:** no whole-program closure, exhaustive pinned-tree include search, executed C/C++ preprocessing, native compiler/linker, emulator runtime, stock gameplay, `.sav` restart, interrupted physical Flash, or combined-distribution proof is asserted.
- **License:** original file notice is MPL-2.0 and pinned upstream `LICENSE` (blob `14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e`) identifies Mozilla Public License 2.0. File-scoped **source mapping** can assess this notice; actual future combined distribution, notices and corresponding-source obligations remain **NOT CLEARED**.
- **Original machine evidence:** original packet identity and recorded digest inspected; original compressed dossier bytes not independently rehashed by this analyst. Copilot must verify original bytes and SHA-256, source and dependency blobs, licensing, all 18 lines and any unresolved objections independently.
- **Reviewer decision:** only a distinct reviewer may produce a complete per-file receipt, passing fail-closed validator and exact-head CI with attributable attestation. A source-only analyst dossier, CI success or user-authored PR review does **not** constitute approval. Maintain legacy external approvals 0/338 P0 and 0/14,834 total, and main `FAIL_INCOMPLETE`.

**Reviewer questions:** Is the 17-path incoming include set complete at the pinned revision? Does `MACROS_H` collide with any other included guard? Are the unaligned/effective-type and big-endian caveats adequately scoped to the separate `common.h` implementation rather than misrepresented as proven runtime defects? Do feature flags materially change the header contract? Can MPL-2.0 be marked cleared **only for file-scoped source mapping**? If any mandatory per-file objection remains unresolved, record `NEEDS_REVIEW`, not a passing receipt.
