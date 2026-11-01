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
| Pinned native assertions executed (follow-up run) | 34 passed; 4 hazards observed |
| Distribution clearance | `NOT_ASSESSED` |

The six source-order contracts are not whole-file semantic maps. At the time of this original pilot snapshot, the native fixture had not been compiled or executed. The source-index catalog likewise labels its test-source inventory as present but not executed and license-file presence as not distribution clearance. The later exact-head native run is recorded below and in [the per-file evidence matrix](PHASE1_MGBA_NATIVE_SEMANTIC_MATRIX_20261101.json); neither that run nor the compiler analysis is a semantic signoff.

The behavioral evidence schema `xgba.phase1.behavioral_congruence_evidence.v2` is deliberately separate from exact-byte v1 and supersedes the pilot's unactivated v1 evidence shape. Its structural validator requires whole-file line coverage and claim IDs; source-backed semantic statements and specification references; complete dependency and consumer closure; positive and negative test coverage for the claims on the exact source revision with executed successful Actions jobs; risk-specific negative controls; license clearance; and no unresolved objections or contradictions. Each referenced artifact and Actions run must be independently reverified. Synthetic positive/negative unit fixtures exercise those checks only; they are not accepted by the live CLI, produce no receipt, and are excluded from all counts.

The candidate reason codes include:

- `NO_WHOLE_FILE_SEMANTIC_MAP`
- `LEXICAL_INCLUDE_CANDIDATES_ARE_NOT_DEPENDENCY_CLOSURE`
- `PINNED_POSITIVE_AND_NEGATIVE_TESTS_NOT_EXECUTED`
- `LICENSE_DISTRIBUTION_CLEARANCE_NOT_ASSESSED`
- `WHOLE_FILE_DEPENDENCY_AND_CONSUMER_SCOPE_NOT_ESTABLISHED`
- `SUBSTANTIVE_ROM_BOUNDARY_OBJECTIONS_REMAIN_OPEN`
- `UNRESOLVED_LITERAL_INCLUDE_CANDIDATE` for `src/gba/serialize.c`

The open native-ROM obligations include backing-file bounds and short-read handling during Matrix remaps, instruction prefetch invalidation and bank-switch arbitration, DMA/EEPROM/e-Reader interactions, and save-state backing identity. The source-anchored fixture describes probes for some cases but does not close these risks.

## Source/build closure and per-file blockers

The evaluator now emits, for each of the six candidates, the pinned source SHA-256 and byte count, the canonical original machine-dossier SHA-256, both independently pinned compressed-dossier archive hashes, CMake source-list membership, any source-contract rows with line spans and anchors, MPL-2.0 notice evidence, and applicable risk obligations. It explicitly reports that source bytes were not reopened in this reconciliation run. The two source-contract files (`src/gba/gba.c` and `src/gba/memory.c`) contribute six order contracts total; the remaining four files have no such contract rows. These partial rows are not whole-file semantic dispositions.

At the pinned mGBA revision, `src/arm/CMakeLists.txt` (`a86f0bea1f38aeb88222fb5b532b4ea9e256767f`) lists `arm.c` in the ARM source set, and `src/gba/CMakeLists.txt` (`71ab7bbb199ad95422e35ded5774c06a1b2e7c5c`) lists the other five pilot files in the GBA source set. Its `test/core.c` entry (`25b8f3ce30b59c3ecde8ecb377ea80964888b0ae`) covers core creation/platform/reset/null-ROM behavior, not these Matrix boundary risks. The local native-probe CMake file pins the expected layout at `upstream/mgba`, sets `BUILD_TEST=OFF`, and stops at configuration if `src/gba/cart/matrix.c` is absent. These CMake lists establish build-target membership, not resolved compiler/preprocessor, runtime, or consumer closure.

**Local native build result: BLOCKED, not PASS.** This checkout has no `upstream/mgba/src/gba/cart/matrix.c` and no configured boundary-test build directory. CMake and a C compiler are available, but the clone-capable local runner was not invoked. The separate PR #13 native Qt6 SaveConverter job was only an execution precedent; it did not test the Matrix/ARM boundary fixture.

