# Phase 1 v5 receipt live-check checkpoint — 2026-11-01

**Disposition: `BLOCKED`; no receipt was counted.** This records an actual v5 CLI run and the evidence independently available at the time. It is not a successful live validation, semantic approval, or change to the authoritative `FAIL_INCOMPLETE` gate.

## Exact inputs

- PR #2 adapter/validation head: `72c6179ed2e9e4b911d1da1d7af37b406512fc9b` (this checkpoint is a later documentation-only commit).
- PR #8 head: `3ee4b1117f2976b6ea41098f5456634da18a50f8`, checked out detached at `/tmp/xgba-validation/pr8`; the PR #8 history was fetched to complete ancestry checks.
- v5 adapter Git blob: `cb64da41dd7d28d305916b60ec5b8a93590bd92d`; SHA-256: `b3549391eacc173fdb1a04d8508c45c49f90f1ba10b542d5373fed4f2f2036b0`.
- PR #8 receipt register: Git blob `22f47d4e53954e133a6da117c247f25c158e8147`; SHA-256 `f5e681820ed9e5c9bae6b1eddbe2a5791fe75bf3b50997dfa2b65224f439aecf`.
- PR #8 protocol: Git blob `16382c1146a191f3027347644696b9444251303b`; SHA-256 `00bc511cfe46a527c5de66b4d6bba51b99684597b6e7ff788a26326b8c2346d2`.
- Pinned validator and triage: Git blobs `c68a11e0de846a12179cf71171b3c3a15fc65764` and `56eff6d4b5a6b1a566d5c5b00ca670bed219b4f8`.
- Original compressed dossier and queue: blobs `3b982876c7d810a827af8c80c7e5d9231fdaa327` and `52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268`; SHA-256 values `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609` and `c50498b751ecbe38d7a5939e06fa85cf4e62d529a943983710d4c5b9095d2eff`.
- Required upstream checkout: `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`.

The adapter verified the pinned PR #8 worktree files and archive hashes, loaded the original queue and dossier snapshot, checked all 14,834 dossier records, and accepted the four exact ordered receipt identities. Independently recomputed canonical body digests matched all four register values:

| Receipt source | Canonical SHA-256 |
| --- | --- |
| `include/mgba/internal/arm/debugger/cli-debugger.h` | `49924b5437aecfc88ebdf335fbd6fe05a68fa13987f61d87e0a7ee62809f0c64` |
| `include/mgba/internal/arm/debugger/memory-debugger.h` | `2d30b0f6d533f5091f0e0b58233032707c3fdb07b81984cc8aa85a5a6516cc53` |
| `src/arm/CMakeLists.txt` | `e410f88c79a6b3dfb2612f1228c6f7ae0bda83e4eb7d896fbc6221aa2903a0d0` |
| `include/mgba/internal/arm/isa-arm.h` | `d59ea911f09d5d5393b36a62d770159293672ab5f774b23c71fcd684e98e0ded` |

## Actual CLI result

Command:

```text
python3 tools/phase1_copilot_receipts_v5_adapter.py --pr8-root /tmp/xgba-validation/pr8 --source-root /tmp/xgba-validation/upstreams
```

Exit status: **2**.

Captured stdout:

```json
{"blocker": "Pinned upstream source checkout is unavailable; original source bytes cannot be verified.", "source": "mgba-emu/mgba:include/mgba/internal/arm/debugger/cli-debugger.h", "status": "BLOCKED"}
{"blocker": "Pinned upstream source checkout is unavailable; original source bytes cannot be verified.", "source": "mgba-emu/mgba:include/mgba/internal/arm/debugger/memory-debugger.h", "status": "BLOCKED"}
{"blocker": "Pinned upstream source checkout is unavailable; original source bytes cannot be verified.", "source": "mgba-emu/mgba:src/arm/CMakeLists.txt", "status": "BLOCKED"}
{"blocker": "Pinned upstream source checkout is unavailable; original source bytes cannot be verified.", "source": "mgba-emu/mgba:include/mgba/internal/arm/isa-arm.h", "status": "BLOCKED"}
```

`/tmp/xgba-validation/upstreams` and the repository's conventional `upstream/mgba` checkout were absent. The CLI therefore did not compare each receipt's source, dependencies, and license evidence against original mGBA Git objects and returned four `BLOCKED` results. It did not validate the live comment and Actions evidence through its own API client either. No `GITHUB_TOKEN` or `GH_TOKEN` was present; separate anonymous v5 API-client checks for the comment and exact-head Actions returned `Unable to retrieve complete GitHub API response`. These are missing-input/API-access blockers, not a passing adapter result or an identified validator defect.

## Independently observed GitHub evidence

- PR #8 Copilot comment [#6560888568](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/8#issuecomment-6560888568) is present in the PR conversation after receipt introduction. Its unquoted attestation markers name the fourth receipt digest above, introduction commit `3ee4b1117f2976b6ea41098f5456634da18a50f8`, evidence commit `be990407135c99de8113df81af7cd91d531a4fc2`, and `APPROVED`. The available conversation result reports user ID `198982749` and login `Copilot`; owner checkpoint [#6561500155](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/8#issuecomment-6561500155) records the individual REST identity fields. The v5 adapter itself could not fetch/authenticate that object in this run.
- PR #8 exact-head PR run [#41290048259](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41290048259), attempt 2, completed successfully on `3ee4b1117f2976b6ea41098f5456634da18a50f8`: 41/41 jobs and 326 returned steps completed successfully.
- PR #8 exact-head push census [#41290044590](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41290044590), attempt 2, completed successfully on the same SHA: census job `124902374464` succeeded. Its log records `FAIL_INCOMPLETE` and uploaded artifact `13090309660` (ZIP SHA-256 `ad461847dd1667e8a0069cd39d17304dab0b7d8e88c2bf1b555d5fbc6980f5ed`).
- PR #2 v5 workflow [#41308002333](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41308002333), attempt 2, completed successfully at the PR #2 head: jobs `124902450928` (v5), `124902451183` (v4), and `124902451271` (v1) all succeeded. The v5 job ran 12 synthetic positive/adversarial tests. These controls are not live receipt validation.
- No PR-triggered Actions run for PR #2 at this exact head was returned by the workflow-run query; the successful #41308002333 run is a push event.

The CI and comment observations above came from GitHub tools, not from a successful v5 live run. The fourth receipt remains **unvalidated and uncounted** until the v5 CLI runs with the exact pinned mGBA source checkout and obtains the required live GitHub comment/Actions responses. Historical external approval counts and the `FAIL_INCOMPLETE` gate are unchanged.
