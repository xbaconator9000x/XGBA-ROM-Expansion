# Phase 1 mGBA save-fault-to-observer handoff

This bounded addendum extends the existing pinned callback and observer
workpapers; it adds no frontend source inventory and does not repeat the prior
POSIX/stdio teardown or callback scenarios. Its only new execution observation
is whether the original pinned `GBASavedataClean()` warning traverses original
`mLog()` dispatch under the existing controlled Linux fd-backend sync failure.

## Result and evidence classification

The callback witness already executes the original GBA savedata-clean and
frame-ended bodies with `msync(MS_ASYNC)` returning injected `EIO`. It observed
dirty-to-clean notification despite failed sync; this is a save-data-change
event, not a persistence acknowledgment. The fixture previously compiled
`mLOG` away, so it did not establish the warning-message dispatch.

The expanded host fixture additionally compiles the original pinned
`src/core/log.c` bodies `mLogGetThreadLogger`, `mLogGetContext`,
`mLogSetDefaultLogger`, and `mLog`, and captures the warning through a test
logger callback. It observed one `mLOG_INFO` message with exact text
`Savedata failed to sync!` on the injected failure; the successful-sync control
separately emitted one `Savedata synced` INFO message. The native output also
records that no persistence acknowledgment was returned. This is a compiled
Linux source-extraction witness with controlled test-backend `EIO`; it does not
execute any actual frontend logger or prove persistence outcome.

The original savedata call site, complete fd VFile translation unit, and core
logger are pinned in the JSON with Git blob, full-byte SHA-256, canonical
dossier-row SHA-256, MPL-2.0 notice, and role. Exact extracted function hashes
cover `GBASavedataClean()` and the four core logger context/dispatch functions.
The host run used individually retrieved original files with exact blob and
byte checks; whole-checkout tree identity is reserved for checkout-mode
workflow verification.

The machine-readable per-path dispositions are restricted to
`RESOLVED_SOURCE_ONLY` or `NEEDS_EVIDENCE`:

- The callback meaning, source-level shutdown/teardown return contracts, and
  native-host core logger dispatch are resolved only within their pinned source
  and harness scopes.
- Qt, SDL, libretro, Python, and headless consumer visibility remain
  `NEEDS_EVIDENCE`. Source review identifies filters and conditional sinks:
  Qt INFO routing is not its ERROR-dialog condition; SDL defaults to excluding
  INFO; libretro forwarding requires an optional host log interface; Python
  logging depends on installation and can be silenced; headless configures the
  standard logger with stdout defaulting true. No frontend or headless process
  was executed here.
- Flush/unmap/close status and shutdown return behavior reuse prior pinned
  source and host-teardown evidence, not new fault cases.

The JSON matrix points to the exact original pins and existing evidence
workpapers. Its fail-closed controls reject stale source revision, wrong
backend, a sync-failure success claim, missing/unobserved frontend delivery,
fabricated persistence acknowledgment, warning-log level/message mutation, and
frontend/physical/stock-game claims.

## Remaining evidence

Actual Qt/SDL/libretro/Python/headless log delivery and user-visible behavior
remain unobserved. The host test logger is not any of these consumers. The
injected async-sync error does not establish whether bytes reached storage;
there is no real save-file, restart, gameplay, physical Flash, or power-loss
claim. No independent semantic approval or gate change is made.

Local validation compiled and ran the host witness successfully with GCC
13.3.0. It observed one failed async sync, one exact failure INFO log, one
success-control INFO log, one failed-sync callback, no retry without a new
write, and no persistence acknowledgment. The native executable SHA-256 was
`495a8184ab1d58ca6f2ace4f938cfd7a67428611b42226f3b4babdab3cf85ce5`.
The machine-matrix controls and callback parser controls also passed locally.
Exact-head Actions evidence for this addendum is recorded after its run
completes; local execution is not CI evidence.
