# Phase 1 — original FireRed root Makefile generated Poryscript object (2026-10-29)

**Status: exact-head CI pending; FAIL_INCOMPLETE; independent approvals 0/14,834.** This is not a whole-file disposition or a Phase 2 implementation.

## New boundary, distinct from the already-green isolated Makefile fixture

The earlier PR27 executable test built Porymap's default .pory using a minimal test-only Makefile and separately invoked FireRed's native preprocessing pipeline. This new test instead executes the **original pinned FireRed root Makefile** and its **real data/event_scripts.o target** after applying only the existing Poryscript README's documented generation rule in a disposable detached source checkout. The full original data/event_scripts.s is preserved with one appended test-only include. The source checker pins all original commits/blobs and rejects eight source-semantic mutations.

Exact upstream identities: pret/pokefirered ce6406d8c2eaf46d543c8a2606de0c3cb1951982, Makefile blob 8b454dbd18eb0069fa5851d788697190890a5b37, data/event_scripts.s blob 88d75946a7300ccf952f4a36c283966c6aebf5c0, tools/preproc/preproc.cpp blob 20c2de51b635a5d59f2b4e1ecd93d8fc2748ebe1; huderlem/poryscript c32481161c767b25a3425fa9f1f8729927ff3d55, README blob c77e022eb86e74a41b184daac5953d14c72cacc3; huderlem/porymap 26b919d7ff4b54152de010abd5bf344af2ebe116, src/project.cpp blob d43b0949303433111d4478ad76117c2b3445dd13.

## Mandatory maximum reuse

Use the existing Porymap default map script, existing Poryscript Go CLI and documented AUTO_GEN_TARGETS/data/%.inc rule, original FireRed root Makefile and preproc, C preprocessor and GNU ARM assembler. No replacement compiler, assembler, editor or exporter. The test requires root Makefile's generated target to discover the new script; executes root make to generate scripts.inc and compile build/firered/data/event_scripts.o; verifies the generated map-script symbol with GNU ARM nm; and records only SHA-256 identities and JSON. It requires unchanged input to avoid regeneration, removal of the rule to fail, malformed input to fail and recovery to reproduce identical bytes. Fifteen evidence mutations must fail closed.

The test modifies the **disposable checkout's working tree only**, restores the original Makefile and event_scripts.s in finally, and never commits or distributes upstream assets. Original upstream commits remain unchanged.

## Limitations and reviewer obligations

Even if CI passes, this is an original-root-build **object-level** integration, not a complete FireRed ROM link, real Porymap GUI new-map save, mGBA native map-script reader execution, malformed-table safety, or crash-consistent multi-file transaction. It does not address the native Trainer Tower special-sector transaction. The root Makefile may expose unanticipated dependency or tool ordering; preserve failure logs and fix only the actual failing assumption. Poryscript's pinned license is MIT, Porymap's inspected root is LGPL-3.0, and other upstream code/assets/toolchains require component-specific licensing review before distribution.

**Reviewer questions:** Does the root build retain the generated dependency in every build configuration? Can the real editor GUI save and reopen a new map with Poryscript mode? Are malformed records bounded in actual mGBA ARM execution? Do all relevant whole-file source identities receive independent review? No approvals are added here. All Phase 1 gates remain FAIL_INCOMPLETE.
