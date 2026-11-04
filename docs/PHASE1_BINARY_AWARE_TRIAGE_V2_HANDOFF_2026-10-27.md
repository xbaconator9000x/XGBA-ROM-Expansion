# Phase 1 binary-aware machine triage v2 — isolated review handoff (2026-10-27)

**Scope:** issue #9; Phase 1 evidence quality only. **No independent approvals or Phase 2 work.** Authoritative gate remains `FAIL_INCOMPLETE`.

## Source of truth and historical boundary

The main Phase 1 worker's `phase1/firered-layout-writers-20261026` branch has a 14,721-record legacy v1 machine-triage manifest at `docs/phase1-machine-triage/integrity-000000-014720.json`, produced after a successful bounded 721-file reconciliation run. It excludes 113 prepared review-register identities. **These are exact-source machine triage, not whole-file semantic approvals.** This isolated branch is based on the older review-readiness branch; do not merge or overwrite its old batch shards into the main worker branch.

The original 4,000-file sample contains 885 files with explicitly binary extensions (.bin, .png, .gba). Legacy v1 assigned source-line semantics to them. Exact Git blob identity and SHA-256 evidence can still be valid; the source-line and lexical interpretations are not.

## Typed v2 evidence contract

`tools/phase1_bulk_triage.py` now emits `xgba-phase1-machine-triage-v2` for newly generated records. It checks PNG chunk CRCs and IEND/IHDR structure, checks the GBA header marker and complement, rejects malformed/ambiguous formats as `unknown_binary`, and limits text analysis to UTF-8 without NUL bytes and explicitly recognized text extensions. The source still must be retrieved from the exact pinned tree, with Git blob SHA-1 and full-byte SHA-256 checks.

For binary or unknown kinds, source-line counts/digests are null; source includes, conditional lines and lexical hazards are empty. Dossier lexical/symbol samples are suppressed, with only explicitly unverified dependency hints retained. Format signature, byte count and byte digest remain, with a format-specific producer/consumer review obligation. Classification is **not** binary semantic approval or a proof of consumer compatibility.

`tools/phase1_bulk_triage_integrity.py` accepts historical v1 records as **legacy** without reinterpreting their evidence and validates v2 kinds fail-closed. Negative controls cover valid PNG with embedded risk strings, invalid PNG CRC, valid/invalid GBA header, opaque and ambiguous .bin, unknown binary, valid C includes, hash preservation, invalid line anchors, lexical leakage and forged approval.

## Migration and acceptance gates

1. Do not change the 14,721 historical manifest, gate totals, or 113 prepared baseline in place.
2. On a separate integration branch based on the **current** main-worker head, regenerate legacy records using exact pinned Git bytes into **new** v2 shards. Reconcile deterministic source identity, historical v1 manifest hash, disjoint prepared register, contiguous offsets and v2 kind constraints; retain both manifests and record the differences. If register has advanced to 114+ on a separate branch, explicitly reconcile identities before selecting or claiming totals.
3. Review all unknown/ambiguous kinds and their real producers/consumers; record binary format, layout, dimensions, offsets, endian/packing and editor/runtime dependencies as applicable. Source signatures alone are insufficient.
4. Run typed negative fixtures, v1 backward-compatibility checks and full shard reconciliation in CI at the **exact integration head**. No fabricated reviewer signoff, no manual gate changes, no self-approval.
5. Only after verified evidence and independent review should a substantive candidate or approved count change. Do not equate source verification with semantic disposition.

**Isolation:** `phase1/binary-aware-triage-issue9-20261027` is a quality-fix branch, not the authoritative 14,721-file checkpoint branch. Existing main-worker runs and PR #10 are untouched.
