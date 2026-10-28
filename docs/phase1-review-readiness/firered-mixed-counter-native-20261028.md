# Phase 1 — native mixed-counter save-loader physical-slot experiment (2026-10-28)

**New experiment awaiting exact-head CI. All gates FAIL_INCOMPLETE; independent approvals 0.**

## Source-grounded dependency and scope

- FireRed pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; `src/save.c` Git blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`, `include/save.h` Git blob `87fb9b615b434b58823d15688056695acda9feab`.
- Native execution uses pinned agbcc `da598c1d918402c42c0c0d7128ba14567f3175e9` and mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`, with actual ELF-derived addresses for `LoadGameSave`, `GetSaveValidStatus`, `CopySaveSlotData`, `gSaveCounter`, `gSaveFileStatus` and `gSaveBlock2Ptr`.
- `GetSaveValidStatus` checks signature, per-sector checksum and coverage of all 14 sector IDs. For each physical slot it overwrites the candidate slot counter on each valid sector; it does not require a unanimous counter across sectors. `CopySaveSlotData` selects physical slot from `gSaveCounter % 2` and copies valid sectors without checking their counter against that selected counter.
- Prior native `mixed_counters` fixture (13 counter1 sectors + final counter2 in physical slot1) observed status1/counter2/slot0 marker A5. **Do not rerun this green case as a new finding.**

## Three additional native cases

All fixtures are explicitly synthetic, checksum-valid and contain 14 unique sector IDs in each of two physical slots. Physical slot0 has counter0 and marker A5. Physical slot1 has marker 5A and the following sector-counter profiles:

| New case | First 13 physical slot1 sectors | Last sector | Expected selected counter | Expected loaded marker |
|---|---:|---:|---:|---:|
| `mixed_counter_tail0` | 1 | 0 | 0 | A5 (slot0) |
| `mixed_counter_tail1` | 2 | 1 | 1 | 5A (slot1) |
| `mixed_counter_tail3` | 1 | 3 | 3 | 5A (slot1) |

The new native runner checks source Git blobs and function anchors, fixture metadata/checksum/signature/ID, actual compiled loader and copy entry hits, status/counter, observed relocated SaveBlock2 marker, and byte-identical physical Flash before/after loading. Fifteen offline fixture mutations and twelve trace mutations must be rejected, not counted as emulator results.

## Interpretation and reviewer questions

A passing run would demonstrate that the **last checksum-valid sector's counter**, rather than a consensus of all 14, can determine both reported save counter and physical slot selection. It would not prove that normal FireRed saves produce these mixed metadata combinations, that arbitrary malformed sectors are safe, or that physical power-loss persistence is guaranteed.

Reviewers should assess whether counter unanimity is required by downstream consumers; whether rotation or interrupted-write order can produce comparable states; and whether additional native memory-safety instrumentation is needed for malformed IDs or partial sectors. This dossier is **partial subsystem evidence**, not a complete-file disposition or independent approval.
