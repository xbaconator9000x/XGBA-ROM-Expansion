# Phase 1 review-readiness packets — machine-only handoff

The packet generator consumes exact-pinned, source-verified machine-triage shards and requires their upstream integrity manifest, including per-shard SHA-256 hashes. It produces a deterministic P0-first queue of review obligations. Source hashes, line counts, lexical include anchors and risk flags are carried through without asserting whole-file semantic understanding.

An include edge is a **candidate lexical match**, not proof of actual preprocessor resolution. Ambiguous, invalid and unresolved include names are preserved for review. A match cannot establish cross-repository compatibility, runtime behaviour, external consumers, build variants or source-code correctness.

After the source-verification workflow has committed the complete 2,000-file integrity manifest, run:

```sh
python3 -m unittest discover -s tests -p test_phase1_review_packets.py -v
python3 tools/phase1_bulk_triage_integrity.py
python3 tools/phase1_review_packets.py --max-packets 100 --output docs/phase1-review-readiness/packet-0000-0099.json
```

The ten positive/negative controls cover duplicate identities, wrong source hashes, fabricated approvals, unverified sources, invalid offsets, ambiguous include resolution and missing/tampered integrity evidence. The generator fails closed when the required upstream reconciliation has not completed. The output must not be committed or reported as source-verified without checking the complete manifest and exact-head CI.

**Counting:** review packets are not substantively prepared whole-file dispositions, independent approvals or a Phase 1 pass. At this checkpoint, the last confirmed baseline is **113/14,834 prepared (0.7618%)**, **0/14,834 approved (0.0000%)**, **14,834/14,834 inventoried (100%)**, gate **FAIL_INCOMPLETE**. Machine triage is separate. Actual independent reviewers must examine each complete pinned file and unresolved dependencies.
