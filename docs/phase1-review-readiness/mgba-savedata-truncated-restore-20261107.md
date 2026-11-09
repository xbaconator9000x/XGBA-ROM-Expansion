# Phase 1 — truncated savedata restore return path

**Disposition:** compiled, source-extracted host witness only. This is
non-approving Phase 1 evidence; independent approvals remain `0`, status remains
`NEEDS_EVIDENCE`, and the gate remains `FAIL_INCOMPLETE`.

## Non-overlap inventory

At PR #13 HEAD `0663d065da81e9d43d94a9e3c15215e3221f3b5e`, the existing
workpapers and fixtures already cover:

| Existing witness | Covered behavior |
|---|---|
| Headless runtime sync | Real pinned headless caller with successful `MS_ASYNC`, injected `MS_ASYNC` `EIO`, logging, teardown, and a same-host cold-process reopen. |
| Final teardown sync | Injected final `MS_SYNC` failure, teardown return/log behavior, and a same-host child read. |
| Existing-save reopen | Targeted `open(...)=EIO` through script-facing `loadSaveFile`, failure return, and an uninjected recovery reopen. |
| POSIX restore write | `_GBACoreSavedataRestore(writeback=true)` with a mapped destination absent: full write, positive short write/no retry, and negative write/`EIO`. |
| Mask/unmask short read | A short mapped input read where `GBASavedataUnmask` ignores the false `GBASavedataLoad` result. |

This package does not repeat those faults. It exercises the distinct
`savedata->data != NULL` branch of `GBASavedataLoad` through the original
`_GBACoreSavedataRestore(writeback=true)` caller, so the caller's `false`
result is observed. In contrast, the earlier masked short-read case reached
`GBASavedataLoad` through `GBASavedataUnmask`, whose pinned caller ignores the
result.

## Source closure and licensing

All six source/header identities, full-byte SHA-256 values, dossier row hashes,
license notices, call roles, and per-file substantive objections are recorded
in [`mgba-savedata-truncated-restore-20261107.json`](mgba-savedata-truncated-restore-20261107.json).
The immutable upstream pin is mGBA
`fd9dc5c2cbf234365068855851107e762fc6211b`, tree
`5863e657d270d0fe3ccaa4299f48d5689d74fa1f`. The original compressed dossier is
Git blob `3b982876c7d810a827af8c80c7e5d9231fdaa327`, SHA-256
`1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.

The dependency path is:

`_GBACoreSavedataRestore(writeback=true)` →
`VFileMemChunk(sram, size)` →
`GBASavedataLoad` →
`GBASavedataSize` →
`VFileMemChunk.read` and mapped POSIX savedata destination.

The verifier checks the existing pinned source and dossier identities and
extracts the original caller and savedata function bodies into a temporary
build file. The complete pinned `vfs-fd.c` and `vfs-mem.c` translation units
are compiled. The full mGBA core translation unit is not compiled. The sources
and headers carry MPL-2.0 notices; no upstream file is modified or copied into
the repository.

## Compiled-host observations

The fixture initializes a 4096-byte mapped POSIX save to `0xB6` and supplies a
32-byte snapshot:

| Case | Caller return | Observed state |
|---|---:|---|
| Truncated snapshot | `false` | The 32-byte prefix was copied before the exact-size read failed; bytes after the prefix remained `0xB6`. |
| Full-size recovery retry | `true` | A subsequent 4096-byte restore matched the complete input. |

The short input is fixture-supplied. No host syscall failure is injected in
this case, and no frontend, headless process, naturally truncated state file,
or real savestate consumer is observed. The partial in-memory update is not
durable-persistence evidence. The recovery retry establishes only behavior of
these compiled pinned bodies and host VFiles under this controlled fixture.
No `.sav` interoperability, stock gameplay, power-loss, or physical Flash
claim is made.

The deterministic verifier rejects eight source mutations and eighteen
contradictory or malformed output mutations, including a fabricated successful
short restore, an altered partial-prefix result, failed recovery, false source
identity, and a stale source receipt.
