# Phase 1 semantic evidence reconciliation — 2026-10-25

**Decision: substantial source-backed semantic mapping exists; independent whole-file dispositions remain 0/14,834. Phase 1 stays FAIL_INCOMPLETE.**

## Verified evidence, not merely a file census

- `docs/SEMANTIC_DEPENDENCIES_v16.md` records pinned source/blob-backed contracts for CPU instruction prefetch versus ROM data reads, EEPROM/Matrix DMA arbitration, typed FireRed script pointer roles, Porymap map-event/collision separation, savestate versus in-game save identity, and original/modern linker limits. These are substantive semantic findings, with unexecuted tests explicitly identified.
- `docs/PHASE1_STATUS_v27.md` reconciles 946 external object-symbol sites against final linked ELF and relocation evidence across original and modern builds. It expressly distinguishes symbol resolution from proof of runtime role.
- `docs/PHASE1_STATUS_v28.md` reports independent pinned FireRed build comparisons: original agbcc ROM reproducible; modern GCC image differs in one 64-KiB page despite stable symbols. The changed bytes' runtime significance remains unresolved.
- The full census run https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40196534638 completed successfully, including 29,068 mapping-anchor verification, all 461 script-opcode operand/cursor checks, and generated module/function evidence. Passing jobs validate those specific automated checks, **not** independent review acceptance.
- `tools/phase1_mapping_gate.py` requires a source-blob-matched, dossier-hash-matched, uniquely keyed disposition with independent reviewer and substantial rationale for every tracked file. No existing machine-generated dossier can be promoted to a signed review by inference.

## Reconciliation: what the counters actually measure

| Measure | Verified value | Meaning |
| --- | ---: | --- |
| Pinned files inventoried | 14,834 | Source coverage / provenance, not reviewed understanding |
| Source/config blobs verified | 4,685 | Hash-checked inputs, not independent signoff |
| Mapping anchors | 29,068 | Source-backed register including candidates, not approved findings |
| Function-scope dossiers | 39,530 (v2.5 checkpoint) | Machine-generated review material |
| Independent whole-file dispositions | 0 | Formal acceptance remains outstanding |

**Do not use 0/14,834 as a percentage of semantic analysis performed.** It measures the separate formal disposition gate. Conversely, do not treat the verified contracts as proof that all files are understood.

## Next bounded evidence-first work

1. Preserve and reuse the existing source-linked contracts and compiler/runtime checks; do not repeat the full census.
2. For a high-risk contract, reconcile the existing dossier's exact source hash, call/side-effect coverage, dependencies, unknowns, and executable negative controls against its source lines. Produce a review-ready evidence packet, keeping candidate and verified assertions separate.
3. Only after actual independent review, write a disposition keyed to the exact blob and dossier hashes. Never invent reviewers or approvals.
4. Continue contract-by-contract and file-by-file until the authoritative Phase 1 gate and its additional semantic/regression obligations are satisfied. Passing automated scans alone is insufficient.

This document is an evidence reconciliation checkpoint, not a new semantic signoff, Phase 2 implementation, or declaration of completion.
