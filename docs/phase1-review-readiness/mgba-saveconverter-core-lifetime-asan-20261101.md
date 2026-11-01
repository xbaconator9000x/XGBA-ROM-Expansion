# Pinned SaveConverter core-lifetime sanitizer witness (non-approving)

**Status:** source hazard observed in a bounded host sanitizer witness;
`NEEDS_REVIEW` / `NEEDS_EVIDENCE`; no semantic approval.

## Provenance and exact extraction

- mGBA commit: `fd9dc5c2cbf234365068855851107e762fc6211b`.
- Source: `src/platform/qt/SaveConverter.cpp`, Git blob
  `4c32280c9c5288e806ffd237119186e2a633c4a7`, SHA-256
  `3a6498a4fa69064d9b3723b49398cfe9d8e827ada3d8be26215db3a5ead2184f`.
- Extracted original `SaveConverter::getStatePlatform(VFile*)` byte range
  `[10913, 11841)`; extracted body SHA-256
  `9b7ebec69806b91569e19422c4269b20d24d6ff2691333d783a1f17c2e00d83b`.
- Test fixture:
  `tests/phase1_mgba_saveconverter_core_lifetime.cpp`, SHA-256
  `463199eca75b06c3adc276379874cf6939a08827f7bf11c74ae88f040b02db0b`.

The runner checks pinned commit, source tree/worktree Git blob, whole-source
SHA-256, function byte range and function SHA-256 before inserting the exact
extracted body into the C++ fixture. Only external types/functions and the
`SaveConverter` class shell are test doubles. Both `M_CORE_GBA` and `M_CORE_GB`
branches are compiled from the pinned function body. Mock `deinit` calls
`free(core)`; mock extraction returns separately allocated state on the
selected branch. The sanitizer therefore observes the original body reading
the freed mock core’s `stateSize` function pointer, not a separately
reimplemented sequence.

## Command and observed result

On the local runner, using GCC 13.3.0:

```sh
python3 -m py_compile tools/phase1_mgba_saveconverter_core_lifetime.py
python3 tools/phase1_mgba_saveconverter_core_lifetime.py \
  --checkout /tmp/xgba-mgba-core-lifetime \
  --harness tests/phase1_mgba_saveconverter_core_lifetime.cpp \
  --output /tmp/core-lifetime-evidence.json
```

Compiler options were
`-std=c++17 -O1 -g -Wall -Wextra -Werror
-fsanitize=address,undefined -fno-omit-frame-pointer
-fno-sanitize-recover=all`. Each potentially failing case runs as its own
subprocess with `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1:abort_on_error=0`
and `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1`.

| Case | Expected/executed outcome |
|---|---|
| GBA selected; extraction returns non-null | Child exits 1 with `AddressSanitizer: heap-use-after-free`, `READ of size 8`; diagnostic stack names the extracted `QGBA::SaveConverter::getStatePlatform` frame and `mock_deinit` free callback |
| GBA extraction null; GB selected extraction non-null | Child exits 1 with the same heap-use-after-free diagnostic, function frame, and freeing callback |
| Both core extractions return null | Child exits 0 and reports platform `mPLATFORM_NONE` (`0`) |

Three source mutations (cache size before deinit, replace the original
state-size call, remove deinit) were rejected. Nine evidence-field mutations
were also rejected by the runner’s fail-closed validator. The expected
non-null-case sanitizer exits are treated as positive observations; they are
not workflow failures unless the diagnostic or stack expectation is absent.
The null path is the non-crashing control. UBSan was enabled; no UBSan report
was observed in these cases.

The observed source ordering is at pinned
`SaveConverter.cpp:325–337` and `340–352`: each branch calls
`core->deinit(core)` before, on non-null state, calling
`core->stateSize(core)` as the size argument to `mappedMemoryFree`. Pinned
GBA/GB core deinitializers free their core objects at `src/gba/core.c:329` and
`src/gb/core.c:181`, respectively. This host test establishes the lifetime
violation in the exact function body when deinit frees the supplied core. It
does not run the real mGBA core or establish a real application crash.

## Evidence boundary

This is a native host C++ ASan/UBSan execution of the exact extracted function
body against controlled mock `mCore` and `VFile` functions. It is not a full
mGBA Qt application build, real mGBA core execution, real save-state
interoperability, stock gameplay, `.sav` restart test, or physical Flash
evidence. The pinned upstream source was not modified. The test only observes
the first invalid access after mock core deinit; no claim is made about
subsequent behavior without a sanitizer.

The witness author is still the same `@copilot` identity that produced the
earlier PR #13 witnesses. This is not an independent semantic review, must not
be marked `COPILOT_REVIEWED`/`PASSED`, and does not change legacy approval
counts or the `FAIL_INCOMPLETE` gate. The source-level MPL-2.0 notice remains
file-scoped; no combined-distribution licensing conclusion is made.

## CI status

The local positive and adversarial controls passed twice before commit. On the
new head `5ecf0ac60b5854c3d027e7f070517bd3fa40e0ce`, exact-head Actions run
[#41322742866](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41322742866)
completed with conclusion `action_required`. The Actions API reports **zero
jobs**, so no step log exists and the new witness has not executed in GitHub
Actions. This is a permission blocker, not a green CI result; no permission
check was bypassed. The previous successful run #41260407534 predates this
change and does not validate this new test.

CodeQL on the committed code/workflow change reported zero alerts for Actions,
Python, and C++. No source pin, approval count, or shared gate was changed.
