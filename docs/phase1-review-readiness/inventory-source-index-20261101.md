# Phase 1 inventory-wide source index (2026-11-01)

This is a deterministic source-identity and evidence-presence index for the
existing 14,834-record Phase 1 machine inventory. It extends the focused
upstream-evidence pilot to every inventory entry; it does **not** make semantic
dispositions or approvals.

## Result

The compressed machine-readable result is
[`inventory-source-index-20261101.json.gz`](inventory-source-index-20261101.json.gz),
SHA-256
`aaeb605aa9906e979b66c532bc34336f88d8255e534701f2ea6629da3de8a0db`.
It contains one source record for every queue record, retains each record's
original machine-dossier SHA-256, and carries the original machine-triage
counts/rule buckets without elevating them to semantic findings.

| Measure | Result |
| --- | ---: |
| Exact pinned inventory/dossier records indexed | 14,834 / 14,834 |
| Blocked or unindexed records in final artifact | 0 |
| P0 records indexed | 338 / 338 |
| Literal C/assembler include candidates | 15,027 |
| Unique pinned-path candidates | 9,311 |
| Ambiguous pinned-path candidates | 60 |
| Unresolved/out-of-inventory include candidates | 5,656 |
| Records with a direct test-include candidate | 51 |
| Test source files hash-verified (not run) | 94 |
| Documentation files hash-verified (not reviewed) | 188 |
| License/notice files hash-verified (no clearance) | 28 |
| Semantic dispositions added / legacy approvals | 0 / 0 |

One source exceeded the bounded 512-literal-include scan. Its source identity
is still verified, while its record marks the lexical include scan incomplete.
The output marks 1,790 records as having no hash-verified test source in the
current index; this is especially relevant to repositories with no inventory
paths matching the test-source classifier. It is not a claim that upstream
has no tests. Per-file test links are candidate links only, not coverage.

The inventory was processed in eight batches (2,000 records per batch except
the final 834). Their recorded indexer times sum to 34.468 seconds. A final
cache-only pass revalidated the source and dossier identities for all 14,834
records in 6.203 seconds. All runs preserved `FAIL_INCOMPLETE`, 0/338 P0
approvals, and 0/14,834 total approvals.

## Reproduce

Extract the five repositories at the exact commits in
[`phase1_bulk_triage.py`](../../tools/phase1_bulk_triage.py) into a directory
named with each repository's final path component (for example, `mgba/` and
`pokefirered/`). The indexer accepts either those names or a single
`name-<suffix>` directory under `--source-roots`.

Run the same bounded batch command repeatedly. Each invocation verifies the
original queue and all 14,834 compressed dossiers, revalidates cached source
records against the current pinned source bytes, then selects the next
unindexed records in P0-first order:

```sh
python tools/phase1_inventory_source_index.py \
  --source-roots /path/to/pinned-source-roots \
  --cache /path/to/local/inventory-source-cache.json.gz \
  --output docs/phase1-review-readiness/inventory-source-index-20261101.json.gz \
  --offset 0 --limit 2000
```

Repeat until `run.indexed_count` equals `gate.inventory_total`. If an
invocation makes no indexing progress, inspect its
`blocked_or_unindexed_records`; do not treat a blocker as an indexed record.
The cache is local, compressed, checksummed per record, bound to the exact
queue/dossier/gate snapshot blobs, limited to 64 MiB compressed and 512 MiB
expanded, and stores derived metadata rather than source contents. Its
checksums detect accidental corruption, not malicious tampering by someone
able to rewrite both the cache and its checksums. Every source/dossier identity
is revalidated from the provided roots on each invocation. The cache does not
act as semantic evidence.

## Evidence and limits

- The generator verifies the original queue, all dossier digests and
  provenance, the authoritative gate, every upstream Git blob ID, and the
  dossier's source SHA-256 when that field is present. For files materialized
  with CRLF by the source archive, it reads the repository's pinned
  `.gitattributes`, normalizes only matching `text eol=crlf` files, and accepts
  the result only when the normalized bytes reproduce the queued Git blob.
- Symlink targets are read as link text, not followed. Paths that escape a
  repository root are rejected. Missing roots/files, source drift, invalid
  attributes, dossier mismatch, and malformed/corrupt cache entries fail
  closed with reason codes.
- Dependency edges cover only literal C-preprocessor `#include` and
  assembler `.include` declarations. Path resolution creates pinned-inventory
  candidates; it is not preprocessor/compiler resolution. Generated,
  conditional, macro-expanded, Go-module, build-system, runtime, call-graph,
  and data-flow dependencies are not resolved here. Incoming include links
  are not caller/reader/writer analysis.
- Repository catalogs enumerate hash-verified test, documentation, and
  license/notice file paths. Test presence is not test execution, relevance,
  coverage, or build/runtime evidence. Documentation identity is not a
  semantic review. License text is not per-file legal clearance or
  combined-distribution approval. Porymap and agbcc have no paths matching
  this inventory's test-source classifier.
- No semantic invariants are automatically extracted by this index. The
  existing focused memory pilot remains separate; neither artifact substitutes
  for whole-file review, source-level dependency closure, compilation,
  gameplay/save-file testing, native mGBA execution, or physical Flash testing.
- GBATEK and NBA hardware-documentation references remain unverified and
  support no claim. The output explicitly records that limitation.

The authoritative mapping gate remains `FAIL_INCOMPLETE`. This index does
not alter the inventory, prepared-review register, semantic receipt register,
legacy approval counts, source pins, main/audit branches, or Phase 2 scope.
