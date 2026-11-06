# Phase 1 ARM semantic-review blocker reconciliation — 2026-11-02

**NON-APPROVING analyst handoff.** This file records actual GitHub state and unresolved source-level objections; it is not an external reviewer signature, native mGBA result, or a new machine dossier. Scope is existing draft PR #8 and the immutable mGBA source revision `fd9dc5c2cbf234365068855851107e762fc6211b`.

## Immutable reviewed/queued identities

The original seven source-only user-defined Copilot receipts were previously validated by the actual v6 live job `125082967874` in PR #2 Actions run `41379058968`. They remain distinct from historical external-human approvals.

The eighth append-only candidate at PR #8 introduction commit `279077f773f0eb472696328ccea2ed3c554c1b0b` is `include/mgba/internal/arm/emitter-thumb.h`, original pinned Git blob `7d27524b2e723696df642a72135bac024bbd8071`, source SHA-256 `b7a0167782c8fd63665345ed4520bd00a530e792be712e111bd9b056900b7353`, original machine dossier SHA-256 `482d2a7131cef6f320f3e4786f2d3482e7a4217ca931428dd409e92d3e7da729`, receipt SHA-256 **claimed** `18261796a7ce6cb74f884a53a37cdcbe72284cc542b67264e1c41deb691075de`. Non-Copilot source evidence was introduced at `4fbd104c22d0e3fca64dfd2fe3bbdd2dc6d75b15`. The source-level Copilot review reported a host-preprocessed 1,024-entry Thumb dispatch table, 78 illegal slots, two BX and four BKPT, and resolved producer/consumer edges. These are scoped source/host findings, **not** native linked instruction semantics.

## Why the eighth candidate is NOT validated

At original receipt-introduction head `279077f773f0eb472696328ccea2ed3c554c1b0b`, pull-request Actions run `41391400026` and push run `41391395862` both returned `completed/action_required`, with **zero executed jobs**. The Copilot PR #8 conversation response `#6569456277` includes **three unquoted attestation sections for the same receipt in a single top-level comment**. The prior v6 fail-closed protocol requires a unique one-receipt-per-comment bot attestation; do not treat that multi-section response as an eligible receipt. Neither successful older-head CI nor a Copilot `APPROVED` narrative fixes these two blockers. A later exact-head successful PR and push run, a **new independently attributable single-block** bot comment, and a separate versioned live v7 validator are required before counting an eighth `COPILOT_REVIEWED/PASSED`.

## Two explicit substantive source objections, not approvals

* Packet #5, `include/mgba/internal/arm/macros.h` (original blob `4832f054611044e63f1e2393fe4072f48004545a`, dossier SHA-256 `6508e54c65f1b871f5998bb17dbf6204a73e9428e4ff57734e50e0d1e4dbf558`): Copilot traced typed-pointer LE helpers from pinned `common.h` into active-region storage, raising unresolved C effective-type/strict-aliasing and cross-platform alignment assumptions. The host correctly-typed aligned fixture is insufficient to clear these consumers. **NEEDS_REVIEW.**
* Packet #9, `include/mgba/internal/arm/isa-inlines.h` (original blob `ebda28e411f627c6cd1570aff6f29a3b79a60840`, dossier SHA-256 `22099dfd7b67ee163af3dd04afe6aed7b70f059d9df2ebb14f713aeec91f58db`): unchanged `ARM_SXT_8/16` macro expressions shift signed negative values, and host C11 UBSan reproduced `left shift of negative value -1` for `0xff` and `0xffff`; pinned ARM and Thumb signed-load call sites use these macros. This is source-level undefined behaviour, **not** a demonstrated native emulator failure. **NEEDS_REVIEW.**

The unresolved source issues must be addressed through honest semantic dispositions and bounded source evidence, not by modifying immutable upstream pins, suppressing sanitizer checks or claiming native runtime proof. The original machine dossier inventory remains 14,834; this note adds **zero** semantic approvals, zero machine dossiers and zero analyst-partial counts. MPL-2.0 file notices are not combined-work distribution clearance. Stock gameplay, native link, `.sav` restart and physical Flash remain separate unsupported claims.

## Gate and next execution

Main authoritative `semantic-snapshots/current/phase1_mapping_gate.json` remains Git blob `dab5789433dc55cf325a917a220d060088bf1d29`, `FAIL_INCOMPLETE`, external independent approvals **0/338 P0 and 0/14,834 total**. Preserve the first seven receipt bytes. This file is deliberately named `analyst-*.md` to exercise the existing `phase1-census.yml` push path; an executed successful exact-head workflow must be verified after this commit, not inferred. Then seek one new unique Copilot attestation for the eighth receipt, and implement fail-closed v7 integration on existing PR #2 only. No main/audit edits, second scheduler, new PR or Phase 2.
