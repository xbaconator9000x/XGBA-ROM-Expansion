# POSIX savedata truncate-failure witness

## Finding and bounded call path

At pinned mGBA revision `fd9dc5c2cbf234365068855851107e762fc6211b`, `_vfdTruncate` calls `ftruncate(vfd->fd, size)` and discards its result (`src/util/vfs/vfs-fd.c:232`). `GBASavedataInitSRAM` grows a short file through the VFile's void `truncate` callback, then maps the requested SRAM size and fills the tail (`src/gba/savedata.c:327`). `GBALoadSave` dispatches the configured savedata type, and `_GBACoreLoadSave` forwards the registered core callback (`src/gba/gba.c:496`, `src/gba/core.c:655,1675`).

This closes one distinct POSIX boundary not exercised by the prior teardown and short-write receipts: the outcome when a backing-file growth operation fails while the SRAM initializer proceeds to access the requested mapping. It does not characterize other savedata types or backends.

## Executable evidence

The runner validates the pinned source blobs, full-file SHA-256 values, dossier blob/archive identity, canonical dossier rows, and selected original function-body hashes. It compiles those extracted production bodies together with the original POSIX `vfs-fd.c` translation unit. The host fixture starts with a one-byte save and seeds the existing SRAM type before invoking the extracted `_GBACoreLoadSave` callback.

The native Linux run passed these cases:

| Case | Observation |
| --- | --- |
| Normal growth | `ftruncate` succeeds; initialization fills the 32 KiB extent while preserving the original first byte; original `GBAUnloadROM` cleanup completes. |
| Injected `EIO` | A linker wrapper returns `-1` before the host syscall; the original initializer proceeds and the short shared mapping raises `SIGBUS` in an isolated child. |
| Recovery after `EIO` | A separate invocation with injection removed succeeds and cleans up. |
| Injected `ENOSPC` | Same bounded signal outcome under a distinct injected errno. |
| Recovery after `ENOSPC` | A separate invocation with injection removed succeeds and cleans up. |

Three source mutations and eight contradictory output mutations are rejected. The focused Python tests also verify missing-case rejection and fail closed if the receipt is changed to an approval state. Local compiled witness execution passed using exact pinned source files in `/tmp`. Exact-head CI is tracked independently; local validation is not a substitute for it.

## Evidence limits and disposition

The failure is injected, not a naturally observed storage error. This is a controlled Linux mapping result, not proof of user-visible save corruption, broad VFile behavior, frontend behavior, or a durable `.sav` outcome. On the fault path, the child is terminated by `SIGBUS`; production teardown is only observed after successful initialization. The harness directly seeds SRAM rather than executing ROM initialization, autodetection, or the `GBAMemoryWrite8` caller. Flash, EEPROM, gameplay, physical Flash, and full core/frontend translation units are outside this witness.

The machine receipt is deliberately `NEEDS_EVIDENCE` / `FAIL_INCOMPLETE`, records zero independent approvals, and identifies the original source records as reused identities rather than new whole-file reviews. No semantic approval or gate change is claimed.
