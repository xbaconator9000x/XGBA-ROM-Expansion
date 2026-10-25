# Phase 1 curated P0 registry fail-closed metadata checkpoint — 2026-10-26

**Authoritative mapping gate:** FAIL_INCOMPLETE; 0/14,834 independent whole-file dispositions.

## Reproduced audit-script validation gap

The 29-file pinned cross-repository semantic candidate registry has source-backed roles, Git blob identities, and explicit pending-review flags. The prior `tools/verify_curated_p0_semantic_registry.py` did **not** validate `evidence_class` and accepted an absent or empty `source_documentation` list. A syntactically valid `docs/../...` path could also pass its documentation existence check. Consequently a changed registry could retain a passing source-identity audit while silently weakening or misrepresenting its *manual, unsigned evidence* metadata. This is a verifier defect, not a finding about any pinned upstream source.

## Bounded correction

Commit [`11e8b3811b469727590188477897510499965bec`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/11e8b3811b469727590188477897510499965bec) requires the curated entries to retain their exact `SOURCE_PINNED_MANUAL_SEMANTIC_INTERPRETATION_WITH_SOME_COMPILED_AND_RUNTIME_SUPPORT` evidence class; requires a nonempty, typed, nonduplicate documentation list; and rejects documentation traversal, non-Markdown paths and missing documents. It adds three negative fixtures to the five existing false-approval/identity guards, for **eight** negative fixtures. Existing Git blob verification, source roles, and zero-approval state remain unchanged.

## Verification boundary

[Previously active pinned census run #40222453857](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40222453857) has **completed successfully**, including the existing curated verifier; it predates this new validator commit. The dedicated Phase 1 census workflow is configured to trigger when `tools/verify_curated_p0_semantic_registry.py` changes. A new run's outcome must be inspected before claiming the eight-fixture change is CI-verified. Passing census is **not** independent semantic review or Phase 1 completion.

## Subsequent verification (2026-10-26)

[Phase 1 census workflow #40226474522](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40226474522) completed **successfully**. Its census job, including the curated registry verification step and the Phase 1 gate evaluation step, reported success. This confirms the **workflow** completed on the updated validator; the gate step's successful execution does **not** mean the gate passed. The authoritative decision remains **FAIL_INCOMPLETE**, with 0/14,834 independent whole-file dispositions. The authoritative status was reconciled in commit `38359f97c624678dd4111612e45d4332d3fe9cac`. No new runtime expansion or independent semantic review is claimed.
