# XGBA autonomous product queue — 10 November 2026

**Purpose:** replace the repeatedly failing legacy Phase 1 Copilot comment dispatcher with a running, bounded sequence of *actual resource-expansion deliverables*, not further blanket hardware re-audits.

## Existing capability and prior work — reuse, do not repeat

- GBATEK establishes the GBA cartridge memory map. Normal ROM window is 32 MiB (repeated across three wait-state windows).
- The pinned native mGBA Matrix mapper implements 64 MiB GBA Video cartridge paging; XGBA's existing `tests/mgba_bank_boundary.c` already exercises a synthetic 64 MiB Matrix cartridge. These are **not missing work**.
- mGBA Matrix mapper is limited by its physical address mask and tiny banked aperture. It is not a general unlimited-capacity ROM. `mstan/gbarecomp` also has a Matrix model, but the repository is PolyForm Noncommercial, not an automatically permissible source-code donor.
- The unimplemented capability is a versioned **opt-in** external asset system with reliable identity, lifetime, and compatibility semantics.

## Operational implementation

- Target **existing draft PR #40** only, with its own experimental branch. No edits to legacy PR #27 or other work, and no direct writes to `main`.
- The original three packages **R1 streaming sidecar**, **R2 deterministic pack builder**, and **R3 host staging bridge** are delivered, awaiting review. The queue was expanded to a finite **R4-R6 FireRed/mGBA native integration cycle** on 10 November 2026, appended in `tools/xgba_autonomous_product.py` without rewriting historical delivery receipts. See PR #40's design document for concrete acceptance criteria and expected filenames.
- GitHub Actions runs every 30 minutes and on an authorised manual trigger. Concurrency group limits to one dispatcher. An Actions-secret `XGBA_COPILOT_AGENT_PAT` makes the request to GitHub Agent Tasks API (Copilot Pro pilot tested successfully); `GITHUB_TOKEN` cannot call that API.
- A dedicated GitHub branch `xgba-autonomous-product-state` stores an atomic compare-and-swap ledger. Reservation is persisted **before** the single task POST to prevent uncertain retries.
- Refuse to dispatch when any other active Agent Task is reported in the repository, or if PR identity changes. No new tasks while a task is active.
- When Copilot reports `completed`, compare the PR's exact new head to the dispatched baseline, require both expected source + test files actually changed and present, require exact-head **XGBA opt-in resource prototype CI** success, and prohibit unexpected changed paths. Only then record `DELIVERED_AWAITING_INDEPENDENT_REVIEW` and advance automatically.
- A successful CI run **does not grant a semantic disposition**. Actual independent review remains separate. No merges, no source-pin changes or revisions of source-map gates.
- At most **three new tasks per UTC day**, finite six-package queue (including the preserved completed first three). The dispatcher cannot inspect account billing limits; it must stop on quota and enforce its explicit task/day limits.
- Failed, cancelled, timed-out, unknown, mismatched, no-commit or unrelated-path work **blocks** automatic advancement and reports a specific reason; never counts as completed. A `RESERVED` outcome means manual reconciliation is required before another POST.
- This is real persistent autonomy **within a specific validated queue**, not perpetual invention of unrelated tasks.

## Entry points and links

- GitHub workflow: `.github/workflows/xgba-autonomous-product.yml`.
- Dispatcher and tests: `tools/xgba_autonomous_product.py`, `tests/test_xgba_autonomous_product.py`.
- PR #40: `https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/40`.
- Existing pilot PR #38: `https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/38`.
- Discontinued legacy scheduled workflow: `.github/workflows/phase1-copilot-chain.yml` is retained as manual-only to avoid duplicate dispatch, repeated syntax failures, and wasted runners.

## Watchdog congruence and event-driven reconciliation (10 November 2026)

**Single authority for paid-capable dispatch:** the default-branch GitHub Actions job
`XGBA autonomous product dispatcher (bounded)`. It is the only service allowed
to POST GitHub Copilot Agent Tasks and atomically maintain
`xgba-autonomous-product-state:.xgba-autonomy/ledger.json`. The pre-existing
external status monitors are **supervisory only**:
it must read this same ledger/PR/CI, never independently POST another Agent Task,
create a duplicate automation, restart the 14,834-file census, or override
semantic approval counts.

