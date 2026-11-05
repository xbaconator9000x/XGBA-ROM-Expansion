# Headless timeout and Qt feasibility diagnosis

## Result

This is a diagnostic follow-up to the existing six-source feasibility matrix,
not another frontend runtime witness. It remains `NEEDS_EVIDENCE` /
`FAIL_INCOMPLETE`.

The pinned headless source registers a `SIGINT` handler, initializes the
default GBA exit SWI as `3`, and continues the core run loop until its dispatch
flag is set by a shutdown/SWI callback. A TERM-based timeout does not invoke
that handler, so it can kill the process before the normal `unloadROM` and
`deinit` cleanup path. In the prior synthetic-ROM attempt, the observed
repeating BIOS SWI `00` did not reach the configured exit SWI or save/shutdown
path. The GBA savedata object starts with a null VFile, and the headless caller
does not autoload a normal save file. Fixing the timeout signal alone would
therefore not demonstrate a file-backed `.sav` lifecycle.

## Bounded signal controls

The original pinned headless binary, command, full output, exit status, and
elapsed time from the earlier attempt were not retained. I did not reconstruct
or invent those values. Instead, two explicitly synthetic host controls
reproduced the timeout signal distinction in 0.40 seconds each:

- TERM to a process that installs only a SIGINT handler: output
  `CONTROL_STARTED`, exit status `143`; the handler did not run.
- SIGINT to the same style of handler: output `CONTROL_STARTED`,
  `SIGINT_HANDLER_RAN`, exit status `0`.

The commands and captured output summaries are machine-readable in the JSON
record. These controls demonstrate generic signal semantics only; neither
executes mGBA, tests its cleanup, nor injects a save error.

## Qt build and CI status

The previous local Qt attempts reported two distinct failures: with
`BUILD_GL=OFF`, compilation reported `ShaderSelector` undeclared; with
`BUILD_GL=ON` after installing `libepoxy-dev`, linking reported unresolved
`ShaderSelector` Qt meta-object/vtable symbols. The logs and build tree are no
longer retained, so those local errors were not reproduced in this diagnostic.
On exact head `71592a77aa9da87bf09a06f056878ed18cb7b393`, push run
`42068329162` / job `127388846614` succeeded in 99 seconds, including the Qt6
install and native Qt checks. The corresponding PR run `42068342841` / job
`127388783297` was cancelled during “Install native Qt6 Core for SaveConverter
witness.” That step ran from `16:49:25Z` to `17:09:25Z`; the log shows slow
Azure Ubuntu package downloads (including a retry of `libavcodec62`) and then
“The operation was canceled.” The job ended at the configured 20-minute
timeout. This indicates package-mirror delay exhausted the job budget, not a
Qt compile error; the exact cancellation actor/reason is not exposed in the
available run metadata.

The permitted workflow retry API rejected the cancelled PR run with HTTP 409
because it only retries a run with a failure conclusion. As a bounded repair,
the existing job timeout is raised to 45 minutes. No dependencies, test
commands, or native Qt checks were removed or weakened; the new timeout is
asserted by the diagnostic test. The next exact-head PR and push runs are
needed to verify the repair.

## Provenance and remaining evidence

The five source identities and dossier-row hashes below are reused from the
already verified pinned feasibility matrix; this package does not count them as
new whole-file reviews:

- `src/platform/headless-main.c`
- `src/gba/core.c`
- `src/gba/gba.c`
- `src/core/core.c`
- `src/platform/qt/CoreController.cpp`

The verifier cross-checks those identities against the original mGBA pin
`fd9dc5c2cbf234365068855851107e762fc6211b`, source tree, and compressed dossier.
The files carry MPL-2.0 notices; preserve them and the repository license when
redistributing combined artifacts. No upstream source or pin was changed.

Still unproven: actual mGBA timeout exit/runtime, shutdown cleanup under SIGINT
or a valid shutdown SWI, file-backed save failure/reopen, real Qt frontend
build/runtime, logger delivery, persistence durability, stock gameplay, and
physical Flash. The prior logger controls are not rerun or relabeled here.
There is no approval or gate-state change.
