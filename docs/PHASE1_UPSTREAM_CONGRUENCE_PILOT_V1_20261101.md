# Phase 1 upstream-congruence pilot v1 — 2026-11-01

**Status: prospective, read-only proposal on draft PR #2. No dispositions were added.** This pilot does not alter the historical gate, its external-review metrics, PR8, or the Copilot receipt lane. The PR8 source index is cross-branch evidence, not merged policy.

## Reproducible inventory bridge

`tools/phase1_upstream_congruence_pilot_v1.py` accepts only the pinned PR8 index and its original dossier archive. It verifies both files' SHA-256 and Git blob identities, checks the index snapshot against the PR8 gate/queue/dossier pins, then cross-reconciles every indexed `(repository, path, source blob)` and canonical dossier record against PR2's separately pinned queue and original dossier archive. It rejects missing, extra, duplicate, altered, or approval-marked records. The index's lexical include candidates remain candidates, not a complete compiler, call, data-flow, or consumer graph.

The PR8 compressed dossier archive is not byte-identical to PR2's archive:

| Archive | SHA-256 | Git blob |
| --- | --- | --- |
| PR8 at head `12bebda10473877e8f82faf3806d4fbbf0f882df` | `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609` | `3b982876c7d810a827af8c80c7e5d9231fdaa327` |
| PR2 historical baseline | `c47d1fea819e7df59f67bfe8d1bc4dc2650483d03563957145f7331ed099005b` | `143c373f9aae5b9cb24af39abb7d8244362d23b5` |

Both contain 14,834 records; all 14,834 canonical dossier records and inventory identities reconcile with zero mismatches. The pinned PR8 index is `docs/phase1-review-readiness/inventory-source-index-20261101.json.gz`, SHA-256 `aaeb605aa9906e979b66c532bc34336f88d8255e534701f2ea6629da3de8a0db`, Git blob `d82c9edd68b3facb4cdc1623111f62c397c0b486`. Its own result says 14,834/14,834 source identities indexed, 338/338 P0 identities present, and zero semantic dispositions or approvals.

Download those exact public artifacts and run:

```sh
curl -fL 'https://raw.githubusercontent.com/xbaconator9000x/XGBA-ROM-Expansion/12bebda10473877e8f82faf3806d4fbbf0f882df/docs/phase1-review-readiness/inventory-source-index-20261101.json.gz' -o /tmp/phase1-inventory-source-index.json.gz
curl -fL 'https://raw.githubusercontent.com/xbaconator9000x/XGBA-ROM-Expansion/12bebda10473877e8f82faf3806d4fbbf0f882df/semantic-snapshots/current/candidate_review_dossiers.jsonl.gz' -o /tmp/phase1-pr8-dossiers.jsonl.gz
python3 tools/phase1_upstream_congruence_pilot_v1.py \
  --pr8-index /tmp/phase1-inventory-source-index.json.gz \
  --pr8-dossier /tmp/phase1-pr8-dossiers.jsonl.gz
```

The tool reports source identities recorded by that pinned index; `source_bytes_reopened_in_this_run` is explicitly false. Recreating the index still requires the five source checkouts at their immutable pins. The report never upgrades index records, machine dossiers, source assertions, or test presence into semantic dispositions.

## Measured mGBA ROM-memory pilot

The bounded dependency-connected pilot anchors six P0 source files at mGBA revision `fd9dc5c2cbf234365068855851107e762fc6211b`: `src/arm/arm.c`, `src/gba/cart/matrix.c`, `src/gba/dma.c`, `src/gba/gba.c`, `src/gba/memory.c`, and `src/gba/serialize.c`. Their exact Git blobs and source SHA-256 values are pinned in the evaluator and reported per file. The index's undirected literal-include candidate graph connects all six within a 759-node candidate component. That broad lexical component is not a compiler-resolved dependency or consumer closure; the six anchors are a scoped pilot, not a claim that the remaining 753 nodes have been reviewed.

| Measure | Result |
| --- | ---: |
| Candidate files | 6 |
| Eligible under exact-byte-only v1 | 0 |
| Ineligible under v1 | 6 |
| v1 reason | `NO_DISTINCT_BYTE_IDENTICAL_IMPLEMENTATION_REFERENCE` (6) |
| Existing pinned v1 proposal-register records | 0 |
| Behavioral-congruence `PASSED` | 0 |
| Behavioral-congruence `NEEDS_REVIEW` | 6 |
| PR8 direct test-link candidates for these files | 0 |
| PR8 lexical include candidates | 48 unique pinned-path candidates, 1 unresolved |
| Lexical component containing all six pilot files | 759 candidate nodes |
| Source-order contract rows in PR2 | 6 across 2 files |
| Pinned native runtime paths exercised | 0 |
| Distribution clearance | `NOT_ASSESSED` |

The six source-order contracts are not whole-file semantic maps. The existing native mGBA boundary fixture is pinned as test source but its checkpoint says it has not been compiled or executed. The source-index catalog likewise labels its test-source inventory as present but not executed and license-file presence as not distribution clearance. No test result or semantic signoff is inferred.

The behavioral evidence schema `xgba.phase1.behavioral_congruence_evidence.v1` is deliberately separate from exact-byte v1. Its structural validator requires whole-file line coverage and claim IDs; source-backed semantic statements and specification references; complete dependency and consumer closure; positive and negative test coverage for the claims on the exact source revision with executed successful Actions jobs; license clearance; and no unresolved objections or contradictions. Each referenced artifact and Actions run must be independently reverified. Synthetic positive/negative unit fixtures exercise those checks only; they are not accepted by the live CLI, produce no receipt, and are excluded from all counts.

The candidate reason codes include:

- `NO_WHOLE_FILE_SEMANTIC_MAP`
- `LEXICAL_INCLUDE_CANDIDATES_ARE_NOT_DEPENDENCY_CLOSURE`
- `PINNED_POSITIVE_AND_NEGATIVE_TESTS_NOT_EXECUTED`
- `LICENSE_DISTRIBUTION_CLEARANCE_NOT_ASSESSED`
- `WHOLE_FILE_DEPENDENCY_AND_CONSUMER_SCOPE_NOT_ESTABLISHED`
- `SUBSTANTIVE_ROM_BOUNDARY_OBJECTIONS_REMAIN_OPEN`
- `UNRESOLVED_LITERAL_INCLUDE_CANDIDATE` for `src/gba/serialize.c`

The open native-ROM obligations include backing-file bounds and short-read handling during Matrix remaps, instruction prefetch invalidation and bank-switch arbitration, DMA/EEPROM/e-Reader interactions, and save-state backing identity. The source-anchored fixture describes probes for some cases but does not close these risks.

## Validation and counters

Run the pilot unit fixtures with:

```sh
python3 -m unittest discover -s tests -p 'test_phase1_upstream_congruence_pilot_v1.py'
```

The CLI currently reports `FAIL_INCOMPLETE`, `legacy_external_independent_approved=0`, `legacy_p0_external_independent_approved=0`, `behavioral_congruence_passed_count=0`, and six files remaining in this pilot. The pilot has no effect on the legacy `0/338` P0 or `0/14,834` external approval metrics. Any future prospective semantic total must union only separately validated dispositions by unique pinned identity; it must never add to or reinterpret the legacy external-review metric.
