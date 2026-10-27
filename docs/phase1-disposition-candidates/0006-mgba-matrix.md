# Phase 1 semantic disposition candidate 0006 — mGBA Matrix cartridge mapping

**State: PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** Analyst-prepared whole-file inventory; it must not increment independent approval counts or be interpreted as a runtime certification.

## Exact file and dependencies

- Repository: `mgba-emu/mgba`; pinned commit `fd9dc5c2cbf234365068855851107e762fc6211b`.
- Entire [`src/gba/cart/matrix.c`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c), Git blob SHA-1 `9ccbe883235b98bcf56cd609015e7b4003aa832c`. Includes six functions: private `_remapMatrix`; exported `GBAMatrixReset`, `GBAMatrixWrite`, `GBAMatrixWrite16`, `GBAMatrixSerialize` and `GBAMatrixDeserialize`.
- Direct includes: Matrix API/constant definitions, ARM macros, GBA core/memory, savestate structures and VFile ABI. Related pinned source: [ROM load/reset and identity](../PHASE1_P0_MGBA_MATRIX_ROM_IDENTITY_VFS_2026-10-27.md), [savestate replay](../PHASE1_P0_FIRERED_MGBA_SAVESTATE_MATRIX_2026-10-27.md), and [CPU prefetch lifecycle](../PHASE1_P0_MGBA_MATRIX_PREFETCH_LIFECYCLE_2026-10-27.md).

## Complete function-level inventory

**`_remapMatrix` (private):** Rejects misaligned/out-of-window virtual addresses, invalid mapping lengths and virtual ranges exceeding the native 8 KiB window. Calculates a 512-byte slot start and count, records each slot's physical address, then seeks and reads backing VFile bytes into the ROM buffer. No local check of VFile seek/read return values or backing-file physical bounds occurs. Mapping metadata is updated *before* the VFile operations; on short read or failed seek the metadata and buffer can disagree. The guard on size (`0xFFFFE1FF`) excludes a single 8 KiB mapping request; the 8 KiB window can be populated via smaller remaps. Do not infer an accepted 8 KiB request from the window size alone.

**`GBAMatrixReset`:** Clears 16 slot mappings and makes two 4 KiB remaps, virtual offsets `0x0000` and `0x1000`, physical offsets `0x0000` and `0x0200` respectively. The second physical source overlaps the first; this is authored native Matrix behavior, not a generic linear-ROM mapping.

**`GBAMatrixWrite`:** Register offset `0x0` stores the command and triggers remap only for `0x01` or `0x11`. Offset `0x4` masks the physical start to 26 bits; `0x8` masks virtual start to `0x007FFFFF` (the later remap guard is stricter); `0xC` rejects zero and stores a size shifted left nine bits. Other commands/writes are logged as stubs. These registers do not provide unlimited physical addressing.

**`GBAMatrixWrite16`:** Dispatches only register offsets `0x0, 0x4, 0x8, 0xC`, combining the 16-bit value with the corresponding register's current upper 16 bits and passing the result to the 32-bit write handler. The size register's internal byte-unit representation versus write-handler 512-byte-unit interpretation is a **separate width/unit compatibility question**, not yet tested for all halfword write sequences.

**`GBAMatrixSerialize`:** Stores command, physical address, virtual address, size and 16 mapping entries. It logs an error if the compile-time mapping cardinality is not 16, but does not serialize the external VFile bytes or content digest.

**`GBAMatrixDeserialize`:** Logs the same cardinality concern; temporarily sets size to 512 bytes, replays 16 saved physical mapping entries into successive virtual slots through `_remapMatrix`, then restores command, physical address, virtual address and size. It does not locally validate source VFile identity, seek/read results or CPU prefetch coherence.

## Reviewer requirements and gate

Independent review must cover the entire pinned file and its callers, bitmask arithmetic, exact register-width behavior, command/size boundaries, mapping metadata versus backing-byte consistency, compiled ABI, truncated/changed VFiles, CPU prefetch and savestate restore ordering. Include native runtime evidence for the halfword size-register path and invalid/short-read mapping cases; check editor/tool assumptions about bank identity and finite address ranges. A reviewer must provide an actual identity, dated verdict and rationale before this candidate could contribute to the gate.

**Gate contribution: 0. Phase 1: FAIL_INCOMPLETE. Independent whole-file approvals: 0/14,834. No Phase 2 implementation.**