**Primary wakeups:** in addition to schedule and manual dispatch, the GitHub
dispatcher now listens to `workflow_run: completed` for
`XGBA opt-in resource prototype CI`. Only success events from this same repo,
the exact PR #40 head branch, and `push`/`pull_request` sources qualify.
The default-branch dispatcher separately re-reads PR #40 and requires the CI
event's commit SHA to equal its latest head before accessing tasks or ledger.
`workflow_run` never checks out or executes untrusted PR code, downloads PR
artifacts, or evaluates PR-authored scripts. Existing single-run concurrency,
task queue, CAS ledger and finite three-package dispatch cap remain.

**Fallback:** GitHub cron `23,53 * * * *` is best-effort, not a guaranteed
30-minute cadence. An external status monitor may check PR #40, current task,
exact-head checks and the latest GitHub dispatcher runs; it reports genuine
delays/failures and repairs bounded defects only under the pre-existing
no-direct-main / no-duplicate-dispatch / no-false-approval constraints. A green
workflow with an `AGENT_ACTIVE` or `WAIT_OTHER_AGENT` result is **not**
evidence that delivery finished. A stalled ledger must not be automatically
cleared just because a branch commit or green test appears.

**Terminal behaviour:** At the original R3 checkpoint, GitHub recorded all R1/R2/R3 as
`DELIVERED_AWAITING_INDEPENDENT_REVIEW`, `next=3`, `current=null`.
The dispatcher returned `QUEUE_DONE_AWAITING_REVIEW` with no new paid-capable task. That previous state is preserved in history. The later scoped integration priority extended the queue through R4–R6. The dispatcher now advances only into that separately defined finite scope, stops again at R6, and still never grants semantic approvals. Host-side prototype tests do not prove a
playable expanded ROM or ordinary GBA cartridge compatibility.

## Revised priority and historical estimate — 10 November 2026

The full 14,834-file census and independent semantic mapping gate remain historical
and must not be misrepresented as complete, but **they are no longer a prerequisite**
for the first working expanded FireRed prototype. Reuse pinned GBA documentation,
pret/pokefirered symbol/asset semantics, mGBA Matrix and Hex Maniac Advance pointer
formats. Only investigate the precise pointer/retention paths that our actual
integration touches. No 14,834-file re-review assignments.

The live implementation target is STILL draft PR #40; the finite additional
packages are **R4 FireRed native adapter**, **R5 mGBA native opt-in provider**,
and **R6 actual compiled FireRed+mGBA smoke test with an external resource above
32 MiB**. Required source and test files and fail-closed native acceptance are
specified in `docs/XGBA_FIRERED_INTEGRATION_PRIORITY_20261110.md` on PR #40.
This does not authorize merging that draft PR or rewriting upstream projects.
Do not call R4/R5 complete without actual pinned source compile + native tests,
or R6 complete without actual executed emulator and game evidence.

**Estimate for first playable expanded FireRed demonstration: ~25%, with
material uncertainty.** Weighted scope: hardware/decomp pointer baseline 10%
(existing reference), host-side prototype 20% (15 credited pending review),
native FireRed integration 20%, native mGBA integration 20%, first working
game demonstration 20%, validation 10%. This is not an elapsed-time forecast
and is **not** a percent of the full reusable GBA/Android/editor platform.
No unverifiable completion percentages or automatic increments based solely on
a green workflow.

Daily dispatch cap (3), CAS reservation, single dispatcher, automatic CI
exact-head verification, old R1-R3 receipts, and
independent semantic approval 0 all remain unchanged.

## Success criteria

1. Exact-head PR checks pass with offline negative tests before deployment.
2. First production scheduled or push run creates ledger + at most one task on PR #40 (unless another active Agent Task is present).
3. Copilot writes real code and tests, passes exact-head product CI, and is acknowledged as delivered **not approved**.
4. A later scheduled run selects R2 without user intervention. Reconcile and repair anything that blocks; never simply call a green workflow progress.
5. After the original R3 delivery, the queue reported `QUEUE_DONE_AWAITING_REVIEW`. After the explicitly authorised extension cycle, the queue must stop again at R6 and deliver native FireRed/mGBA test evidence, not mock code. Do not claim an arbitrary-size ROM, original hardware compatibility or fully complete XGBA until independently demonstrated.

## Notes on expected costs

Agent Tasks consume platform quota according to current service terms. The workflow cannot read billing permissions or balances. A missing/expired token or exceeded GitHub quota blocks the workflow without creating a fallback paid service.
