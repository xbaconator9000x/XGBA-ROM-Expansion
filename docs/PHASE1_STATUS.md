# Latest verified checkpoint: v2.6

[**Read the current Phase 1 v2.6 status and compiled ABI evidence**](PHASE1_STATUS_v26.md). The cumulative source and mapping work is preserved across v2.5 and earlier releases. **Phase 1 semantic signoff remains FAIL_INCOMPLETE.**

---

# Current Phase 1 checkpoint — v2.5

**Status: INCOMPLETE — no release-ready XGBA runtime.**

The actively maintained source-map checkpoint is [v2.5](PHASE1_STATUS_v25.md). Five immutable source repositories, both FireRed compiler variants and native mGBA/Porymap build evidence are preserved. All 14,834 pinned files are inventoried, 39,530 function-scope dossiers are generated, and the native ROM/save/graphics/bytecode limits are source linked. Automated dossiers are not semantic approvals. The fail-closed Phase 1 gate still requires independent file dispositions.

[Latest verified permanent archive — v2.4](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.4) · [v2.5 save/ABI status](PHASE1_STATUS_v25.md)

---

# Current status: v2.0

The latest verified semantic evidence and remaining completion requirements are in [PHASE1_STATUS_v20.md](PHASE1_STATUS_v20.md). Prior v1.8 and v1.5 sections below are historical. **Phase 1 is NOT complete.**

---

# Phase 1 checkpoint — v1.5 (2026-10-25)

**Decision: FAIL_INCOMPLETE. Phase 1 source mapping has not received independent semantic approval.**

## Verified GitHub Actions evidence
- [Successful 5-repo source audit, second-pass dossiers and mapping gate](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40159337299).
- All **14,834** tracked files from five pinned upstream Git revisions are inventoried.
- All **4,685** source/config files have been read and Git-blob SHA checked.
- **14,834** machine-generated, hash-pinned per-file dossiers; **0** independently approved file dispositions.
- **5,711** lexical candidate occurrences; **8,315** symbol candidates.
- **13,729** include syntax references: **8,676** single-path candidates, **62** ambiguous, **4,991** unresolved. Provisional unresolved classes: **2,384** standard library, **1,015** Qt, **230** generated, **155** platform/third-party, **698** local basename hypotheses, **509** unknown.
- Heuristic review queue: **338 P0**, **1,297 P1**, **8,658 P2**, **4,541 P3**. Priorities are not semantic signoffs.

## Source mapping register (v1.5)
- Original **11,024** mapping entries source-reconciled: **0 missing paths, 0 blob hash mismatches, 0 revision mismatches**.
- **4,315** novel source-line lexical candidates appended from the complete census, with original IDs untouched.
- **13,729** typed include-reference candidates appended as a separate dependency class.
- Combined **29,068** register records spanning **2,631** different files.
- 500-record checkpoints at **11,500–29,000**. New entries explicitly state candidate-only status.
- The 29,068 mapping register is a **candidate discovery and provenance index**, not 29,068 approved semantic findings.

## Source-backed constraints
See [new v1.5 contracts](CRITICAL_SOURCE_CONTRACTS_v15.md) for save-state identity, ROM remap sequencing, raw script bytecode execution, and FireRed save-block relocation/encryption.

## Validation
- GitHub Actions evidence pipeline: SUCCESS.
- Fail-closed Phase 1 mapping gate: FAIL_INCOMPLETE, **0/14,834** independent signoffs.
- Offline local integration tests: 11/11 PASS.
- Preserved v1.4 offline tests: 18/18 PASS.
- No XGBA emulator/ROM expansion patch or end-to-end runtime tests have been implemented.

## Persistence and next step
The reproducible pipeline is committed to this repository. The complete 11.5MB mapping workpack generated in ChatGPT must be copied to `imports/XGBA_Phase1_v1.5_Complete_Workpack.zip` for permanent GitHub persistence; the connected GitHub API cannot import a local binary attachment automatically. [Import workflow](../.github/workflows/import-workpack.yml) verifies each ZIP entry SHA256, the 29,068 record counts, and the non-completion status when the archive is uploaded.

Once imported, continue ranked semantic review, source/asset dependency proofs, versioned adapter contracts and independent per-file approvals. Phase 2 compilation/runtime/compatibility checks are a separate release gate.

Do not count initial source scans, guessed paths, or unsigned dossiers as completed semantic review.
