# Phase 1 — five unchanged Porymap global JSON Project writers under native Qt

Status: **PENDING EXACT-HEAD CI / FAIL_INCOMPLETE / 0 independent approvals**.

## Dependency closure

Pinned Porymap \`huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116\`: \`src/project.cpp\` Git blob \`d43b0949303433111d4478ad76117c2b3445dd13\`; \`include/lib/orderedjson.h\` \`cb5139d37d955f2469ebd2eaaf089668b82884fe\`; \`src/lib/orderedjson.cpp\` \`4d3a460c652541371a01132116e508db8c4c872c\`; \`include/lib/orderedmap.h\` \`33fcfc50609722b10ae45eaa847be540c7c72d13\`.

The five global JSON methods \`saveMapLayouts\`, \`saveMapGroups\`, \`saveRegionMapSections\`, \`saveWildMonData\`, and \`saveHealLocations\` all call the existing \`OrderedJsonDoc::dump(QFile*)\` and close their QFile without checking post-write status. Prior evidence executed only the shared serializer and the separate text writers, not these five Project method bodies.

## Test and scope

The new harness extracts and compiles the **verbatim original five method bodies** with the original OrderedJson implementation and Qt6. Minimal test-only Project data types, empty input collections and a project-config filepath adapter allow a positive JSON write/readback and a controlled \`/dev/full\` failed write per method. A syscall trace must prove an actual Linux \`write = -1 ENOSPC\` for each method. The verifier rejects five source and ten transcript mutations. It must not infer full GUI, real Project constructor, nonempty editor state, atomic multi-file transactions, physical Flash, or independent whole-file review.

## Reuse and license decision

Keep Qt QFile/QSaveFile, original OrderedJsonDoc and Project/Editor/MainWindow interfaces; smallest compatible future patch is a QIODevice-compatible serializer entry point, per-file write/flush/commit checks and propagated bool failures, followed by editor lifecycle testing. No new JSON serializer. Porymap root LGPL-3.0; embedded json11 and OrderedMap permissive notices require license-preserving reuse. Upstream remains unchanged.

## Reviewer questions

Confirm nonempty collection edge cases, file-watcher ignore duration on failed saves, multi-file partial writes, GUI new-map rollback and whether every original caller propagates a failed return. This is partial-function evidence, not complete-file disposition. Gate remains FAIL_INCOMPLETE.


## Executed checkpoint (2026-10-29)

At draft-branch commit \`e7e6414616f57a3000a31b8ec60bc07da5d6b117\`, original-function Qt6 compilation and execution **passed** in exact-head push CI [#40781519051](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40781519051), job \`123144103843\`, and exact-head PR CI [#40781528956](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40781528956). Push artifact \`12857522152\` digest \`sha256:70daca293c224d8da3c1533041e1dbc09196c7be430fd910d3a6b2cd9cb68349\`.

Five original Project method bodies compiled unchanged with the pinned OrderedJson implementation. Each wrote a syntactically valid JSON file with its expected top-level key in the positive case. Each returned **true** after two real Linux \`write(/dev/full) = -1 ENOSPC\` syscalls in the controlled failed-write case. Five source and ten syscall/transcript mutations were rejected. This upgrades the five previously source-only suspected false-clean returns to **native Qt evidence for the original function bodies under test-only empty project data**. It does not establish a full Porymap GUI/new-map path or populated-project behaviour.

### Partial per-file reviewer records — not approvals

| Pinned file and blob | Examined scope | Untraced / reviewer obligations |
| --- | --- | --- |
| \`src/project.cpp\` \`d43b0949303433111d4478ad76117c2b3445dd13\` | Five verbatim global JSON writer functions, initial open guards, serializer calls, returns, positive and ENOSPC | Other functions, populated project state, file watcher effects, real GUI/new-map lifecycle, caller error propagation |
| \`include/lib/orderedjson.h\` \`cb5139d37d955f2469ebd2eaaf089668b82884fe\` | \`OrderedJsonDoc::dump(QFile*)\` interface and stream writes | Entire-header semantics, Qt versions beyond tested Qt6, QIODevice adapter review |
| \`src/lib/orderedjson.cpp\` \`4d3a460c652541371a01132116e508db8c4c872c\` | Original implementation linked into native executable | Full parser, conversion and ordering edge cases |
| \`include/lib/orderedmap.h\` \`33fcfc50609722b10ae45eaa847be540c7c72d13\` | Original container implementation linked into native executable | Whole-file ordering/invalidation/lifetime review |

These are **partial-file scopes only**. No complete-file candidate or independent semantic approval is added. The expected-SHA follow-up evidence-checker change must pass its own exact-head CI before its new evidence mutation count can be asserted.
