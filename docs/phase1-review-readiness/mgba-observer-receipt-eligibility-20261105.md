# Phase 1 mGBA observer receipt-eligibility closure

This handoff reuses the already-pinned cross-backend, platform-observer, and
fault-to-observer matrices. It adds no mGBA source review or runtime test.
`tools/phase1_mgba_observer_receipt_eligibility.py` verifies all three
workpapers against the exact upstream checkout and emits deterministic JSON.

## Source-record disposition

The report contains the 16 distinct records already designated
`reviewed_source_only` in the cross-backend workpaper. For each, the checker
preserves the pinned Git blob, full-source SHA-256, canonical dossier-row
SHA-256 and dossier archive SHA-256; it carries forward license terms, source
scope, linked dependency edges, and known objections. It does not duplicate
the reused prior-source inventory. The 11 platform records retain their
existing scoped or identity-only disposition and are not promoted to complete
file reviews.

Under the user's explicit status override, the 16 records may be labeled
`COPILOT_REVIEWED/PASSED` for their pinned-source scope only. Every record is
attributed to Copilot and explicitly marked non-independent, with no GitHub
independent review ID. This is not an `APPROVED` disposition and does not
change the authoritative review register, historical counts, or gate.

Receipt eligibility remains `FAIL_INCOMPLETE` unless both a successful
pull-request run and a successful push run from workflow `398059096` are
provided for the same exact PR branch SHA, and separate independent per-file
attribution is established. The checker validates normalized run metadata
fields but does not authenticate the source of a supplied metadata snapshot;
actual run IDs and results must be reconciled against GitHub Actions. It rejects
stale/wrong-head evidence, wrong event or workflow, duplicate run IDs,
unsuccessful runs, missing source or dossier identity, duplicate paths, altered
dependency evidence, and unsupported status claims. CI evidence is supplied as
a JSON snapshot with `--ci-evidence`; omission is an explicit blocking result,
not a pass.

## Still unresolved

The five Qt, SDL, libretro, Python, and headless log-delivery paths remain
`NEEDS_EVIDENCE`: their source-level routing does not prove a frontend emitted
or displayed the message. The eight console/platform observer paths also
remain `NEEDS_EVIDENCE` for native platform behavior. A compiled Linux host
logger witness is not frontend execution. Dirty-to-clean callback behavior is
not persistence acknowledgment; no real save persistence, stock gameplay,
physical Flash, or power-loss durability is claimed.

The existing PR workflow remains the only workflow. Its path-scoped push
trigger is limited to this existing draft branch and this eligibility package
so exact-head PR and push evidence can both be checked; it does not modify
main, the authoritative gate, or any approval count.

## Validation

The focused suite exercises the canonical 16-row output and fail-closed
mutations for missing/stale PR or push evidence, source/dossier mismatches,
duplicate review identities, false frontend delivery, host/synthetic evidence
mislabeling, durable-save claims, physical Flash claims, and misleading
`APPROVED` or external-human attribution.
