# Phase 1 — Porymap original Qt text writers under native ENOSPC (2026-10-29)

**Status: exact-head CI pending. Partial function evidence only. FAIL_INCOMPLETE; independent approvals 0/14,834.**

## Scope and immutable provenance

Pinned huderlem/porymap commit 26b919d7ff4b54152de010abd5bf344af2ebe116, src/project.cpp Git blob d43b0949303433111d4478ad76117c2b3445dd13. This experiment extracts the complete, unchanged original bodies of Project::saveTextFile and Project::appendTextFile from the pinned source at test execution time. It compiles them with the existing Qt6 Core API using minimal test-only Project declarations and a logError stub. It does not build MainWindow, invoke Project::saveMap or mutate upstream Porymap.

## Independent positive and failure controls

The native test requires normal save to write "alpha\n", normal append to produce "alpha\nbeta\n", and both functions to reject a nonexistent parent directory at QFile::open. It then calls each unchanged original function with 4,096 bytes directed to Linux /dev/full, requiring the original boolean return to be true. A separate Linux strace -f -yy trace must show a real write(fd</dev/full>,...) = -1 ENOSPC **between the appropriate test stage markers** for each original function, rather than merely assuming a device failure. The test fails closed if the native compiler, pinned blob, Qt execution, syscall attribution or positive controls disagree. Six source and eleven output-evidence mutations are rejected.

This is stronger than a source-only inference that QFile::write is unchecked: it executes the actual original function bodies with real Qt and kernel ENOSPC. It is narrower than the previous full pinned MainWindow GUI map.json false-clean test: these helpers are extracted into a test harness, and this experiment does **not** demonstrate an actual new-map save, event_scripts.s corruption, filesystem crash consistency or the private QFile::error value. A strace ENOSPC syscall is not a hardware persistence test.

## Maximum reuse and interoperability

Keep the existing Porymap Project, Editor and MainWindow implementations, Qt QFile/QSaveFile and Poryscript/FireRed build path. The smallest future repair should inspect the existing QFile::write byte count and error state, check required flush/close semantics, propagate failures from all three new-map collateral calls, and avoid clearing dirty state before all required writes succeed. Append-only event_scripts.s needs an explicit atomicity/rollback decision; do not replace it blindly with QSaveFile. This is a Phase 1 review recommendation, not a product patch.

Porymap root LICENSE.md at the pinned revision is LGPL-3.0; existing third-party components require their own notice and licensing review. No ROM assets or upstream source are redistributed by this evidence. Review the entire relevant source file and dependency closure independently before counting a semantic approval.

## Unresolved

- Real full Porymap GUI new-map creation under each collateral failure, including the resulting project dirty flags and disk bytes.
- Poryscript .pory-to-.inc generation and FireRed include dependency.
- Cross-file transaction and recovery semantics for map.json, scripts/text and event_scripts.s.
- Independent whole-file semantic review and all remaining Phase 1 gates.

**Do not advance Phase 2 or mark this source file approved.**
