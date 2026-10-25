# Phase 1 P0: pinned mGBA native ROM banking boundary probe (26 Oct 2026)

**Review state: SOURCE-ANCHORED TEST IMPLEMENTATION; NOT YET COMPILED OR EXECUTED.** Phase 1 semantic gate remains `FAIL_INCOMPLETE`. No XGBA runtime, ROM expansion, patch, independent file signoff or native compatibility certification is claimed.

## Durable test files

- `tests/mgba_bank_boundary.c`: synthetic in-memory 16 MiB conventional ROM and 64 MiB native Matrix test cartridge, with no copyrighted game assets. The fixture compares data reads with ARM and Thumb instruction-prefetch values after explicit refetch, observes existing prefetched opcodes around a Matrix remap, and records native rejected/accepted mapping cases.
- `tests/CMakeLists.txt`: external executable linked against a fresh, unchanged, pinned mGBA static library (rather than compiling a mock emulator).
- `tests/run_pinned_mgba_boundary.sh`: clones/checks out the immutable mGBA commit, verifies source Git blob hashes, compiles and runs the test, and writes logs/hashes into `audit-output`.

**To run on a Linux machine with Git, GCC and CMake:** from the XGBA repository root, run `bash tests/run_pinned_mgba_boundary.sh`. It creates an ignored `upstream/mgba` source checkout and `build-mgba-boundary` build folder. Report both configure/compiler failures and test failures; never silently replace a failed fixture with a simulated result.

An attempt to create `.github/workflows/mgba-bank-boundary.yml` through the current GitHub connection was rejected by tool safety checks; no workflow was installed, and no workflow result is claimed.

## Pinned upstream evidence

| Source | Pinned blob | Behaviour that the fixture interrogates |
| --- | --- | --- |
| [mGBA Matrix handler](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c#L16-L79) | `9ccbe883235b98bcf56cd609015e7b4003aa832c` | Mapping command, window checks, 512-byte units, native virtual/physical bank selection |
| [mGBA Matrix serialization](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c#L100-L133) | same blob | 16 recorded native cartridge mappings, VFile rereads during state restoration |
| [mGBA ROM image loader](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/gba.c#L425-L493) | `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e` | For images above 32 MiB, header 0xAC == 'M' selects native Matrix, otherwise distinct behavior |
| [mGBA ARM and Thumb stepping](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/arm/arm.c#L198-L225) | `0b92d7f55f1fb853d4b1b9c9163ee086126066e2` | Fetch uses CPU active region/mask and two-entry prefetch, not ordinary data-read callback |
| [mGBA active-region selection](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L280-L377) | `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc` | Valid ROM active region selected from memory->rom and romMask; does not itself prove mid-instruction remap |

## Scope of positive controls (test implementation only)

1. Vanilla 16 MiB non-M image retains conventional ROM aperture; ordinary data reads and explicit ARM/Thumb refetch agree.
2. Matrix M-marker image selects the native 16 MiB active aperture; two distinct backing physical pages copied into its small virtual window can be read/fetched through ARM.
3. Thumb fetch and data read agree following two native Matrix mappings to an allowed window.
4. Native Matrix rejects a virtual mapping outside the restricted window and rejects zero-length size update.

These tests are not yet passing evidence. When run, preserve the *actual process exit code*, compiler log and stdout/stderr.

## Important negative control / unresolved defect

Pinned `_remapMatrix()` validates virtual address and mapping-size/window constraints, then calls `gba->romVf->seek` and `gba->romVf->read` **without checking return values or verifying `paddr + size <= backing file length`**. This is a source-grounded missing validation, **not** a proved exploitable failure or an XGBA fix. The fixture probes a 512-byte native mapping starting only 256 bytes before the synthetic backing EOF and reports whether mapping metadata accepts the request. A future XGBA bank manager MUST bound-check physical start/length safely, reject missing banks before mutating state, and fail closed on VFile short reads, including overflow tests.

Similarly, writing new ROM bytes to the mGBA backing allocation is not a documented prefetch invalidation point. The probe records whether already-prefetched instructions remain stale until an explicit branch/refetch. This **does not** prove safe asynchronous bank switching; future XGBA mode must define instruction-boundary arbitration and cache/prefetch lifetime.

Unaddressed: real CPU execution across dynamic bank changes; queued DMA, interrupt/BIOS effects, simultaneous EEPROM/e-Reader accesses, Matrix/native coexistence, debugger/rewind, save-state migration, backing identity/hash checks. Those require separate fixture families, source-level flow review and independent semantic signoffs. Do not use passing positive fixtures to close these obligations.

## Next step

**Run the pinned executable test, fix compilation errors if any, capture hash-bound results and classify real observations.** Continue with DMA, EEPROM/e-Reader and Matrix serialization fixtures. Existing `docs/PHASE1_P0_ROM_FETCH_ARBITRATION_REVIEW_2026-10-25.md` remains authoritative for open obligations. No semantic disposition is approved by this document.
