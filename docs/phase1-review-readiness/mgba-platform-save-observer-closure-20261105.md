# Phase 1 mGBA platform save-error observer closure

This is a non-approving, source-only handoff for the eight previously identified
platform files. It closes the call path through the shared GUI runner and VFS
dispatcher; it does not repeat the prior POSIX-fd, stdio, or callback-native
execution packages. The machine-readable matrix pins every reviewed source and
canonical dossier row to mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`:

- `mgba-platform-save-observer-closure-20261105.json`
- 11 pinned source files: eight platform files, `gui-runner.c`/`.h`, and
  `src/util/vfs.c`; all have original Git blob IDs, full-byte SHA-256 values,
  dossier-row SHA-256 values, MPL-2.0 notices, and line anchors.
- `headless-main.c`, platform `main.c` files, the three relevant VFile/VDir
  files, and the shared dependencies are source-reviewed only within the
  observer/lifecycle scope stated per file. `windows/vfs-w32.c` is explicitly
  identity-only for this question: it implements a VDir wrapper and delegates
  file opening to `VFileOpen`; it is not a Windows VFile backend.

## Observer and status dispositions

| Path | Observer route | Status reaching the host |
| --- | --- | --- |
| Headless | Configures the standard logger; `logToStdout` defaults true in this entry point. | Calls core unload/deinit but does not convert save persistence into its exit result. Logger implementation/configuration and actual output are not runtime-verified here. |
| 3DS frontend | Uses the shared GUI runner and its configured log file. | Log requires a logger VFile and a `logLevel` accepting the message; GUI shutdown does not return persistence status. |
| 3DS VFile | Selected only if the compile-time `ENABLE_VFS_3DS` branch is active. | Buffered sync returns the FS result but does not check `sizeWritten`; no-buffer flush result, unmap write result, and close results are discarded. Close returns true. |
| PSP2 frontend | Uses the shared GUI runner and its configured log file. | Log is conditional as above; GUI shutdown does not return persistence status. |
| PSP2 VFile | Selected only if the compile-time `PSP2` branch is reached. | Buffered sync checks exact `pwrite` length and sync status. Unmap discards seek/write/sync results; close discards sync status and returns only close status. |
| Switch frontend | Uses the shared GUI runner. | Conditional log route; the selected VFile backend is unproven without target build definitions. |
| Wii frontend | Uses the shared GUI runner. | Conditional GUI log route; `puts` is compiled under `GEKKO` and remains conditional on logger VFile/level checks. This is not an on-screen notification. Backend selection is unproven. |
| Windows VDir wrapper | Not a frontend logging path. | Delegates file creation to `VFileOpen`; no Windows save VFile backend semantics are assigned to this file. |

The shared GUI logger drops messages if its VFile is absent or the configured
level excludes them. It tests writes for a negative result, not a positive short
write. After a negative write it closes and reopens the log but dereferences the
reopened VFile without checking for null; this is a source-level risk, not an
observed failure. A log message is neither an acknowledgment of persistence nor
proof that a user saw it.

The GUI runner calls optional autosave-state handling, core `unloadROM`, core
`deinit`, then emits its “Game stopped!” INFO log. `mGUIRun` returns void.
`gameLoaded`/`gameUnloaded` are lifecycle hooks, not `savedataUpdated`
persistence receipts. Consequently, a conditional sync-failure log may be the
only source-level observer on some routes; unmap/close failures discarded by
platform VFiles do not acquire a status channel from the runner.

`src/util/vfs.c` selects VFile implementations by compile-time preprocessor
order. This package did not verify target build definitions, so it does not
assert which backend Switch/Wii use or claim an observed console build.

## Evidence boundary and review handoff

All findings above are pinned-source deductions. No 3DS, PSP2, Switch, Wii, or
Windows native frontend was built or executed; no platform save failure was
injected. There is no observed frontend display, real save-file outcome,
physical Flash/power-loss evidence, or independent semantic approval. Reviewers
should verify target build configuration, real platform logger sinks and user
visibility, and platform-specific save behavior before making runtime claims.
The existing Phase 1 gate and approval counts are unchanged.

The workflow runs the fail-closed validator and mutation controls, then checks
the exact pinned source tree, dossier identity, license headers, and anchors.
This validates provenance and the source handoff only; it is not native
platform execution or semantic approval.
