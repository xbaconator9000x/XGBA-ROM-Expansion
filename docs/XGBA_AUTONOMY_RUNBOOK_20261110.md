# XGBA autonomous product queue — 10 November 2026

**Purpose:** replace the repeatedly failing legacy Phase 1 Copilot comment dispatcher with a running, bounded sequence of *actual resource-expansion deliverables*, not further blanket hardware re-audits.

## Existing capability and prior work — reuse, do not repeat

- GBATEK establishes the GBA cartridge memory map. Normal ROM window is 32 MiB (repeated across three wait-state windows).
- The pinned native mGBA Matrix mapper implements 64 MiB GBA Video cartridge paging; XGBA's existing `tests/mgba_bank_boundary.c` already exercises a synthetic 64 MiB Matrix cartridge. These are **not missing work**.
- mGBA Matrix mapper is limited by its physical address mask and tiny banked aperture. It is not a general unlimited-capacity ROM. `mstan/gbarecomp` also has a Matrix model, but the repository is PolyForm Noncommercial, not an automatically permissible source-code donor.
- The unimplemented capability is a versioned **opt-in** external asset system with reliable identity, lifetime, and compatibility semantics.

## Operational implementation

- Target **existing draft PR #40** only, with its own experimental branch. No edits to legacy PR #27 or other work, and no direct writes to `main`.
- Three disjoint, ordered packages **R1 streaming sidecar**, **R2 deterministic pack builder**, and **R3 host staging bridge** are fixed in `tools/xgba_autonomous_product.py`. See PR #40's design document for concrete acceptance criteria and expected filenames.
- GitHub Actions runs every 30 minutes and on an authorised manual trigger. Concurrency group limits to one dispatcher. User-owned `XGBA_COPILOT_AGENT_PAT` makes the request to GitHub Agent Tasks API (Copilot Pro pilot tested successfully); `GITHUB_TOKEN` cannot call that API.
- A dedicated GitHub branch `xgba-autonomous-product-state` stores an atomic compare-and-swap ledger. Reservation is persisted **before** the single task POST to prevent uncertain retries.
- Refuse to dispatch when any other active Agent Task is reported in the repository, or if PR identity changes. No new tasks while a task is active.
- When Copilot reports `completed`, compare the PR's exact new head to the dispatched baseline, require both expected source + test files actually changed and present, require exact-head **XGBA opt-in resource prototype CI** success, and prohibit unexpected changed paths. Only then record `DELIVERED_AWAITING_INDEPENDENT_REVIEW` and advance automatically.
- A successful CI run **does not grant a semantic disposition**. Actual independent review remains separate. No merges, no source-pin changes or revisions of source-map gates.
- At most **three new tasks per UTC day**, finite three-package queue. No unbounded credit consumption. The user separately confirmed their $0 AI-credit overage budget; this code cannot query or enforce GitHub account billing. It stops at the daily/queue limits even if that GitHub budget changes.
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
hourly ChatGPT task `Continuous XGBA Phase 1` is **supervisory only**:
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
task queue, CAS ledger, finite three-package cap and $0-overage requirement remain.

**Fallback:** GitHub cron `23,53 * * * *` is best-effort, not a guaranteed
30-minute cadence. An hourly ChatGPT watchdog checks PR #40, current task,
exact-head checks and the latest GitHub dispatcher runs; it reports genuine
delays/failures and repairs bounded defects only under the pre-existing
no-direct-main / no-duplicate-dispatch / no-false-approval constraints. A green
workflow with an `AGENT_ACTIVE` or `WAIT_OTHER_AGENT` result is **not**
evidence that delivery finished. A stalled ledger must not be automatically
cleared just because a branch commit or green test appears.

**Terminal behaviour:** After R3, GitHub must record all R1/R2/R3 as
`DELIVERED_AWAITING_INDEPENDENT_REVIEW`, `next=3`, `current=null`.
The dispatcher then returns `QUEUE_DONE_AWAITING_REVIEW` and creates
**no additional paid-capable Agent Task**. The watchdog reports the transition
and requests independently reviewed integration before any additional
implementation queue is authorised. Host-side prototype tests do not prove a
playable expanded ROM or ordinary GBA cartridge compatibility.

## Success criteria

1. Exact-head PR checks pass with offline negative tests before deployment.
2. First production scheduled or push run creates ledger + at most one task on PR #40 (unless another active Agent Task is present).
3. Copilot writes real code and tests, passes exact-head product CI, and is acknowledged as delivered **not approved**.
4. A later scheduled run selects R2 without user intervention. Reconcile and repair anything that blocks; never simply call a green workflow progress.
5. After R3 delivery, the queue reports `QUEUE_DONE_AWAITING_REVIEW`. Review integration/compatibility and design next concrete package queue from test evidence. Do not claim an arbitrary-size ROM, original hardware compatibility or fully complete XGBA until independently demonstrated.

## Notes on expected costs

Autonomous Agent Tasks may use included Copilot Pro credits. They are **not necessarily zero-credit**, and this workflow does not itself read the user's spending cap. A missing/expired token or exceeded GitHub quota blocks the workflow without creating a fallback paid service. No other projects are touched.
