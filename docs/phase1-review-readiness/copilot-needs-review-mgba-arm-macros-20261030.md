# mGBA ARM load/store macros — NEEDS_REVIEW

**Disposition:** NEEDS_REVIEW. This is an attributed source-inspection checkpoint, not a semantic approval or receipt. No approval was added to the register or gate.

**Reviewer/provenance:** Copilot agent, acting under the user-authorized Phase 1 reviewer policy. The existing analyst note for this item, `remaining-p0-eight-interop-20261029.json`, was authored by `xbaconator9000x` in commit `120e7d044e3c5a4ead8a1fc578869bce29f97edf`; it is a partial handoff, not a complete review. This Copilot checkpoint is not used as independent non-Copilot evidence.

## Immutable evidence checked

- Original machine dossier identity: `mgba-emu/mgba`, `include/mgba/internal/arm/macros.h`, pin `fd9dc5c2cbf234365068855851107e762fc6211b`, Git blob `4832f054611044e63f1e2393fe4072f48004545a`, 484 bytes, SHA-256 `196d6bf1210d223dd58930908dcf5d538a7111fe93e0a0b36b45721cd93dbad9`.
- Original dossier payload was rehashed from `semantic-snapshots/current/candidate_review_dossiers.jsonl.gz` using the repository's `checked_dossiers` verifier: SHA-256 `6508e54c65f1b871f5998bb17dbf6204a73e9428e4ff57734e50e0d1e4dbf558`. Its machine assessment has no semantic signoff or reviewer.
- Complete pinned `include/mgba-util/common.h`: Git blob `923e93086adfa09c9a55fcc2f0f6fa4d560e5888`, 12,589 bytes, SHA-256 `ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f`.
- Complete pinned `include/mgba-util/dllexports.h`: Git blob `a44480df6ec26821b8616650b2575ba794848eca`, 523 bytes, SHA-256 `96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4`.
- Pinned `LICENSE`: Git blob `14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e`, 16,726 bytes, SHA-256 `fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85`. The source headers carry MPL-2.0 notices. This identifies the upstream license and notice; it is not a legal clearance of any larger distribution.

The source bytes were retrieved from the exact public upstream commit and their Git blob IDs and SHA-256 values recomputed. The machine dossier's canonical payload digest was independently recomputed; the machine snapshot remains triage evidence, not a semantic finding.

## Source observations

The full 18-line `macros.h` includes `mgba-util/common.h` (line 9) and aliases the generic 16/32/64-bit `LOAD` and `STORE` names to their `LE` forms (lines 11–16). In `common.h`, little-endian hosts use typed pointer dereferences for these operations (lines 235–240); this header does not add an alignment check or bytewise fallback. Big-endian builds select byte swapping or PowerPC byte-reverse instructions for little-endian operations, while unsupported big-endian targets reach an explicit `#error` (lines 146–232). These are source-level observations only: they do not establish that every caller supplies aligned addresses or that every supported compiler/host combination behaves safely.

`common.h` includes `dllexports.h` and platform/standard headers. The pinned root CMake file selects C11 and adds the ARM and GBA source directories (lines 25 and 846–850); `src/arm/CMakeLists.txt` and `src/gba/CMakeLists.txt` list their implementation files. A pinned `src/gba/memory.c` caller masks a 32-bit BIOS offset with `-4` (line 386), and `src/gba/cart/ereader.c` masks a 16-bit offset with `0xFE` (line 266). These examples do not prove alignment for all call sites.

## Remaining evidence and objections

- **Caller/dependency closure is not reconciled.** The original machine dossier records 18 incoming include candidates and one outgoing `common.h` candidate. The supplied checkpoint describes 16 incoming candidates and an unresolved edge. GitHub code search results plus pinned-file fetches showed multiple direct and transitive macro users, but that search is not an exhaustive source-tree scan at the pinned revision. The count and full pinned caller list therefore remain unresolved.
- **Alignment and endian behavior remain unverified across all callers and supported build targets.** No pinned cross-host native build, alignment/undefined-behavior test, or runtime comparison was run. No runtime, save, or physical-device behavior is claimed.
- **Independent substantive evidence remains incomplete.** The non-Copilot analyst note is explicitly partial and records whole-file coverage as false. It does not resolve the caller inventory or the alignment/build objections. This Copilot note cannot stand in for independently authored evidence.
- **Exact-head evidence is missing.** At the time of this checkpoint, the current PR check was permission-gated (`action_required`, zero jobs), so no exact-head success is asserted.

Keep this item at NEEDS_REVIEW. Do not create a receipt, count an approval, infer semantic signoff from CI, or change the authoritative gate on the basis of this checkpoint.
