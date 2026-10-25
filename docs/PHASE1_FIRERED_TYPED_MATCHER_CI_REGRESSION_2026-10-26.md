# Phase 1 P0 FireRed typed-definition matcher regression checkpoint — 2026-10-26

**Gate:** FAIL_INCOMPLETE; no independent whole-file semantic dispositions.

## Observed CI failure and diagnosis

[Compiled FireRed variants run 40212610996](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40212610996) failed at step 8 **after both original agbcc and modern GCC FireRed builds succeeded**. Its log raises `SourceContractFailure: Missing/nonunique C definition RunScriptCommand` in `tools/field_script_stack_lifetime_semantics.py:function_body`. The pinned upstream `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c` has `bool8 RunScriptCommand(struct ScriptContext *ctx)` at lines 82 onward; the problem was the audit tool's C-definition matcher, **not evidence of a FireRed compiler or emulator defect**.

Earlier corrective commits `447b72c`, `a109621`, and `66a321a` restored a typed C definition matcher and added Python syntax checking to the CI path. [Later source census run 40212948395](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40212948395) completed successfully; it does **not** prove the previously failed compiled-variants step has rerun.

## Bounded regression control

Commits `f19f744` and `02e67f4` add **three positive and four negative synthetic matcher fixtures** directly to the pinned script stack verifier, then correct the Python fixture newline escaping. Positive fixtures exercise the exact C declaration families used by `RunScriptCommand`, `ScriptPop`, and `ScriptCall`. Negative fixtures reject untyped call-expression lookalikes, comment-only declarations, prototypes without bodies, and duplicate definitions. The existing seven source-mutation controls remain required. The matcher fixture cases were also executed in a standalone Python reproduction before commit (3 positive and 4 negative PASS); the updated complete pinned-source CI run is **not yet confirmed**.

These controls guard the evidence pipeline from false-positive/false-negative function extraction. They do not prove script stack behavior on compiled hardware, bank remap safety, or the Phase 1 semantic gate.

**Next check:** inspect the next actual `compare-compiled-variants` workflow job, verify its script lifetime contract output and artifact, and do not count the separate census success as a substitute.
