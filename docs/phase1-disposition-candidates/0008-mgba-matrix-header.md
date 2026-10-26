# Phase 1 semantic disposition candidate 0008 — mGBA Matrix public-internal C interface

**State: PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** This is an analyst-prepared whole-file candidate, not independent approval, compiled ABI certification, or runtime proof.

## Immutable identity and entire-file inventory
- Upstream: `mgba-emu/mgba`; pinned commit `fd9dc5c2cbf234365068855851107e762fc6211b`.
- Exact [`include/mgba/internal/gba/cart/matrix.h`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/include/mgba/internal/gba/cart/matrix.h); Git blob SHA-1 `27e32a75c0f521dac9ded53821591485089d7b76`, directly verified by the pinned upstream file response.
- Whole-file scope: MPL 2.0 copyright/license header; `GBA_MATRIX_H` include guard; `<mgba-util/common.h>` include; `CXX_GUARD_START` / `CXX_GUARD_END` language-linkage macros; `GBA_MATRIX_MAPPINGS_MAX 16`; one struct; two forward-declared struct tags; five function prototypes. No executable statements, inline function bodies, runtime validation or bank-I/O implementation appear here.

## Struct and function contract
- `struct GBAMatrix` contains four `uint32_t` fields in order: `cmd`, `paddr`, `vaddr`, `size`, followed by `uint32_t mappings[16]`. The source declares **20 32-bit scalar elements** (nominally 80 bytes if `uint32_t` is four bytes and ABI adds no padding); **do not assume 80-byte compiled `sizeof`, alignment or serialization format without checking actual target ABI**.
- Forward declaration `struct GBA` supports `GBAMatrixReset(struct GBA*)`, `GBAMatrixWrite(struct GBA*, uint32_t address, uint32_t value)`, and `GBAMatrixWrite16(struct GBA*, uint32_t address, uint16_t value)`. The declarations establish call signatures and argument widths, **not** accepted register addresses or remap semantics.
- Forward declaration `struct GBASerializedState` supports `GBAMatrixSerialize(const struct GBA* memory, struct GBASerializedState* state)` and `GBAMatrixDeserialize(struct GBA* memory, const struct GBASerializedState* state)`. The parameter identifier `memory` is not a different type; `const` applies to the pointed-to struct in the serialize declaration. The header itself neither stores external ROM bytes nor checks VFile identity.

## Dependencies and compatibility consequences
- [Pinned `src/gba/cart/matrix.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c), Git blob `9ccbe883235b98bcf56cd609015e7b4003aa832c`, implements these five declared functions and a private remapping routine. The [whole-file implementation candidate 0006](0006-mgba-matrix.md) and [pinned mapping dossier](../PHASE1_P0_MGBA_MATRIX_ROM_IDENTITY_VFS_2026-10-27.md) cover the distinct implementation-level limitations.
- The constant 16 fixes the *declared* slot array cardinality. Changing it could change struct layout, serialization assumptions and consumer ABI; it does **not** enable unlimited ROM addressing. No external-resource identity/version field appears in this declaration.
- `<mgba-util/common.h>` and `CXX_GUARD_*` introduce a compile-time portability dependency; this file alone does not establish actual C++ linkage, compiler packing or calling convention.
- The distinction between source declaration, compiled ABI, serialized savestate record and VFile content is essential for a future XGBA adapter. Do not conflate them.

## Independent reviewer obligations
Verify every declaration against the exact pinned blob and all definitions/callers across the pinned tree; compile with the pinned toolchains to measure `sizeof`, `offsetof`, alignment and symbol/linkage properties; verify serialization cardinality and format under changed mappings; test the 16-bit write interface and restore path with native runtime fixtures; reconcile VFile and prefetch assumptions. Identify the actual reviewer, date, complete-file verdict and supporting evidence before gate ingestion.

**Verified:** complete pinned header, Git blob identity, declaration-level dependency on pinned implementation. **Unverified:** all callers, compiled ABI, runtime/savestate and editor interoperability, independent review. **Gate contribution: 0; Phase 1 FAIL_INCOMPLETE, 0/14,834 approved.**
