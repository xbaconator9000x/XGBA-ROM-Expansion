# Phase 1 — pinned mGBA core POSIX savedata teardown ownership

**Disposition:** partial, non-approving evidence. The receipt remains
`NEEDS_EVIDENCE` / `FAIL_INCOMPLETE`, with zero independent approvals. No
upstream source, shared gate, approval count, or runtime behavior was changed.

## Distinct boundary

The PR13 FD teardown matrix already executed the pinned POSIX backend,
`GBASavedataDeinit`, and `GBAUnloadROM`, including injected `msync`, `munmap`,
and `close` failures. It source-audited but did not execute `GBADestroy` or
`_GBACoreDeinit`. PR35's
`semantic-snapshots/independent-reviews/copilot-mgba-savedata/fd-stdio-error-propagation-handoff.json`
reconciles the same prior FD/stdio cases and their limits; it does not execute
this complete destruction callback path. PR35's rewind map-failure witness is a
different caller and is not reused as teardown evidence.

This package compiles and executes the exact pinned extracted bodies along the
missing owner chain:

`core->deinit = _GBACoreDeinit` -> `_GBACoreDeinit` -> `GBADestroy` ->
`GBAUnloadROM` -> `GBASavedataDeinit` / POSIX VFile unmap and close.

The original POSIX `vfs-fd.c` translation unit is compiled unchanged. The two
newly executed production bodies are `_GBACoreDeinit` and `GBADestroy`; the
other original function bodies and source identities are reused from the prior
teardown receipt and explicitly remain partial-file evidence.

## Observed bounded behavior

The normal case completed the original teardown with one sync, unmap, and close;
the board and core were freed and the descriptor was closed.

The fault case injects `EIO` into `msync(MS_SYNC)` and into close **before**
calling the real close syscall. The original deinit chain continued, cleared
savedata references, freed the board and core, and returned no result channel.
`GBAUnloadROM` discarded the close result; with the fixture's injected backend
behavior, the VFile wrapper and descriptor remained live after the production
owner was gone. Only the harness retained an external pointer and closed it for
safe cleanup. That is not a production retry or recovery path and does not
establish real OS close-error descriptor semantics.

Three source mutations and ten contradictory-output controls are rejected by
the runner. Reproduce against the exact upstream checkout with:

```sh
python3 tools/phase1_mgba_core_teardown_ownership.py \
  --checkout /path/to/mgba-fd9dc5c2cbf234365068855851107e762fc6211b
python3 -m unittest discover -s tests \
  -p 'test_phase1_mgba_core_teardown_ownership.py' -v
```

The JSON receipt binds each selected original file to the pinned Git blob,
complete-byte SHA-256, canonical dossier-row SHA-256, and MPL-2.0 notice. No
original source is copied into the repository. This is not a legal conclusion
for combined distribution.

## Limits

This is extracted original code with host stubs for unrelated GBA subsystem
deinitializers, manually initialized savedata fields, and a linker-injected
syscall failure. The complete GBA/core translation units, frontend dispatch,
native user workflow, natural OS failure incidence, durable `.sav` persistence,
stock gameplay, and physical Flash are not tested. Page-cache visibility is
not durability. No independent semantic approval or gate promotion is claimed.
The fixture starts with `savedata.vf == savedata.realVf`, so the original
unmask body takes its early return; fixture-only load/type stubs for the
unexercised masked branch are not evidence about that branch.
