# Pinned mGBA SDL restore-caller witness

This Phase 1 witness executes the hash-checked original `_loadState` callback
and complete `mSDLRun` function body from pinned mGBA
`fd9dc5c2cbf234365068855851107e762fc6211b`. It checks the optional state-file
open path, core-thread dispatch, callback result handling, global `_state`
reset, VFile close, and continuation to the runloop. The test compiles against
the pinned serializer and VFile headers and source-checks the upstream tree,
source blobs, full-file SHA-256 values, dossier row hashes, compressed dossier
identity, and extracted function hashes.

On an injected loader failure, the original SDL callback discards the
`mCoreLoadStateNamed` false result; the tested `mSDLRun` continues to the
runloop and returns its normal success value under the host thread/audio
fixtures. On either loader result, it clears `_state` and closes the opened
VFile. Open failure skips callback and close, then still reaches the runloop.
The retry control is two separate `mSDLRun` invocations, first with a failed
load fixture and then with a successful one; it does not claim that SDL retries
automatically.

The core loader, VFileOpen/close implementation, thread dispatch, audio and
runloop are host fixtures. This is not a full SDL frontend or native user-file
execution, natural malformed-state evidence, durable savestate/savedata,
gameplay, physical Flash, or a semantic approval. The pinned core restore
closure, libretro caller, Qt caller and PR #35 rewind/VFile witnesses are
referenced for overlap accounting, not repeated. The serializer and VFile
header identities are reused dependencies and are not counted as new reviews.
MPL-2.0 notices are verified for the listed pinned sources; transitive
distribution licensing remains unresolved.

The receipt remains `NEEDS_EVIDENCE` / `FAIL_INCOMPLETE`, with zero independent
approvals. Four source-body mutations and six contradictory-output mutations
are rejected by the fail-closed runner.

Run in the repository root with the exact pinned mGBA checkout:

```sh
python3 -m unittest discover -s tests -p 'test_phase1_mgba_sdl_restore_caller.py' -v
python3 tools/phase1_mgba_sdl_restore_caller.py \
  --checkout /path/to/mgba-fd9dc5c
```
