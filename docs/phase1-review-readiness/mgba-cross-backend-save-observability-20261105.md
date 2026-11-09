# Phase 1 — pinned mGBA cross-backend save-error observability

**Disposition:** source-only caller/observer closure plus references to prior
native witnesses; non-approving. No upstream source, backend pin, save behavior,
shared gate, approval count, or runtime code changed. The evidence does not
establish physical Flash persistence, power-loss durability, or a stock-game
failure.

## Result

At pinned mGBA revision
`fd9dc5c2cbf234365068855851107e762fc6211b`, save-backend failures do not produce
a persistence result through the core shutdown API or the reviewed frontend
lifecycle return paths. There is, however, an explicit source-level sync-failure
log, with frontend visibility conditional on each logger's configuration:

* `GBASavedataClean` does not return the `VFile.sync` result. The fd backend's
  mapped `msync(MS_ASYNC)` result and the stdio backend's flush result are
  discarded by that void caller. Prior native witnesses observed the dirty
  flag clear before injected sync failure; they did not observe a retry absent
  another write.
* `GBASavedataDeinit` and the `VFile.unmap` interface are void. The fd backend
  ignores `msync(MS_SYNC)` and `munmap` results; the stdio backend ignores
  buffered write/seek results while unmapping. The caller has no return channel.
* Both tested backends can return a close failure, but `GBAUnloadROM` ignores
  the close result. Its callers and the core `deinit` interface are void.
  `mCoreThreadEnd` is also declared void.
* The `savedataUpdated` callback is a dirty-to-clean/save-data-modified event,
  not a persistence acknowledgment. The prior native failed-sync callback
  witness observed the event despite the failed sync. This does not establish
  that any UI presents a persistence error.
* The Qt and SDL teardown paths discard the void shutdown/deinit operations.
  SDL's returned `didFail` reflects load, audio, or emulation-thread failures,
  not VFile teardown. Qt's `CoreManager` save-file message concerns opening or
  autoloading a save, not a later flush/unmap/close failure.
* The reviewed libretro GBA path uses an in-memory VFile backed by a buffer
  returned through the libretro memory API; the fd/stdio failure cases are not
  executed there. Its unload entry point is void. The Python binding's CFFI
  finalizer calls `native.deinit`, also void, and the callback adapter does not
  register `savedataUpdated`.

### Sync-failure log versus persistence status

`GBASavedataClean()` at pinned `src/gba/savedata.c:600` emits the INFO message
`Savedata failed to sync!` when `VFile.sync` returns false. This is a source-level
log path, not a success/failure return from shutdown, and the new logger closure
was reviewed statically rather than executed with an injected failure:

* Qt's `CoreController` forwards core messages to `LogController::postLog`;
  accepted messages emit `logPosted`, which `LogView` can display. The INFO
  message is not the `mLOG_ERROR` case used by the Qt error-dialog path, and
  filters/views/configured sinks may affect visibility.
* SDL routes through the standard logger. Its default `logLevel` is
  `mLOG_WARN | mLOG_ERROR | mLOG_FATAL`, so this INFO message is filtered by
  default. Configuration can change the filter; output additionally depends on
  stdout/file sinks.
* Libretro maps `mLOG_INFO` to `RETRO_LOG_INFO`, but only forwards it when the
  frontend supplied `RETRO_ENVIRONMENT_GET_LOG_INTERFACE`.
* Python can route logs through `mgba.log.Logger` after a caller installs it as
  the default logger; the base logger prints, while `NullLogger` suppresses.

These are conditional logging routes, not evidence that a frontend displays or
acts on the message. The earlier script callback is a separate signal: its
published meaning is save-data modification/dirty-to-clean, not persistence
success. The sync log, optional consumers, and prior native callback observation
are distinguished in the machine-readable matrix below.

## New source closure and provenance

