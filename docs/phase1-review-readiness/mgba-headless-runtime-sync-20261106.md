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
distinguishes five bounded runtime-path source inspections from reused
source-review identities and dependency-only identities. No source pin or
upstream file is changed.

The existing workflow builds headless with Lua, compiles the small host
interposer, runs successful and injected sync cases, the final-teardown failure,
the targeted existing-save open failure, and separate-process reopen controls.
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

## Distinct existing-save reopen failure

The new case follows the original pinned caller chain: the Lua `BOOL`
`loadSaveFile` binding calls `mCoreLoadSaveFile`, which opens the supplied path
with `O_CREAT | O_RDWR`; the pinned POSIX `VFileOpen` dispatcher selects
`VFileOpenFD`, whose `open` result becomes a null VFile on failure. A compiled
`mgba-headless` process first creates and writes the controlled `.sav`; a later
process attempts to reopen that existing path while the host interposer returns
`-1/EIO` only for that exact path. The script records and asserts the API's
`false` result. It handles the failure instead of failing script loading, so
the headless process is expected to exit normally. The harness also compares
the full save hash before and after the failed open, then starts another
separate process without injection and requires a successful reopen/read of
the original byte.

The additional `src/util/vfs.c` provenance is pinned to Git blob
`3158c52659a83333cb23aeb0dd7ea4bba35908fc`, full-source SHA-256
`7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06`, and
canonical dossier-row SHA-256
`47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2`.
It is a bounded dispatcher-path review, not a whole-file approval.

This is a distinct POSIX open-boundary fault, not another `msync`/unmap/close
case and not an allocation failure. The later process reads the same-host save
after a previously successful write and teardown; this is a recovery control
for an injected open failure, **not** evidence about failed flush persistence,
power-loss durability, or independent media. The machine record marks this
case `REQUIRED_IN_EXISTING_CI`; the Actions output, rather than the static
contract, is the execution evidence.

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
