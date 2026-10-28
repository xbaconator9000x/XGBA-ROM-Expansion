# Phase 1 — pinned Porymap QSaveFile device compatibility and watcher boundary (2026-10-29)

**Status: CI pending; FAIL_INCOMPLETE; independently approved 0/14,834. Partial source contracts only.**

## Maximum-reuse decision

Reuse pinned Porymap's Project/Editor/MainWindow, OrderedJsonDoc and existing Qt QIODevice/QSaveFile/QTextStream/QFileSystemWatcher APIs. Do not replace the JSON serializer or editor. The previously verified Qt GUI `saveMap` false-clean failure and the five other source-level unchecked JSON writers are separate evidence. This packet asks the narrower question: **can existing OrderedJsonDoc::dump(QFile*) accept QSaveFile directly, and what existing Qt facilities already provide atomic replacement and watcher recovery?**

The pinned `include/lib/orderedjson.h` defines `JsonDoc::dump(QFile *file)`, constructs `QTextStream fileStream(file)`, emits JSON and newline, and does not inspect `QTextStream::status()`. A Qt `QSaveFile*` is convertible to `QIODevice*` but **not** to `QFile*`; a direct replacement of the local QFile variable therefore does not compile. A minimal future adapter would change/overload the serializer's device parameter to `QIODevice*`, preserve serialization and key order, inspect stream status, and call `QSaveFile::commit()` before reporting success or clearing dirty state. This is a proposal, **not a Phase 2 implementation**. Compatibility with other callers must be checked before modifying the signature.

The pinned `src/project.cpp` already uses `QFileSystemWatcher` and, in `recordFileChange`, re-adds a watch if an atomic replacement caused the original path to disappear from the watch list. That is a relevant existing recovery hook, not proof of correct event suppression or watcher behaviour after an actual QSaveFile commit. Its five-second `ignoreWatchedFileTemporarily` logic also requires a native integration test.

Two **additional source-only** unchecked text write functions, `Project::saveTextFile` and `Project::appendTextFile`, call `QFile::write(text.toUtf8())` then return true without checking write count, flush or close. These are distinct from the previously audited six JSON writers. Callers and actual failed-write consequences are not yet established. Append operations cannot automatically use atomic replace without assessing semantics.

## Immutable source, license and executable test

Pinned `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`:
- `include/lib/orderedjson.h` Git blob `cb5139d37d955f2469ebd2eaaf089668b82884fe`
- `src/project.cpp` Git blob `d43b0949303433111d4478ad76117c2b3445dd13`
- `LICENSE.md` Git blob `65c5ca88a67c30becee01c5a8816d964b03862f9`

The root license file contains the **GNU LGPL version 3** text; the bundled json11-derived header separately carries a permissive copyright/permission notice attributed to Dropbox (2013). These are source observations, not legal clearance to distribute game assets or a final conclusion about every component's license. Preserve all applicable notices; independently verify the scope of the root license and third-party dependencies.

The new CI compiles an actual Qt6 Core C++ test with the pinned serializer header. Compile-time assertions require the exact existing `dump(QFile*)` type, `QSaveFile* !-> QFile*` and `QSaveFile* -> QIODevice*`. Native Qt exercises a successful QSaveFile replacement, cancelled write preserving prior bytes, and a separate matched `QFile` /dev/full error control. These are **Qt API tests, not execution of any of the six Porymap Project writers**. The Python checker pins all three upstream blobs, checks the existing watcher and two text writers, rejects nine source mutations and ten evidence mutations, and retains FAIL_INCOMPLETE.

## Open boundaries and reviewer questions

1. Run actual pinned Porymap Project global writer failures through Qt, disk snapshots, and error propagation; do not infer them from this Qt API test.
2. Verify the `OrderedJsonDoc` QIODevice adapter against all callers, preserving output bytes and key order.
3. Test QSaveFile failed write/commit, symlink targets, watcher suppression/re-registration, and the editor dirty flag in the actual GUI. Do not assume `/dev/full` symlink injection retains its meaning under atomic replacement.
4. Trace all callers of `saveTextFile` and `appendTextFile`, including whether an append must remain non-atomic.
5. Independently review complete source identities and licensing before any approval or distribution.

**Gate: FAIL_INCOMPLETE; independently approved 0/14,834. No upstream patches, Phase 2 changes or whole-file semantic approvals.**
