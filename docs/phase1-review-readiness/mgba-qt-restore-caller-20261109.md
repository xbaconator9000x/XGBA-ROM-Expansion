# Pinned mGBA Qt restore caller witness

This Phase 1 witness executes extracted, hash-checked bodies from pinned mGBA
`fd9dc5c2cbf234365068855851107e762fc6211b` using native Qt6Core/QIODevice.
It covers the Qt `CoreController::loadState` QIODevice and filename overloads,
backup recovery, `VFileDevice` opening/wrapping, wrapper cleanup, rejected
state, open failure, and retry. The machine receipt records the exact source
Git blobs, full-file SHA-256 values, canonical dossier-row hashes, pinned tree,
compressed dossier identity, and extracted-body hashes.

The harness uses host fixtures for the core, core-thread dispatch, backup
memory VFile, and `VFileOpen` (a Qt QBuffer fixture). It is not a full Qt
frontend, Qt Widgets/Window or SDL execution, native filesystem access,
natural malformed-state incidence, durable savestate or savedata, stock
gameplay, or physical Flash evidence. SDL behavior and the remaining Qt UI/log
routes are source-traced only. The prior full-frontend feasibility receipt
records build blockers. MPL-2.0 headers are verified for the listed source
files; transitive distribution licensing remains unresolved.

The receipt is deliberately `NEEDS_EVIDENCE` / `FAIL_INCOMPLETE`, with zero
independent approvals. This is a bounded caller/wrapper witness, not a
whole-file semantic review or approval.

Run in the repository root with the pinned mGBA checkout and Qt6Core installed:

```sh
python3 -m unittest discover -s tests -p 'test_phase1_mgba_qt_restore_caller.py' -v
python3 tools/phase1_mgba_qt_restore_caller.py \
  --checkout /path/to/mgba-fd9dc5c
```
