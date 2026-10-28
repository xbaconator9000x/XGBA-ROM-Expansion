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
