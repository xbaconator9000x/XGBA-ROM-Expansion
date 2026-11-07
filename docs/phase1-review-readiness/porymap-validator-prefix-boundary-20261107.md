# Phase 1 — pinned Porymap prefix and identifier validator boundary

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This package is a bounded native Qt observation and non-approving handoff. It does not modify pinned Porymap.

## Distinct source scope and provenance

The focal whole-file scope is `include/core/validator.h` and `src/core/validator.cpp` at pinned Porymap `26b919d7ff4b54152de010abd5bf344af2ebe116`. It is separate from the prior AdvanceMap parser, OrderedJson, and Tileset-persistence work.

The workpack ZIP SHA-256 is `5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4`; its compressed `evidence/candidate_review_dossiers.jsonl.gz` member SHA-256 is `fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac`. Those are candidate-inventory artifacts, not original semantic dossiers or approval receipts. The verifier pins each candidate row hash, original Git blob ID, and full-byte source SHA-256. It finds no original independent semantic dossier or attributable reviewer receipt; no file is marked reviewed or approved. Caller, build, and license entries in the machine handoff are context only.

Pinned `porymap.pro` compiles the validator implementation and declares Qt Core/GUI. The pinned root `LICENSE.md` contains LGPL text; this fact is not a distribution-compliance determination.

## Source-grounded behavior and caller closure

- `IdentifierValidator` uses `[A-Za-z_]+[\\w]*` and an optional empty-string variant.
- `PrefixValidator::validate` delegates to `QRegularExpressionValidator`, marks input `Intermediate` when adding the required prefix could make it valid, and `fixup` prepends a missing prefix.
- Pinned UI call sites use the common validators for define/map-group/layout/map/tileset identifiers, a configured prefix for new map-section and tileset symbols, and `setAllowEmpty(true)` for metatile labels. `ColorInputWidget` uses `UppercaseValidator`. The verifier scans all pinned C++ headers/sources under `src/` and `include/` for these class names and requires the complete reference set to match the inventoried callers. These call sites are pinned as context, not complete-file reviews.
- `include/core/validator.h` declares `PrefixValidator::setPrefix`, but a scan of pinned `src/` and `include/` finds no matching definition or call site in the validator-reference files. The native link probe that calls it fails with that unresolved symbol. This is a source/build boundary observation; no upstream fix is proposed here.

## Native Qt evidence and limits

The existing compiled-Porymap workflow builds the unchanged pinned `validator.cpp` with Qt 6 Core/Gui plus Qt `moc` output. The harness directly tests identifier accept/reject states, empty-input policy, required-prefix states, `fixup`, `isValid`, and uppercasing. It does not simulate QLineEdit events or run the UI dialogs.

The separate link probe intentionally references the declared `setPrefix` method and must fail to link specifically on `PrefixValidator::setPrefix`. The normal application build and validator controls must still pass. Source mutations and evidence-field mutations are rejected by the verifier.

These are bounded source/compiled Qt observations only. They do not prove every Qt version’s editing interaction, GUI usability, downstream project identifier uniqueness semantics, or distribution compliance. All per-file machine records preserve `NEEDS_EVIDENCE` and null independent receipts.