The 16 newly reviewed whole files are the core helper and API/thread contracts,
the core logger, Qt API declarations and log/entry-point consumers, the libretro
API contract, and the Python binding/logger. Exact Git blob IDs, full-byte
SHA-256 digests, canonical machine-dossier row SHA-256 digests, licenses, and
line-anchored evidence are recorded per file in
[`mgba-cross-backend-save-observability-20261105.json`](mgba-cross-backend-save-observability-20261105.json).
The matrix is validated against mGBA's compressed dossier blob
`3b982876c7d810a827af8c80c7e5d9231fdaa327`, full-file SHA-256
`1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`, and the
exact pinned source tree in checkout mode.

The pinned root `LICENSE` is MPL-2.0 (Git blob
`14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e`, SHA-256
`fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85`, canonical
dossier row SHA-256
`b23d241b38f5808b3714b8f4f5d255db9a47e3ab9b114972bcc7e042bc92acf0`). The
libretro API header carries its own MIT permission notice. The Python `_builder.py`
has no embedded license header; its applicable repository-level license is
recorded separately. No upstream source was copied into or modified in this
repository.

Twelve prior source pins are reused by reference rather than re-inventoried:
fd/stdio VFile contracts, savedata and GBA teardown, core deinit, script callback
registration/meaning, and the previously reviewed Qt/SDL/libretro implementations.
Their prior workpapers are named in the JSON matrix. In particular, the four
front-end implementation files were already whole-file-pinned in the callback
package; this package uses that evidence rather than claiming them as new files.

## Caller and observer scope

The machine-readable matrix classifies 15 edges as `propagated`, `conditional`,
`discarded`, or `unproven`, separately recording whether each was source
reviewed or previously executed natively. The four newly traced INFO-log routes
are marked `conditional` and `source_review_only`; they were not observed in a
native frontend run. Six injected-failure observations
link to the already-existing fd/stdio native witnesses; this package adds no
native save-backend case and does not repeat those experiments.

Identified but not reviewed as part of this bounded closure:
`src/platform/headless-main.c`, `src/platform/3ds/main.c`,
`src/platform/3ds/3ds-vfs.c`, `src/platform/psp2/main.c`,
`src/platform/psp2/sce-vfs.c`, `src/platform/switch/main.c`,
`src/platform/wii/main.c`, and `src/platform/windows/vfs-w32.c`. These were
identified from the pinned platform tree listing; no behavior is inferred for
them or for unlisted frontends/backends.

## Validation and limits

The new fail-closed validator checks the source tree revision and blobs, all 16
whole-source SHA-256 values, source anchors, license notices, the complete
compressed dossier identity and canonical rows, the classification of every
edge, and the six prior failure-control records. It rejects changed pins or
dossier hashes, invented error propagation, claims that unexecuted paths were
observed, and any injected-error record that claims persistence success. Its
local `--source-dir` mode checks each fetched source file byte-for-byte but does
not attest whole-tree identity; the existing workflow uses `--checkout`.

The exact-head PR Actions run
[#41983943123](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41983943123),
attempt 2, completed successfully at
`85538bd4d9bce9cc5bb63ae678860d79e1bd0e68`. Job `127166986788` completed
successfully; all reported steps passed. Its logs show the focused suite ran
**19 tests**, and checkout-mode verification printed
`PHASE1_MGBA_CROSS_BACKEND reviewed_new_files=16 edges=15 injected_controls=6`.
The verifier checked the exact pinned checkout, source blob/full-byte hashes,
anchors and canonical dossier rows. The earlier run #41983780464 for the
preceding code-bearing commit was `action_required` with zero jobs; it was a
permission blocker, not a code failure, and was superseded by this successful
exact-head run.

The focused suite contains 19 positive/adversarial tests. Prior native
observations remain host-specific controlled injections; this package does not
run a real Qt/SDL/libretro/Python frontend, stock gameplay, a physical cartridge,
or a power-loss/reboot experiment. The four logger routes remain source-only
conditional classifications, not observed frontend displays or persistence
acknowledgments. A fresh-process read is not proof of durable storage. The
authoritative Phase 1 gate remains `FAIL_INCOMPLETE`, with no new approval or
semantic receipt.
