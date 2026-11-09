# XGBA Phase 1 — Copilot Pro Agent Tasks safe pilot (9 Nov 2026)

**Implementation stage: isolated draft branch; not deployed on \`main\`.**
This is a deliberately **single-task pilot**, not a claim that continuous
autonomous Phase 1 review or a working ROM expansion is complete.

## Verified GitHub functionality (not hypothetical)

- GitHub announced Agent Tasks API access for Copilot Pro on 4 June 2026:
  https://github.blog/changelog/2026-06-04-agent-tasks-rest-api-now-available-for-copilot-pro-pro-and-max/
- Official API instructions: https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-via-the-api
- REST endpoint and schema:
  https://docs.github.com/en/rest/agent-tasks/agent-tasks
- \`GET /agents/repos/{owner}/{repo}/tasks\` (read-only)
- \`POST /agents/repos/{owner}/{repo}/tasks\` supports \`base_ref\`, \`head_ref\`
  for existing open PR context, and \`create_pull_request: false\`. That
  is how this pilot targets existing **draft PR #27** without spawning a new PR.

**Documentation discrepancy:** the June 2026 release explicitly includes
Pro, while an API reference page may still say Business/Enterprise for task
creation. Read-only access does **not** prove POST permission. The first POST
must remain a deliberate, strictly controlled experiment.

## Scope and protections

- Repository: **xbaconator9000x/XGBA-ROM-Expansion** only.
- Existing draft PR: **#27**.
- Head: \`phase1/porymap-full-qt-project-roundtrip-20261028\`.
- Base: \`phase1/porymap-qt-writer-failure-boundary-20261027\`.
- Maximum **one** new Agent Task. The pilot rejects any active task in this
  repository and refuses to dispatch again once a ledger exists.
- Exact open/draft PR branch identity and SHA checked both before and after
  the reservation. PR head changes block dispatch.
- Persistent reservation is written **before** the billable task request to
  \`phase1-agent-pilot-state:.phase1-agent-pilot/ledger.json\`.
- Ambiguous network errors, 403, state conflicts, missing receipts, head
  changes or token issues **stop**. A reservation is never silently reset.
- \`inspect\` can mark a completed task \`AWAITING_REVIEW\`, never \`APPROVED\`.
  Semantic signoff and the authoritative Phase 1 gate remain unchanged.
- No schedule, no recursive workflow trigger, no automatic merge, no
  installation of new PRs, and no use of other repositories.
- The existing \`phase1-copilot-chain.yml\` workflow is **not** replaced by
  this branch. When promoting the pilot, separately disable/reconcile that
  legacy dispatcher to prevent two dispatchers owning the same PR.

## Authentication and cost: a real operational prerequisite

The Agent Tasks API requires **user-to-server** authentication. A GitHub
Actions \`GITHUB_TOKEN\` (app installation token) cannot be used for this
API; the connected GitHub app token cannot perform this preflight either.

For a later, deliberately authorised manual preflight:

1. In GitHub, create a **fine-grained personal access token** for this
   repository. Select **Agent tasks: read/write** and **Contents: read/write**.
   The latter is required for the pilot's isolated state branch ledger.
   Repository metadata read access is also needed for pull-request checks.
2. Store the token in XGBA repository Actions secret
   \`XGBA_COPILOT_AGENT_PAT\`. Never post a PAT in an issue, PR, chat or log.
   The legacy \`XGBA_COPILOT_DISPATCH_PAT\` has a different purpose and may
   not have Agent Tasks permissions.
3. Only after the reviewed workflow is deployed on \`main\`, run
   **Phase 1 Copilot Agent Tasks safe pilot** with mode \`preflight\`.
   This makes no billable Agent Task and reports whether Agent Tasks **read**
   access and the existing PR identity pass. It does not prove task creation
   permission, account concurrency, or that a task will be completed.
4. Before any **dispatch**, confirm GitHub Copilot premium request availability
   and set GitHub billing/spending limits so no paid overages can be charged.
   The pilot cannot verify the billing cap from the API.
5. A single task may be deliberately submitted with mode \`dispatch\` and
   **both** exact inputs \`I_AUTHORIZE_ONE_AGENT_TASK\` and
   \`ZERO_OVERAGES_CONFIRMED\`. These inputs default to \`NO\`.
   This is an explicit manual authorisation, not a scheduled task.
6. Then run mode \`inspect\` to record queued/in-progress/completed/failed.
   A completed Copilot job is **awaiting independent review**; it does not
   unlock further work automatically.

A missing or insufficient PAT blocks **preflight**. If the preflight cannot
be executed on the account, report the blocker; do **not** claim a successful
live integration.

## Local no-spend checks

\`\`\`bash
python3 -m py_compile tools/phase1_agent_task_pilot.py tests/test_phase1_agent_task_pilot.py
python3 -m unittest discover -s tests -p test_phase1_agent_task_pilot.py -v
python3 tools/phase1_agent_task_pilot.py --mode dry-run
\`\`\`

No secrets, API writes, paid tasks, state branches or external libraries
are needed for these tests. The new workflow runs them on PR changes.

## Criteria to progress beyond the pilot

1. Offline CI and live read-only preflight pass on **the exact reviewed head**.
2. The one deliberately authorised paid task is accepted by the real Agent
   Tasks API, with a verified task ID linked to the existing PR context.
3. Copilot produces meaningful changed source/test files and an exact-head
   checked review, **without** modifying protected files or duplicating work.
4. A separate reviewer validates the source semantics. Copilot completion,
   machine evidence, automated checks, and receipt comments do not count as
   independent semantic approval by themselves.
5. Only then, design and separately test a multi-package persistent ledger
   with disjoint scope claims and bounded concurrency. Do not assume Pro
   concurrency limits without testing them.

## Recovery cases

- \`RESERVED\` without task ID: possible POST outcome uncertainty; inspect
  real Agent Tasks manually and reconcile explicitly. **Never retry POST**
  without resolving it.
- \`DISPATCHED\` with \`failed\`, \`cancelled\`, \`timed_out\`: mark \`BLOCKED\`;
  investigate, don't relaunch automatically.
- \`AWAITING_REVIEW\`: task ended; collect PR diff, tests and provenance before
  considering a next scope.
- API 401/403: token/account permissions or preview mismatch; fix that
  rather than asking Copilot to attempt more work.
- All ledger conflicts fail closed. No automated resetting or deletion.

This pilot is a concrete implementation of GitHub's documented primitives;
**it is not yet an end-to-end production proof**.