The existing `.github/workflows/compiled-mgba-semantics.yml` runs the pinned Matrix/ARM harness on relevant PR branch pushes. It uses its detached mGBA source pin and build, then `tests/run_pinned_mgba_boundary.sh` verifies all six pilot source Git blobs and the boundary test source blob/SHA-256 before execution. The C fixture emits a `CASE` row with exit code for each assertion and a distinct `CASE_OBSERVATION` row for each observed native hazard. `tools/verify_phase1_mgba_boundary_evidence.py` rechecks source/test identities and result/log records, and binds the evidence to the exact run, job, attempt, PR #2 head, and successful completed build/test steps. The resulting ingestion is explicitly `NATIVE_EVIDENCE_ONLY`; it cannot produce semantic dispositions or a Phase 1 pass. Workflow permissions are limited to `contents: read` and `actions: read`.

### Exact-head native and compiler evidence follow-up

The exact-head workflow completed successfully on PR #2 head `a0b5cfa80ac0815644b46f8cc6db4108769eeabd`: run [#41271029098, attempt 2](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41271029098), job `124754053197` (`compile-pinned-mgba`). GitHub reports the run and job `completed/success`; attempt 1 was `action_required` and is not the result reported here. Artifact `13070546254` has SHA-256 `25c4d0910fce915a6d057142cc297ff718b21e47186b41880d2a3d4c50a52371`. The pinned test source SHA-256 is `eaccce9a4b8622d19c6db62ec4f2cd469e00f0ccf3ed056264f64aa66cdd54fa`; runtime log SHA-256 is `20a78eef24c6b5194c05610d6caf4abd227272b54fe34ff6906ef4d028cd66ba`.

The original mGBA source at pin `fd9dc5c2cbf234365068855851107e762fc6211b` compiled 173/173 configured translation units (168 C, 5 C++); the compiler selected 364 pinned headers across 3,126 transitive include edges. The analysis produced 1,345 code-symbol candidate edges and 58 data/other candidate edges. It did **not** establish a complete consumer or dependency closure: its `nm`-derived CSV omits undefined symbol references without an in-archive provider, does not resolve final frontend/platform links, and does not prove runtime calls or callback/data-flow paths. Compiler counts are configuration-specific, not whole-repository coverage.

The native fixture passed 34 assertions with zero assertion failures and observed four upstream hazards: stale instruction prefetch after remap, warning-only ROM CRC mismatch during state restore, an unverified changed external bank payload, and a Matrix physical range past the backing-file end. These are observations of pinned mGBA behavior, not safe XGBA behavior or semantic controls. The fixture did not test Matrix short reads or combined Matrix/DMA/peripheral arbitration. Do not rerun or relabel the 34 assertions as safety proofs.

| Pinned source | Original dossier SHA-256 | Compiler-selected header rows / unique headers | Symbol candidate rows | Source contract rows | Relevant native evidence | Remaining blocker |
| --- | --- | ---: | ---: | --- | --- | --- |
| `src/arm/arm.c` | `37c2acf57fc04d0327426d88d01b3353f46868be77fa73f3fa633fcc0a267934` | 9 / 8 | 20 | none | stale prefetch observed | prove invalidation and active-region coherence |
| `src/gba/cart/matrix.c` | `8998fbe6e0afc9b9a566c1891055f7526949b728356c125504d163eab97529aa` | 44 / 44 | 7 | none | out-of-backing-range remap accepted | backing bounds, failed seek/read, short-read behavior |
| `src/gba/dma.c` | `2840c84bd7cb1f3c78c6947820a42d45042134e12ba005d27ed55b65822522fa` | 44 / 44 | 24 | none | EEPROM DMA tests passed | no combined Matrix/DMA/peripheral arbitration case |
| `src/gba/gba.c` | `d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056` | 45 / 44 | 102 | 5 partial rows (`NOT_RUN`) | load/restore paths exercised as fixture behavior | partial source-order assertions are not a whole-file map |
| `src/gba/memory.c` | `4b18ab8b7b5f947457093503c6c085e0ba6677f321255d140720cb2965b07f54` | 50 / 50 | 128 | 1 partial row (`NOT_RUN`) | stale prefetch observed | complete memory/DMA/Matrix consumer closure |
| `src/gba/serialize.c` | `0d42ee41e8db7c86bddca22c14889a251ead70cb0c6dd77bd2206f8fc4bd0e47` | 47 / 47 | 70 | none | CRC warning and changed backing payload observed | establish backing identity and reject incompatible restore |

