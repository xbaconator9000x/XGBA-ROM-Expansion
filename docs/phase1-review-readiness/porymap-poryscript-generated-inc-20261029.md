# Phase 1 — Porymap new-map Poryscript generated include dependency (2026-10-29)

**Status: exact-head CI pending. Partial source/build contract; independent approvals 0/14,834; FAIL_INCOMPLETE.**

Pinned Porymap Project::saveMap creates scripts.pory when usePoryScript is enabled, but appends a scripts.inc assembler include to data/event_scripts.s. Its getScriptDefaultString emits mapscripts syntax, and its script discovery includes .pory. This is a source/generated artifact distinction, not by itself an editor defect.

Pinned Poryscript README.md documents the existing CLI .pory to .inc conversion and the Makefile additions required for automatic generation: SCRIPT, AUTO_GEN_TARGETS, and data/%.inc: data/%.pory. The pinned stock FireRed Makefile and all eight directly included rule/config files contain no Poryscript or .pory generation rule. Thus **generated include registration is an integration prerequisite**, not already supplied by the unmodified pinned FireRed build. This does not claim an actual full ROM build failure or exclude external build extensions.

Immutable source: huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116 src/project.cpp blob d43b0949303433111d4478ad76117c2b3445dd13; huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55 README.md blob c77e022eb86e74a41b184daac5953d14c72cacc3; pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982 Makefile blob 8b454dbd18eb0069fa5851d788697190890a5b37 and eight individually pinned included files. Eight source mutations and eight evidence mutations are required to fail closed. No whole-file semantic approval.

**Maximum reuse:** keep Porymap's .pory authoring and event-scripts references, Poryscript's existing CLI and documented Makefile rule, FireRed's original preprocessing/assembler/linker pipeline. The smallest future integration is to register .pory-to-.inc generated targets before native include scanning, verify generated output and rebuild dependencies, and report missing outputs explicitly. Do not invent an XGBA script compiler.

Licensing and distribution rights for Porymap LGPL-3.0, Poryscript and FireRed assets/tools must be checked independently. No upstream product code or ROM is modified by this investigation.

**Unresolved:** actual new-map .pory -> .inc generation and full FireRed build, malformed-table native mGBA reader, independent whole-file review. All Phase 1 gates FAIL_INCOMPLETE.
