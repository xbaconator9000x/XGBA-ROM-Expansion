# Phase 1 P0 — architecture-aware review scheduling versus lexical P0

**2026-10-26. State: SOURCE-AND-MACHINE-QUEUE TRIAGE ONLY, not semantic signoff.**

The authoritative pinned `semantic_review_queue.csv.gz` from [successful full census run 40213762053](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40213762053) contains **14,834 files**, including **338 heuristic P0**. We inspected the actual gzipped records, not only a dashboard summary.

## Measured P0 category mismatch

| Repository | Original lexical P0 | Relevant observation |
| --- | ---: | --- |
| FireRed | 205 | **163** P0 files are individual `data/maps/*/scripts.inc` gameplay script fixtures |
| mGBA | 99 | Includes **10** Game Boy-only (`/gb/`) source files, not all GBA memory-banking architecture |
| Porymap | 25 | Collision source `src/core/block.cpp` and `blockdata.cpp` rank **P2**, not P0 |
| Poryscript | 9 | Emitter and parser paths flagged |
| agbcc | **0** | ARM/Thumb multilib configuration `gcc_arm/config/arm/t-arm-elf` ranks **P3** |

The FireRed native linker `ld_script.ld` also ranks **P3** despite establishing the 32 MiB ROM and 256/32 KiB RAM regions. These findings demonstrate that lexical frequency is not sufficient to schedule architecture signoff.

**This does not mean all 163 gameplay scripts or GB code are irrelevant.** They remain P0 in the original queue and must be dispositioned. The problem is the order in which to investigate architecture dependencies.

## Additive review-order procedure

The exact-source [curated 29-file high-risk cross-repository interpretation register](../semantic-snapshots/curated/p0_semantic_review_candidates_2026-10-26.json) supplies evidence-backed semantic roles; [CI #40214265141](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40214265141) verified all 29 Git blob identities and five false-signoff mutations.

`tools/phase1_architecture_review_priorities.py` reads the original machine queue (not a guessed set of files), verifies it includes 14,834 unique records and 338 original P0 entries, checks all curated source Git SHA identities match, and creates a *second* ordered queue. It emits machine evidence into `audit-output/architecture_semantic_review_queue.csv.gz` and `audit-output/architecture_semantic_review_priority_summary.json`.

The additive tiers have explicit meanings:
- `A0_PINNED_CROSS_SOURCE_CONTRACT_OWNER`: curated 29 source-interpreted files, whatever their lexical priority. **Still not independently approved.**
- `A1_ARCHITECTURE_CRITICAL_P0`: remaining P0 source files in FireRed native engine, mGBA ARM/GBA, Porymap map model, Poryscript parser/emitter.
- `A2_OTHER_P0`: other P0 files that require individual review but have less direct mapped architecture evidence.
- `A3_P0_GAMEPLAY_SCRIPT_FIXTURE`: all 163 FireRed map script examples. Original priority still recorded as P0.
- `A4/A5/A6`: files in original P1/P2/P3, all retained with original source metadata and status.

There is **no source-file deletion, no P0 demotion in the original queue, no machine conversion to approved**, and no change to `phase1_mapping_gate.json`. The review scheduler is *order-of-work metadata*, not a compatibility decision or all-file proof.

## Acceptance checks

1. The generated secondary queue must contain **exactly the same 14,834 source rows and Git SHA identifiers** as the baseline, once each.
2. Exactly 338 original P0 items must be preserved; exactly 163 matched map-script fixtures must stay present in tier A3.
3. Exactly 29 source-pinned curated candidates should appear in A0 regardless of original lexical rank.
4. Every original machine-review status and its priority must remain unchanged on the secondary record.
5. The source census and permanent archive workflows must both be verified PASS; do not claim proof while pending.
6. Independent whole-file source semantics and runtime interoperability must still be reviewed; this sorting procedure does not complete Phase 1.

**Evidence workflow:** [Phase 1 pinned census run #40214802383](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40214802383), pending at writing.

**Phase 1 remains `FAIL_INCOMPLETE`.**
