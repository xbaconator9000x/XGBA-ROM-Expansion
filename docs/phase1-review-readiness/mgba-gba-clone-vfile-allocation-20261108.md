# Phase 1 — pinned GBA clone VFile allocation failure

**Disposition:** compiled, bounded host evidence; not independent approval.
The receipt remains `NEEDS_EVIDENCE` / `FAIL_INCOMPLETE`, with zero independent
approvals. No pinned mGBA source, source pin, shared gate, approval count, or
runtime behavior was changed.

## Distinct source boundary

At mGBA revision `fd9dc5c2cbf234365068855851107e762fc6211b` and tree
`5863e657d270d0fe3ccaa4299f48d5689d74fa1f`, the real GBA callback
`_GBACoreSavedataClone` allocates a savedata buffer, passes it to
`VFileFromMemory`, and frees and clears that buffer if VFile construction
fails. The pinned `VFileFromMemory` body returns null when allocation of its
`VFileMem` wrapper fails. The callback then returns zero. The pinned
`mCoreSaveStateNamed` caller omits savedata extdata for a zero callback result,
but can still serialize its state and return true.

This is distinct from the preceding clone witness, which injected a zero return
at a test-only `mCore.savedataClone` callback. This witness executes the original
extracted GBA callback, original `GBASavedataSize` and `GBASavedataClone`
bodies, original mCore savestate caller and extdata helpers, and the complete
pinned `src/util/vfs/vfs-mem.c` translation unit. Its source records include the
original source Git blobs, full-file SHA-256 values, dossier-row hashes, and
MPL-2.0 notices. The dossier archive SHA-256 is
`1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.
The machine-readable details are in
[`mgba-gba-clone-vfile-allocation-20261108.json`](mgba-gba-clone-vfile-allocation-20261108.json).

## Executed controls

The harness binds `mCore.savedataClone` to the exact extracted
`_GBACoreSavedataClone` body and routes a pinned `GBA_SAVEDATA_SRAM` fixture
through `mCoreSaveStateNamed`. A linker wrapper arms a single allocation
failure only after observing the callback's 32-KiB clone-buffer allocation;
it then rejects the `VFileMem` wrapper allocation used by the pinned
`VFileFromMemory` implementation.

- **Success:** wrapper allocation and close succeed; the output contains the
  savedata extdata and matches the source payload.
- **Injected wrapper-allocation failure:** the original callback frees the
  clone buffer, returns zero, and the original mCore caller returns true with
  state bytes but no savedata extdata.
- **Recovery:** retrying with fault injection disabled succeeds and serializes
  the matching savedata payload.

The verifier rejects four source mutations and six malformed or contradictory
output mutations. The host allocation fault is controlled, not a naturally
observed operating-system memory-pressure event.

## Limits

The callback pointer is connected directly by the harness; full GBA core
initialization and callback-registration execution are not claimed. The full
mGBA core and frontend are not compiled. This is not a native frontend
savestate round trip, filesystem-backed save test, durable persistence or
`.sav` interoperability result, stock gameplay, physical Flash evidence, or
proof of user-visible data loss. No independent semantic approval is implied.
