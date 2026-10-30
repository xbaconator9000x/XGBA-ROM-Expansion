# Phase 1 independent reviewer handoff — Power Plant encounter scripts

**Status: NEEDS_EVIDENCE / NEEDS_REVIEW. No semantic disposition or approval is recorded by this handoff.**

## Reviewer eligibility and provenance

Prepared by the Copilot coding agent on the existing draft PR #8 branch. Copilot is **not eligible to count as a distinct external reviewer here**: this agent has authored work on the branch, and cannot supply an independent external identity or attestation under the Phase 1 protocol. No signed or attributed review receipt has been created. The authoritative gate remains `FAIL_INCOMPLETE`; approvals added: **0**.

## Bounded candidate for independent review

Start with the complete original pinned Power Plant map-script file and its static object-event binding. This is a deliberately small candidate unit, **not a claim that its semantic dependency closure is complete**.

| Evidence | Immutable identity |
| --- | --- |
| `pret/pokefirered:data/maps/PowerPlant/scripts.inc` | Commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; Git blob `ec48a37782877dbd07507bbe58964643c5444d06`; 121 lines / 3,645 bytes; SHA-256 `7558c5214a97c767aa1840d14fa15521e7f0993657ee19a3bb088b4202f6f192` |
| Original machine-dossier record | Packet index 200 in [`packet-0200-0299.json`](packet-0200-0299.json); dossier SHA-256 `1d85c59fc873c14749ebf16c2cb3162d780f6b5cc6b3c71c92404a7d476387fe`; machine state `MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION`; reviewer `null`; semantic signoff `false` |
| Static map binding | `pret/pokefirered:data/maps/PowerPlant/map.json`, same pinned commit; Git blob `38950b3a4980822bd4ea5cb6105e8f7b59d87926`; 5,065 bytes; SHA-256 `2a33bb77406ca5fefc99b9adc48ef640f4143d990e9b02c4ba2e96f17be0a8cb` |
| Existing analyst partial | [`remaining-p0-four-firered-powerplant-rocket-20261030.json`](remaining-p0-four-firered-powerplant-rocket-20261030.json), record `packet_index: 200`; this is an index and lead list, **not** a substitute for reading either full pinned file |

The original-packet integrity verifier was run locally and returned `P0_THIRD_MACHINE_DOSSIER_PASS records=100 original_inventory=14834 negatives=704 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE`. It rehashed the original machine-dossier inventory and packet identities; it does not verify semantics, licensing, compiled output, or runtime behavior. The two upstream source files were fetched at the immutable commit above; their Git blob IDs and byte-level SHA-256 values match the identities recorded here.

## Review history and deduplication

The existing PR #8 had **zero submitted reviews and zero inline review threads** in the live GitHub query used to prepare this handoff. The source machine record has no reviewer and no semantic signoff. No prior independent disposition was found for this item; analyst source notes and CI results are not reviews.

## Questions and evidence still required

The analyst packet lists the following edges; an independent reviewer must resolve them from complete pinned source and record any additional edges or counterexamples:

- `GetBattleOutcome` / `StartLegendaryBattle` dispatch and outcome semantics.
- `FLAG_SYS_SPECIAL_WILD_BATTLE` interactions with resume processing and map-object state.
- Save/read consumers and persistence semantics for the Zapdos and two Electrode completion flags.
- The `PowerPlant/map.json` references to `PowerPlant_EventScript_Zapdos`, `PowerPlant_EventScript_Electrode1`, and `PowerPlant_EventScript_Electrode2`; generated map-table, assembler/linker, and native event-consumer closure.
- Script command definitions and execution semantics for every command in the complete file, including shared labels and cleanup paths.
- Original asset/derivative licensing. The selected script has no per-file license notice; repository-level license identity is not per-file clearance.

The existing partial records source observations around lines 1–13, 17–24, 36–65, and 74–105, but those anchors are navigation aids only. The reviewer must independently inspect all 121 lines, inactive/error paths, and the complete dependency closure before making any disposition. No natural stock-gameplay, native save/restart, physical Flash, or emulator/runtime result is established by the packet or by this handoff.

## Instructions for the independent reviewer

1. Record a real reviewer identity and provenance, and explain why that reviewer is distinct from the PR author and this Copilot agent. Do not use Copilot or CI as the reviewer identity.
2. Independently re-fetch and hash the complete pinned source files; verify the original machine-dossier record and source blob identities rather than accepting this handoff's summaries.
3. Read the complete files and resolve the dependencies above. Separate source-proven behavior, inferred hazards, and executed evidence; document objections and negative/counterexample cases.
4. Record exact coverage, source revisions and blob hashes, evidence sources and hashes, licensing findings, runtime/build scope, unresolved questions, and a per-item verdict attributed to the eligible reviewer.
5. Until all required evidence and protocol conditions are met, retain `NEEDS_EVIDENCE` / `NEEDS_REVIEW`; do not issue approval or infer it from analyst work, packet verification, or passing CI.

Protocol: [`PHASE1_SYSTEM_BATCH_REVIEW_PROTOCOL_2026-10-27.md`](../PHASE1_SYSTEM_BATCH_REVIEW_PROTOCOL_2026-10-27.md). This handoff does not modify the shared review queue, candidate register, immutable pins, main, audit branch, or authoritative gate.
