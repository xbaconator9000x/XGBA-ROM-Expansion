# Pinned mGBA `mCoreAutoloadSave` ownership witness

Status: **NEEDS_EVIDENCE / FAIL_INCOMPLETE**; independent approvals: **0**.

This Phase 1 package covers a distinct pinned caller path on PR #13. It is not
the previously delivered `mCoreLoadSaveFile` allocation-failure witness. The
new caller, `mCoreAutoloadSave`, unconditionally passes the result of
`mDirectorySetOpenSuffix` to `core->loadSave`; unlike `mCoreLoadSaveFile`, it
does not return before the callback when that result is null. The machine
receipt verifies both caller-body hashes and the prior receipt without changing
that prior evidence.

## Pinned source and call path

The source is mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`, tree
`5863e657d270d0fe3ccaa4299f48d5689d74fa1f`, from the original MPL-2.0 files.
The pinned dossier archive SHA-256 is
`1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.
The receipt records the original Git blob, whole-source SHA-256, canonical
dossier-row SHA-256, license, and execution scope for every traced or compiled
file.

Pinned SDL `mSDLRun` loads the ROM and calls `mCoreAutoloadSave` without checking
its return. Pinned Qt `CoreManager::loadGame` checks the return and enters its
`saveFailed` handling on false. The witness does not execute either frontend.
The source path compiled/executed by the witness is:

`mCoreAutoloadSave` → `mDirectorySetOpenSuffix` → original POSIX `VDir` and
`_vdOpenFile` → original `VFileOpen` dispatcher → POSIX `VFileOpenFD` /
`VFileFromFD`.

The exact pinned `mCoreAutoloadSave` and `mDirectorySetOpenSuffix` function
bodies are extracted at run time after whole-file and body hash checks. The
original VDir, VFile dispatcher, and fd-backend translation units are compiled.
A host linker wrapper injects failure only for the `VFileFD` allocation after
the target save file has been opened. Positive controls cover successful open
and callback close, allocation failure followed by retry, and the original
missing-save-directory early return. The callback is a narrow fixture: it
counts a null handoff and returns false, and closes the retry VFile.

## Observation and limits

The source-grounded result is that this caller hands a null VFile to
`core->loadSave` when the POSIX backend's `VFileFromFD` allocation fails; the
backend path leaves the opened descriptor unclosed on that branch. In the
controlled harness, the fixture observes the null argument, the caller returns
false, retry succeeds, the retry descriptor is closed, and the first descriptor
remains open until explicit harness cleanup.

For GBA cores, the pinned callback assignment routes `_GBACoreLoadSave` to
`GBALoadSave`. That function deinitializes then initializes savedata with the
received VFile and returns the VFile pointer as a boolean; a null input
therefore returns false. `GBASavedataInit` stores the incoming pointer and may
close a prior `realVf`. These are source-traced lifecycle effects only: the
witness callback is a fixture and does not execute this GBA path.

This is compiled extracted-caller/original-backend host evidence, not a native
mGBA frontend execution. The failure is injected and was not naturally
observed. The actual GBA savedata callback is source-traced but not executed.
The descriptor check is same-process and ephemeral; it is not evidence of
durable persistence, user-visible save loss, `.sav` interoperability, stock
gameplay, or physical Flash behavior. SDL/Qt behavior, real `VFile` backend
variation, and downstream callback effects remain for independent review.
This receipt is not a semantic approval and does not change the Phase 1 gate.

## Reproduction

The existing PR #13 workflow fetches the exact upstream pin, checks Git tree,
blob, source/dossier identities and MPL notices, rejects seven source mutations
and seven contradictory-output mutations, then compiles and executes the
bounded witness. The machine receipt is
`mgba-core-autoload-save-ownership-20261107.json`.
