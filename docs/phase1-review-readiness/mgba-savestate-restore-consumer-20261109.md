# Pinned mGBA savestate restore-consumer witness

Status: **NEEDS_EVIDENCE / FAIL_INCOMPLETE**. Independent approvals: **0**.

This package traces the pinned `mCoreLoadStateNamed` consumer path after the
previous save-side clone witness. The source path is:

`headless-main.c (flags 0) -> mCoreLoadStateNamed -> mCoreExtractState ->
mStateExtdataDeserialize -> EXTDATA_SAVEDATA -> _GBACoreSavedataRestore ->
GBASavedataLoad or GBASavedataMask/Unmask`

Pinned source inspection found that `mCoreExtractState` ignores the return from
`mStateExtdataDeserialize`. If the fixed-size core state is readable, it can
return that state even when extdata parsing fails. `mCoreLoadStateNamed` then
loads core state and may return true without calling `savedataRestore` if no
savedata item was recovered. This is a source-grounded behavior; the controlled
host witness exercises malformed extdata buffers, not naturally corrupted
frontend savestates.

The compiled host witness executes exact extracted bodies for the extdata
deserializer/state extractor/loader, GBA restore callback, SRAM load/mask/
unmask functions, `GBASavedataInit` and its timer callback, the complete pinned
`vfs-mem.c` translation unit, and the extracted `VFileReadline` helper installed
by that backend. It covers absent
extdata, a short header, a short savedata payload, a complete savedata payload
with immediate writeback, the headless-style flags-zero
deferred VFile ownership/unmask path, and a valid retry after a malformed
payload. The host allocation tracker checks cleanup; a wrapper observes that
the flags-zero restore VFile remains owned by the mask and is closed on unmask.

The harness uses mock host memory mapping functions and controlled in-memory
VFiles. It does not execute the full mGBA core, the headless/GUI frontend,
native filesystem persistence, ordinary user-generated savestates, stock
gameplay, or physical Flash. The `GBASavedataInit` non-autodetect branch is
compiled but not executed; non-SRAM initializer branches are fixture stubs. The
callback-list-size accessor is a host shim equivalent to the pinned generated
vector accessor, and no callbacks are registered. The source records bind each
of 19 selected files to its pinned Git blob,
full-byte SHA-256, canonical dossier-row SHA-256, scope, dependency edges, and
per-file objections. All selected files carry MPL-2.0 notices; transitive
distribution licensing is unresolved.

Five source-body mutation controls and six contradictory output mutations
fail closed. The machine-readable receipt remains non-approving regardless of
the test outcome.
