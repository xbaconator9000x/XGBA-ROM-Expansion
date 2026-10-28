# Phase 1 P0 — independent semantic review attestation gate (26 October 2026)

**Decision: FAIL_INCOMPLETE. This change authenticates the reviewer attestation boundary; it does not approve any of the 14,834 tracked files or implement XGBA.**

## Found in the existing gate

The original `tools/phase1_mapping_gate.py` checked a disposition's source Git blob SHA, generated dossier SHA-256, accepted status, minimum-length rationale, contract IDs and a nonempty `reviewer` string. The `reviewer` string was **self-asserted**: anyone preparing a disposition CSV could write `independent-reviewer` and satisfy the structural predicate. Consequently a fabricated CSV containing all 14,834 correctly keyed entries could have produced `PASS_MAPPING_ONLY` without an independent reviewer having signed anything. This is a gate-design weakness, **not** evidence that such a CSV exists or that a false Phase 1 approval occurred.

## Corrected review provenance

A valid disposition now additionally requires:

1. An **independently provisioned** reviewer identity and pinned Ed25519 public key in `semantic-snapshots/review-trust/trusted_reviewers.json`. The repository owner is excluded from the independent reviewer set; duplicate, malformed, missing or changed keys are rejected.
2. A detached base64-encoded Ed25519 signature in `review_signature_b64`, verified with OpenSSL against the registered public key.
3. A signature over a canonical, versioned JSON statement that binds `repo`, `path`, exact source `git_blob_sha`, exact machine dossier `evidence_sha256`, disposition `status`, `semantic_rationale`, `contract_ids` and `reviewer`. Editing any one of these fields invalidates the signature.
4. All original structural and inventory checks still apply. Missing trust material, signature, verifier or key digest **fails closed**. A signed statement cannot bypass a missing or incorrect source blob, dossier or file inventory.

The trust registry is deliberately **empty**. No independent reviewer has been provisioned, no signatures are asserted, and the mapping gate remains `FAIL_INCOMPLETE` with **0/14,834 approved dispositions**. Do not manufacture reviewer keys, attestations or approval events to make CI green.

### Reviewer onboarding and trust boundary

Before accepting a real reviewer key, verify the person's identity and independence outside the CSV, check their public-key fingerprint with them, and review the trust-registry change through an appropriately protected GitHub branch/PR. The key owner must actually inspect the entire exact pinned file and dependency/contract evidence before signing the canonical statement. Merely possessing a trusted key does not establish that a semantic conclusion is correct; substantive independent review and required compiled/runtime gates remain separate. Repository administrators can change a trust registry unless branch protections and independent change review are enforced, so **cryptographic signatures alone do not prove organizational independence**.

For a future real review, the signing party must generate the canonical bytes with `statement_bytes(disposition)` in `tools/phase1_review_attestations.py`, sign those exact bytes using their **private** Ed25519 key with `openssl pkeyutl -sign -rawin`, and supply the base64 detached signature. Private keys must never be committed or uploaded. The reviewer trust manifest stores only the public PEM path and its SHA-256.

## Reproducible negative controls

`python3 tools/phase1_mapping_gate.py --self-test` now runs the original structural guards plus an isolated, temporary Ed25519 fixture: a correctly signed synthetic row is accepted **by the signature verifier only**, while an absent trust root, all eight signed-field mutations, malformed signature and repository-owner self-review are rejected. These fixtures do **not** produce semantic signoffs.

The lightweight `phase1-review-attestation-gate.yml` workflow checks syntax, signature negative controls and trust-registry integrity. The full pinned census workflow also exercises the gate; the census's expected nonzero `FAIL_INCOMPLETE` result remains nonfatal for evidence collection. A green workflow means only that its tested verification rules ran; it does not certify Phase 1 completion.

## Still outstanding

- Independent reviewer recruitment and vetted public-key onboarding (currently none).
- Actual whole-file semantic dispositions for 14,834 tracked files, beginning with the 338 heuristic P0 and the 29 curated high-risk cross-source candidates.
- Source-level alias/control-flow closure, compiler/linker variants, mGBA fetch/DMA/peripheral/save-state contracts, editor round trips and runtime negative controls.
- A protected reviewer trust and disposition change process, with immutable approval provenance and a separate full compatibility/release decision.

**No Phase 2 architecture changes are authorized by this checkpoint.**
