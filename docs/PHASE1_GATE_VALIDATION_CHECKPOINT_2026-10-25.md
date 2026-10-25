# Phase 1 semantic disposition gate — fail-closed validation checkpoint (2026-10-25)

**Scope:** This checkpoint hardens the review gate; it does not approve any source file, implement an expanded ROM, or certify Phase 1 completion.

## Source-backed defect and bounded correction

The previous `tools/phase1_mapping_gate.py` incremented `approved_semantic_dispositions` whenever a submitted row's status belonged to the approved status set, **even when that same row had a stale source blob, stale dossier evidence, missing independent reviewer, insufficient rationale, or missing contract IDs**. Duplicate rows could also inflate the count. The gate decision remained `FAIL_INCOMPLETE` when it found such errors, but its reported approval count was misleading.

The gate now counts only unique, source-manifest-matching dispositions that pass every per-row validation. `remaining_dispositions` includes unapproved or invalid rows, not merely missing rows. Submitted but invalid reviews remain fail-closed. No reviewer identity, signoff, or contract ID has been invented.

## Reproducible regression controls

`python3 tools/phase1_mapping_gate.py --self-test` exercises a valid example and negative cases for source hash drift, dossier hash drift, unapproved status, missing reviewer, short rationale, and blank mapped-code contract IDs. It also checks both non-mapped approved status classes. The test is wired into the `Verify Python syntax` step of the pinned-source census workflow, before any upstream clones or long scans.

- Gate implementation commit: [`72f7c863`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/72f7c8631fe4babecfece4c90d6112a20cf7b277)
- CI test integration commit: [`841ee5db`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/841ee5db253a05cd0abe5d44efc9d83d0a2e390b)
- [Full Phase 1 census run for the integrated change](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40196534638). The `Verify Python syntax` step passed when this checkpoint was written; the full run's final outcome must be checked independently.

## Unchanged authoritative gate

The last durable mapping snapshot remains `FAIL_INCOMPLETE`: 14,834 pinned files inventoried, 4,685 source/config blobs verified, **0 independent semantic dispositions approved**. This is an integrity improvement to the review accounting, not progress toward approving the 14,834 files. The pinned revisions and existing semantic evidence were not changed.
