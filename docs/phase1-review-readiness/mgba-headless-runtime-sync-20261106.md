# Pinned headless save-sync runtime witness

## Result and boundary

This package builds and runs the exact pinned mGBA `mgba-headless` executable
with its Lua scripting support. The test script explicitly loads a generated
32-KiB `.sav` through the pinned `mCoreLoadSaveFile` script binding, performs an
SRAM bus write through the real GBA core, and waits for the real frame-end save
sync path. A test-only `LD_PRELOAD` interposer matches only that save's mapped
file and injects `msync(..., MS_ASYNC) = -1/EIO` in the failure case. The
interposer separately records `MS_SYNC` from VFile unmap/teardown; this distinct
cleanup flush is not counted as another savedata callback attempt.

The observed failure path emits `Savedata failed to sync!` through mGBA's INFO
logger, yet the headless process exits with status 0 after its normal SIGINT
cleanup. The positive control logs `Savedata synced`, also exits 0, and makes
exactly one savedata callback sync and one teardown unmap flush. After the injected failure, a separate fresh
headless process explicitly reopens the same `.sav` and reads the written SRAM
byte. Because shutdown's separate `MS_SYNC` unmap flush succeeded first, this
read is not attributable to the failed callback. It is only an OS-visible,
same-host/page-cache reopen, not proof that the failed callback persisted data
or that data reached durable media.

This is a compiled original headless process and real pinned GBA/VFile path, but
the ROM and Lua scripts are synthetic test inputs and sync failure is injected
at the host `msync` boundary. It is not a GUI frontend, stock game, physical
Flash, power-loss, or independent semantic approval witness. Status remains
`NEEDS_EVIDENCE` / `FAIL_INCOMPLETE`.

## Execution and provenance

The machine-readable record binds the exact pinned source revision/tree,
compressed dossier blob/archive hash, source Git blobs, full-byte SHA-256
values, dossier-row hashes, MPL-2.0 notices, and dependency edges. It
distinguishes four new bounded runtime-path source inspections from reused
source-review identities and dependency-only identities. No source pin or
upstream file is changed.

The existing workflow builds headless with Lua, compiles the small host
interposer, runs a successful sync, an injected EIO sync failure, and a fresh
process reopen after both the callback-failure and final-teardown-failure cases.
The fail-closed tests reject drifted identities, invented
frontend UI/durability/approval claims, missing failure logging, incorrect
process return propagation, invented teardown error reporting, and fabricated
reopen or persistence results.

## Distinct final-unmap fault case

The additional teardown case targets only the final `msync(MS_SYNC)` in the
original pinned POSIX `vfs-fd.c` path. Its preceding frame-end
`msync(MS_ASYNC)` succeeds; the harness then injects EIO at unmap, records the
failed flush, and confirms the headless process exits 0. The callback log still
says `Savedata synced`; no teardown-specific mGBA error log or unmap return
channel exists because `_vfdUnmap` is `void` and discards both `msync` and
`munmap` results. A separate headless process reopens the file and observes the
same-host byte, but that is not evidence that the failed final flush persisted
it. This is a process-level integration of a distinct fault point; it does not
repeat or replace PR #35's lower-level VFile teardown and allocation-failure
work.

## Limits

- The default headless path does not autoload a `.sav`; the test's script calls
  the original `loadSaveFile` API explicitly.
- The sync failure is a controlled host fault injection, not a physical I/O
  failure.
- The failed sync does not change the process return status; the observed INFO
  logger is the visible failure channel in this headless invocation. Teardown
  still performs its distinct `MS_SYNC` unmap flush after the injected
  `MS_ASYNC` callback failure; the witness records that result separately and
  does not treat it as a retry.
- A cold process reading the same `.sav` does not demonstrate power-loss
  durability or independent storage.
- The run does not execute a GUI, stock gameplay, cartridge hardware, or
  physical Flash and does not create an independent review receipt.
- The final `MS_SYNC` failure occurs at teardown after an ordinary successful
  callback; its EIO and same-host reopen are host-injection observations only,
  not durable persistence or proof of a real storage failure.
