# Pinned mGBA host log-observer witnesses

This Phase 1 package links the previously tested failed `VFile.sync` result and
the exact INFO message to two compiled pinned log-consumer implementations:
`_mCoreStandardLog()` and the shared GUI runner's `_log()`. It is additive to,
not a replacement for, the earlier callback and platform-observer evidence.
It does not repeat the prior VFile backend or logger callback inventories.

## Provenance and scope

The source pin is mGBA
`fd9dc5c2cbf234365068855851107e762fc6211b`. The machine-readable matrix lists
the four exact source records, Git blob IDs, full-byte SHA-256 values, canonical
dossier-row hashes, and the compressed dossier identity. The runner verifies
the checkout commit and source tree entries, complete source bytes, MPL-2.0
notices, and each canonical dossier row before extraction. It compiles the
unchanged extracted bodies of `GBASavedataClean`, `mSavedataClean`, mGBA's
logger dispatch functions, `_mCoreStandardLog`, and GUI `_log`.

The harness supplies the narrow surrounding ABI (structures, category and
filter stubs, configuration-directory and reopen adapters, and a mock VFile).
Its fan-out logger is test-only: it invokes both original sink bodies using
copies of the original `va_list`. The mock savedata `sync` deterministically
returns false. This establishes host execution of the pinned function bodies
and controlled sink behavior; it is not a full mGBA core, headless process, Qt
application, console frontend, or native GUI runtime.

The compiled observations assert the failure message reaches standard logger
stdout and a mock log VFile, and the GUI logger file sink when INFO is enabled.
Additional controls verify GUI INFO filtering, a missing sink, recovery after
a negative write through the source's reopen path, and the source's lack of
retry after a positive short write. The positive short-write result is only a
controlled mock-host observation.

## Evidence limits and unresolved objections

- **Source/compiled-host:** The exact pinned function bodies are compiled and
  run on Linux with injected host adapters. This validates only the exercised
  bodies and stubs.
- **Frontend runtime:** No frontend UI, Qt/SDL/libretro/Python logger
  installation, or end-to-end headless executable was run. The matrix marks
  frontend delivery unobserved.
- **Save and durability:** The failed sync is synthetic. No real backend,
  `.sav` restart/interoperability, process-crash or power-loss durability,
  stock gameplay, or physical Flash result is established.
- **Approval:** This is not a per-file independent semantic receipt and makes
  no approval or gate claim. Historical independent approvals remain
  unchanged.

The source excerpts carry their original MPL-2.0 notices in provenance. The
test harness is a combined distribution with that licensing caveat; it does
not modify or claim endorsement by upstream mGBA.