Per-file source blobs, source SHA-256 values, dossier digests, canonical per-file compiler-row digests, evidence limits, and native case IDs are recorded in `PHASE1_MGBA_NATIVE_SEMANTIC_MATRIX_20261101.json`. The source-order rows remain six partial contracts across only `gba.c` and `memory.c`; all are marked `NOT_RUN`.

### Scoped MPL-2.0 assessment

At the pinned mGBA revision, `LICENSE` is MPL-2.0 (Git blob `14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e`), and the inspected Matrix source carries the MPL-2.0 source notice. At a high level, MPL-2.0 §§3.1–3.2 require covered source-form distributions and covered modifications to remain available under MPL terms, notice of the license and reasonable access to corresponding source for covered executable distributions; §3.3 allows larger works under chosen terms while preserving MPL obligations for covered software; §3.4 protects source notices. This is a scoped inventory of obligations, **not** legal advice, compatibility clearance, or an assessment of this project's proposed distribution. `license_distribution_clearance` remains `NOT_ASSESSED`.

The exact native/compiler evidence therefore changes no disposition: all six pilot files remain `NEEDS_REVIEW`, `UPSTREAM_VERIFIED/PASSED=0`, `COPILOT_REVIEWED/PASSED=0`, and legacy external approvals remain `0/338` P0 and `0/14,834` total. The historical gate remains `FAIL_INCOMPLETE`.

The seven named risk controls are required by the behavioral evidence validator. A control must identify the exact expected case and outcome, the matching immutable source blob/SHA-256 set, an executed negative test, a SHA-256 result, and reverified test-source references; missing, duplicate, unknown, malformed, mismatched-source, or non-executed controls block the evidence. The unit tests below use only synthetic records and never enter the CLI register or counters. The live report still marks all applicable obligations unresolved:

| Risk/control | Source and fixture evidence | Current result |
| --- | --- | --- |
| Matrix physical backing range | `src/gba/cart/matrix.c`; observation `native_matrix_accepts_physical_range_past_end` | Native observation confirms the gap; does not prove a safe rejection control |
| Matrix short read | `_remapMatrix` does not check VFile seek/read results; no short-read fixture case | Control absent; behavior remains untested |
| ARM/Thumb prefetch invalidation | `src/arm/arm.c`, `src/gba/memory.c`; observation `native_remap_leaves_prefetch_stale_until_refetch` | Stale-prefetch behavior observed; safe invalidation remains unproved |
| DMA/peripheral interaction | `src/gba/dma.c`, `src/gba/cart/matrix.c`, `src/gba/memory.c`; EEPROM DMA cases passed | EEPROM path is separate from Matrix/DMA arbitration; combined case absent |
| Save-state backing identity | `src/gba/serialize.c`, `src/gba/cart/matrix.c`; CRC warning and changed external payload observations | Hazardous restore behavior observed; backing-identity rejection remains unproved |
| Dependency/consumer closure | 173 configured units, compiler-selected headers, and object-symbol candidates | Complete dependency/consumer closure not established; unresolved external references are not enumerated |
| Distribution/license clearance | Pinned mGBA `LICENSE` blob `14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e` identifies MPL-2.0 | Scoped obligations documented; project distribution and compatibility clearance remain `NOT_ASSESSED` |

Per-file dispositions remain `NEEDS_REVIEW` (six); none is `UPSTREAM_VERIFIED/PASSED`. Candidate rows carry the unresolved risk IDs and source-contract evidence; the pilot does not promote source inspection, test intentions, build metadata, or synthetic controls to a real receipt. The historical completion gate and legacy external-approval counts remain unchanged at `FAIL_INCOMPLETE`, `0/338` P0 and `0/14,834` total.

## Validation and counters

Run the pilot unit fixtures with:

```sh
python3 -m unittest discover -s tests -p 'test_phase1_upstream_congruence_pilot_v1.py'
```

The CLI reports `FAIL_INCOMPLETE`, `legacy_external_independent_approved=0`, `legacy_p0_external_independent_approved=0`, `behavioral_congruence_passed_count=0`, and six files remaining in this pilot. New synthetic negative-control tests validate only fail-closed evaluator behavior; they are not mGBA test results. The pilot has no effect on the legacy `0/338` P0 or `0/14,834` external approval metrics. Any future prospective semantic total must union only separately validated dispositions by unique pinned identity; it must never add to or reinterpret the legacy external-review metric.
