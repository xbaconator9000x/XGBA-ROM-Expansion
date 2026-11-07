# Phase 1 — Porymap private map QFile error state (2026-10-28)

**PENDING EXACT-HEAD CI; FAIL_INCOMPLETE; independent approvals 0.**

Pinned Porymap `26b919d7ff4b54152de010abd5bf344af2ebe116`, original `src/project.cpp` Git blob `d43b0949303433111d4478ad76117c2b3445dd13`. Prior **unmodified** full Qt GUI + strace evidence at PR #27 `ef61375b` CI #40651820267 verified actual post-QAction `/dev/full` `ENOSPC` kernel writes, but did not inspect the private `QFile::error()` state.

This **new and explicitly test-only instrumented binary** verifies the pristine source blob, then adds a single `std::fprintf`/flush immediately after `OrderedJsonDoc::dump(&mapFile)` and before `mapFile.close()`, filtered to PalletTown map.json. It does not alter the save return path, write call, map dirty-state logic or upstream repository. The actual full pinned MainWindow/Editor QAction harness is rebuilt with this logging-only insertion. Its stderr is archived and a separate verifier requires the successful single-map positive Save's private QFile status to be zero and the two real `/dev/full` GUI Save actions' statuses to be nonzero, with six fail-closed trace mutations. The prior strace verifier remains independently active.

**Interpretation limits:** The measured private handle belongs to the *logging-instrumented* build, not a byte-identical original executable; instrumenting before `close()` cannot establish its later close error state. If the status is unexpectedly zero, fail closed and inspect QTextStream buffering and QFileDevice::error rather than claiming private failure attribution. No code fix is applied to upstream Porymap; the false-clean save defect remains. No complete-file semantic approval, cross-platform behaviour, editor expansion interoperability or Phase 2 certification follows.

Independent reviewer questions: Does QTextStream propagate ENOSPC to QFileDevice::error before close? Would checking `QTextStream::status()` plus `QFile::flush()` and close results be required for a correct upstream repair? Are other Project JSON/text writers similarly vulnerable? What happens when the output device fails only on close?
