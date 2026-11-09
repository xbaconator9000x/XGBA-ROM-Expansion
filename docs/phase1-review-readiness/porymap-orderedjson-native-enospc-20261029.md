# Phase 1 — original Porymap OrderedJsonDoc native Qt write-error boundary

**Status: partial evidence only / FAIL_INCOMPLETE / 0 independent approvals.**

## Pinned dependency closure and maximum reuse

Pinned `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`:
`include/lib/orderedjson.h` blob `cb5139d37d955f2469ebd2eaaf089668b82884fe`,
`src/lib/orderedjson.cpp` blob `4d3a460c652541371a01132116e508db8c4c872c`,
`include/lib/orderedmap.h` blob `33fcfc50609722b10ae45eaa847be540c7c72d13`,
`src/project.cpp` blob `d43b0949303433111d4478ad76117c2b3445dd13`.

Original `OrderedJsonDoc::dump(QFile*)` uses `QTextStream` to write a JSON object and newline, returns `void`, and does not report stream/device errors. The five existing `Project` global JSON writers `saveMapLayouts`, `saveMapGroups`, `saveRegionMapSections`, `saveWildMonData`, and `saveHealLocations` call this shared serializer, close their QFile and return success without checking the result. Those five call sites are **source-confirmed**, not yet independently executed as original Project methods.

The new test compiles the **unchanged original serializer and implementation** against actual Qt6, writes a positive JSON file and then calls the same original serializer with `QFile("/dev/full")`. Syscall evidence is required to establish a genuine `write() = -1 ENOSPC`, with Qt error observed before and after close. The test does not instrument or execute any of the five Project functions, nor the actual GUI new-map path. The earlier original `saveMap` GUI and `saveTextFile/appendTextFile` tests remain separate green evidence.

## Reuse vs build and reviewer questions

Reuse `OrderedJsonDoc`, `QFile`, `QTextStream`, and (for a future patch) Qt `QSaveFile` with the smallest `QIODevice`-compatible adapter, error propagation and transactional commit checks. No new JSON serializer or editor is warranted. Verify all writer return values at `Project` → `Editor` → `MainWindow` and preserve source JSON key order. The original Porymap root license is LGPL-3.0; its embedded json11 notice is permissive and `orderedmap.h` carries an MIT notice. License obligations must be reviewed before any upstream patch or redistribution.

Reviewer must still verify real five-function write failures, GUI new-map collateral rollback, multi-file atomicity and independent whole-file semantics. Passing this test does not satisfy any complete-file gate.
