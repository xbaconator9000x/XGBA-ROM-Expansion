# Pinned mCore save-caller allocation recovery witness

Status: **NEEDS_EVIDENCE / FAIL_INCOMPLETE**. This package is a bounded caller/backend test, not an approval or a compatibility verdict.

## Reachability and ownership conclusion

The pinned script adapter in `src/core/scripting.c` exposes `mCoreLoadSaveFile` as `mCore.loadSaveFile`. The pinned `mCoreLoadSaveFile` body in `src/core/core.c` calls `VFileOpen(path, O_CREAT | O_RDWR)`. If that returns `NULL`, the caller returns `false` before invoking `core->loadSave` or `core->loadTemporarySave`.

For the POSIX backend, `VFileOpen` dispatches to `VFileOpenFD`, which opens the path and passes the descriptor to `VFileFromFD`. After successful `fstat`, a `malloc(sizeof(struct VFileFD))` failure returns `NULL` without closing the descriptor. Therefore the real save caller is reachable, does report failure to its caller, and cannot close the descriptor on that branch because it receives no VFile. The lower backend leaks the descriptor. A later caller retry can succeed, but it does not clean up the descriptor from the failed attempt.

## Compiled matrix

The runner verifies the exact mGBA pin, source blobs/full-byte SHA-256 values, dossier row hashes and compressed dossier hash. It extracts and hashes the original `mCoreLoadSaveFile` body and compiles that body with the original `src/util/vfs.c` dispatcher and complete `src/util/vfs/vfs-fd.c` translation unit. The `mCore` object is an explicitly narrow fixture, not the complete upstream header/core implementation.

The bounded controls exercise:

- Normal call: caller returns true; fixture save callback receives and closes the VFile.
- Host-injected allocation failure: caller returns false; save callback is not called; `fcntl` confirms the descriptor remains open.
- Retry: a second call succeeds and its VFile is closed by the callback fixture, while the first descriptor remains open until explicit harness cleanup.
- Open-failure control: caller returns false on `ENOENT`, with no successful open, allocation, or save callback.

Three caller-source mutations and six contradictory/malformed output mutations are rejected. The machine receipt is checked against the execution output and preserves the exact source identities and evidence scope.

## Provenance and objections

The pin is mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`, tree `5863e657d270d0fe3ccaa4299f48d5689d74fa1f`. The original compressed dossier is blob `3b982876c7d810a827af8c80c7e5d9231fdaa327`, SHA-256 `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`. Every listed upstream file is identified by Git blob, full source SHA-256, canonical dossier-row SHA-256, and MPL-2.0 licensing in the JSON receipt.

Allocation failure is injected through a host linker wrapper; it is not a naturally observed OS failure. The extracted upstream caller body is executed against a narrow `mCore` fixture. The retry callback is a controlled close-only fixture, not the GBA savedata callback. The descriptor observation is process-local and the harness explicitly cleans up after recording it. No full core/frontend, GUI, durable persistence, `.sav` interoperability, stock gameplay, or physical Flash behavior is established.

Independent approvals remain `0`; the package leaves Phase 1 at **NEEDS_EVIDENCE / FAIL_INCOMPLETE**.
