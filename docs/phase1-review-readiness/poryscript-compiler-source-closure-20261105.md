# Phase 1 — pinned Poryscript compiler source closure

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This package inventories a new, non-overlapping set of compiler implementation files at the pinned Poryscript revision. It does not repeat the existing Porymap writer, generated-include execution, mapjson whole-file candidate, map-connection, ABI, or transaction experiments.

## Scope and pinned source closure

The new source inventory is limited to nine production Go files in `huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55`. Each is identified by the upstream Git blob, byte length, line count, and full-byte SHA-256 in the machine-readable CI evidence. The checker derives the expected blob from the pinned commit tree and rejects a different worktree blob. Three Poryscript build/configuration inputs and seven Porymap/FireRed bridge sources are recorded separately as reused context, for twenty identified source/dependency files total.

| Pinned source | Role in compiler path | Disposition |
|---|---|---|
| `main.go` | CLI input/configuration, parser/emitter orchestration, output | `NEEDS_EVIDENCE` |
| `lexer/lexer.go` | Source tokens and source positions | `NEEDS_EVIDENCE` |
| `parser/parser.go` | Poryscript syntax and AST construction | `NEEDS_EVIDENCE` |
| `parser/parse_error.go` | Parser error/source ranges | `NEEDS_EVIDENCE` |
| `parser/formattext.go` | Text substitutions, formatting, and width diagnostics | `NEEDS_EVIDENCE` |
| `ast/ast.go` | Program, map-script, and statement representations | `NEEDS_EVIDENCE` |
| `token/token.go` | Token definitions and keyword mapping | `NEEDS_EVIDENCE` |
| `emitter/emitter.go` | AST-to-assembly generation and chunk scheduling | `NEEDS_EVIDENCE` |
| `emitter/branch.go` | Branch and comparison assembly generation | `NEEDS_EVIDENCE` |

`emitter/chunk.go` is required context for the emitter closure, but it is excluded from new coverage and reused only by identity from candidate 0009, which remains pending independent review. The evidence also records previously examined Porymap and FireRed bridge files as `reused_prior_evidence`; they do not increase the new source count.

## Cross-repository producer and consumer boundary

The checker verifies source identities and compiler call/token anchors. Existing generated-include CI separately builds the pinned Poryscript CLI and feeds its generated `.inc` through the pinned FireRed preprocessor and ARM assembler.

The evidenced relationship is:

1. Porymap `src/project.cpp` creates a `.pory` script and appends a `scripts.inc` include to the shared event-script assembly file.
2. The Poryscript compiler translates `.pory` source, including `mapscripts` syntax, into assembly text in the generated `.inc`.
3. FireRed `data/event_scripts.s` consumes assembly includes. The existing native generated-include test establishes the compiler/include/assembler boundary for its fixture, not a complete project or ROM build.
4. FireRed `mapjson` independently consumes map JSON and emits map-related assembly. It does **not** consume Poryscript output. These producers converge in the broader build but are not one direct data-flow chain.

The evidence matrix records exact source identities for the reused Porymap/FireRed anchors and prior dossier byte hashes. It deliberately does not re-run the mapjson, map connection, native ABI, or GUI tests.

## Licensing and artifacts

The pinned Poryscript `LICENSE.md` identifies the MIT License and its copyright/permission notice. The pinned Porymap root `LICENSE.md` contains GNU LGPL text. The pinned FireRed tree has no root `LICENSE`, `LICENSE.md`, `COPYING`, or `COPYING.md` entry; this is only an inventory observation, not a legal or redistribution conclusion.

CI emits a JSON matrix with every source Git blob and full-byte SHA-256, byte/line count, producer-consumer role, reused/new coverage label, license evidence, and this dossier's SHA-256. It also records exact SHA-256 hashes for the five reused prior dossiers and creates a deterministic compressed archive containing this dossier and matrix, with a separate SHA-256 sidecar. These artifacts are evidence records, not source redistribution or approval.

## Fail-closed checks and limits

The checker rejects nine Poryscript source-anchor mutations plus one mapjson direct-consumer mutation, and fourteen evidence mutations. Controls include pin/count drift, missing prior-dossier hashes, false approval, gate, direct-mapjson-edge, and runtime claims. All rows remain `NEEDS_EVIDENCE`; no reviewer identity or independent semantic approval is inferred from hashes, source anchors, CI, or artifact generation.

This package does not establish a complete Porymap GUI save, a complete FireRed root build/ROM, generated map correctness in a game, physical-media durability, or runtime/gameplay behavior. Existing adjacent experiments and candidate files remain subject to their own limitations and independent review. Phase 1 is still `FAIL_INCOMPLETE`, with zero approvals.
