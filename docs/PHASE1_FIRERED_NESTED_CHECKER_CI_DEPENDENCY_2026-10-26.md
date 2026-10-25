# Phase 1 FireRed compiled-ABI CI dependency closure — 2026-10-26

**Authoritative Phase 1 gate: FAIL_INCOMPLETE; independent whole-file approvals: 0/14,834.** This is CI dependency integrity, not a semantic signoff.

## Verified audit failure and source contract

The [compiled FireRed variants run 40212610996](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40212610996) completed with failure at the compiled symbol/source ABI comparison step after both pinned compiler builds succeeded. The fetched job log records `SourceContractFailure: Missing/nonunique C definition RunScriptCommand` from `tools/field_script_stack_lifetime_semantics.py`. The pinned [FireRed source at `src/script.c:82`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c#L82) actually declares `bool8 RunScriptCommand(struct ScriptContext *ctx)`; the failure was in the audit extractor, not a proven FireRed runtime defect. The existing [typed matcher regression checkpoint](PHASE1_FIRERED_TYPED_MATCHER_CI_REGRESSION_2026-10-26.md) documents the earlier source matcher fix and synthetic controls.

## Newly verified CI wiring gap

The compiled workflow `.github/workflows/compiled-firered-variants.yml` runs `tools/firered_variant_semantics.py`, which invokes **both** `tools/firered_map_view_variant_semantics.py` and `tools/field_script_stack_lifetime_semantics.py` as subprocesses. However, its push-path triggers listed the parent script but omitted both nested verifiers. Consequently, direct edits to the exact audit checker that failed previously could be merged without scheduling the compiled-variants workflow. This is a reproducibility blind spot.

[Commit effbee2c](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/effbee2c10dc6cb5de880370d52ee04049b50c12) adds both nested checker paths to the compiled workflow push triggers. It changes **only** the dedicated XGBA repository's CI configuration, not the pinned FireRed source or compiled ROM.

## Verification boundary

- The [latest inspected census run 40214802383](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40214802383) was successful, but census success cannot substitute for the compiled-variants test.
- The [older compiled run 40212095204](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40212095204) passed **before** the script matcher failure and its corrections.
- A **new compiled-variants run after effbee2c is not yet confirmed**. The connector's commit-workflow lookup returned no PR-associated runs, which is not evidence that push-triggered Actions are absent. Do not mark the typed matcher fix verified until a fresh `compare-compiled-variants` job succeeds and the script-stack evidence artifact is inspected.

No active jobs were cancelled or retried, no independent semantic dispositions were fabricated, and no Phase 2 architecture was implemented.
