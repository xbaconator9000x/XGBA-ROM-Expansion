# Copilot draft-PR integration readiness — 2026-10-30

## Result

**BLOCKED; no merge or branch mutation performed.** The current repository `main`
reported by PR #37 is `de2a775184d69411016ff683a8075af72ef4a58d`. The authoritative
Phase 1 status remains `FAIL_INCOMPLETE`, with **0/14,834 independent semantic
approvals**. This audit and its checker do not alter source pins, evidence,
approval totals, the independent-review queue, or the gate.

The machine-readable record is
[`development/copilot-integration/manifest.json`](../../development/copilot-integration/manifest.json).
It records PR head/base values, dependency edges, observed workflow-run IDs and
the proposed topological sequence. The eight malformed historical base literals
are preserved separately from their evidence-backed PR-metadata corrections;
the mismatch and stale dependency remain explicit.

Manifest SHA-256 (unchanged):
`7413cf43416489ac1254bedba94575420c5fd285d7e6ccaa2fde0474f4b59fb6`.
Current checker SHA-256:
`3bd00d09ef3519c1a45423cbf094c601fdd38221c7e0240169bedf6690d1f06b`.
Base reconciliation fixture SHA-256:
`b6155a4eb45ac73c85cf9f542e6556f3e82ee70474078b6f97761f5831e0bc56`.
Live observation fixture SHA-256:
`a07df2ed1afe824ff184def096afb3e499bdc99fcfe98f74dc13b7c84610bacf`.
Generated blocker triage SHA-256:
`f87c618981d8006b30adc3178eeed68bc9ecb41801dded28ac0289cfbfc73659`.

## First concrete blocker in the recorded snapshot (2026-10-30)

The 2026-10-30 snapshot showed PR #8 based on
`8eb234e3508d55621ecc03531823036d336fa4d1`, while its declared
parent PR #7 currently has head `03608155216b4f283fd92b7c5d795dd066698244`.
Those SHAs do not match. PR #8's queried green run #40449595853 is on
`3f8fab19de2248aeee846cc344769ff069031398`, not PR #8's current head
`a03acca40614db990756aa88730688dcf084ee31`. Resolve the intended parent/base,
refresh the branch, and obtain current-head evidence before considering its
children. The focused 2026-11-04 live reconciliation later observed #8's base
matching #7's head; the stale-main parent and unverified current-head workflow
evidence remain blockers.

There was an additional data-integrity blocker: the recorded base literal
`18dee74bf3042326645eb850f6f1a4fea29f6` for PRs #11, #12, #14–18, and #21 is
malformed and cannot be repaired by padding. On 2026-11-04, a bounded public
API reconciliation replaced the active `base.sha` values with the full
`b76a2b686d4acf4302b9dacfad28494660d9b5f9` SHA returned by each PR metadata
read, preserving the original literal as `base.reported_sha`. This repairs the
malformed data, not the dependency relationship; the child PRs remain stale
relative to PR #8.

### Eight-child base identity reconciliation — 2026-11-04

The read-only public GitHub PR responses report the same base ref and base SHA
for all eight children. The repository branch listing reports that ref's tip as
PR #8's current head instead, and GitHub's compare API independently reports
`18dee74bf3042326645eb13ae7df3c551325b5a8` as the merge base of PR #8's live
head and each child's live head. These are three distinct identities and are
not interchangeable:

- PR metadata base SHA: `b76a2b686d4acf4302b9dacfad28494660d9b5f9`.
- Current target-ref tip / PR #8 head: `995e00904384191170075e8a57d18161ef1a2ec2`.
- Common merge base for these child heads: `18dee74bf3042326645eb13ae7df3c551325b5a8`.

The PR-object base SHA versus target-ref tip discrepancy is explicitly
unresolved. The checker is not relaxed to accept the merge base as the current
base or parent head. The manifest therefore remains blocked on the stale
dependency; its original malformed values remain in `base.reported_sha` for
auditability. Exact per-PR heads and public compare URLs are recorded in
[`base_sha_reconciliation.json`](../../tests/fixtures/copilot-integration-readiness/base_sha_reconciliation.json).
The direct unauthenticated PR REST fetch was unavailable in this environment;
the PR and branch identities were read through the GitHub read tools, while
public compare responses supplied each immutable merge-base identity. The
offline checker now reports **44 readiness issues** rather than stopping at the
eight malformed-SHA errors: each of the eight rows has an explicit stale
dependency diagnostic, alongside the pre-existing stale-head, missing-workflow,
and evidence blockers. This remains blocked, not a green dashboard.

| PR | Manifest head at 2026-10-30 | Live PR head read 2026-11-04 | PR metadata base ref / SHA | GitHub compare merge base | Classification |
|---|---|---|---|---|---|
| #11 | `a59756ee192659ac60988195bf7e5f1a4fea29f6` | `2021d98987c7c895288f9b70ad756ab9608f4ea0` | `phase1/review-readiness-handoff-20261027` / `b76a2b686d4acf4302b9dacfad28494660d9b5f9` | `18dee74bf3042326645eb13ae7df3c551325b5a8` | Malformed literal repaired; dependency on #8 stale. |
| #12 | `9ed9d2630a098525e7703853de0b804c56658da9` | `9ed9d2630a098525e7703853de0b804c56658da9` | Same / same | Same | Malformed literal repaired; dependency on #8 stale. |
| #14 | `618861ff17a4b9cfbb180f5531cf58d8414cbd03` | `618861ff17a4b9cfbb180f5531cf58d8414cbd03` | Same / same | Same | Malformed literal repaired; dependency on #8 stale. |
| #15 | `7c283d21b48ef3b2276a225465b59ff492364a12` | `7c283d21b48ef3b2276a225465b59ff492364a12` | Same / same | Same | Malformed literal repaired; dependency on #8 stale. |
| #16 | `dd6fb2c8e6ec15818ccb841760b540a04dc8212d` | `dd6fb2c8e6ec15818ccb841760b540a04dc8212d` | Same / same | Same | Malformed literal repaired; dependency on #8 stale. |
| #17 | `302465862501f542250d719444b3a9831406f6ac` | `302465862501f542250d719444b3a9831406f6ac` | Same / same | Same | Malformed literal repaired; dependency on #8 stale. |
| #18 | `61a49f48e372272ff2ffcc720e21366bd91507bd` | `61a49f48e372272ff2ffcc720e21366bd91507bd` | Same / same | Same | Malformed literal repaired; dependency on #8 stale. |
| #21 | `a324b99b486d56d57eab94049a2a25ad091a862b` | `a324b99b486d56d57eab94049a2a25ad091a862b` | Same / same | Same | Malformed literal repaired; dependency on #8 stale. |

The existing dependency edges remain #8 → #11/#12/#14–18/#21. Their recorded
parent head is the older `a03acca40614db990756aa88730688dcf084ee31`, whereas
live PR #8 is now at `995e00904384191170075e8a57d18161ef1a2ec2`. The repair
does not refresh those branches or claim readiness.

The #6 PR body cites passing run #40255555421 at `dacbcf31…`, not current head
`14536d85…`. The #7 body cites later passing evidence at `5bb4cad4…`, while the
PR metadata currently reports head `03608155…`. Those body-cited results were
not confirmed as exact-current-head runs.

## Stack inventory and ordering

All listed PRs were reported open and draft in the live PR listing. “Parent” is
the branch relationship observed from the PR base ref/SHA, not a claim that the
parent is merge-ready. Full 40-character values are in the manifest.

Two additional in-flight review PRs (#35 and #36) were inspected because they
overlap the same Phase 1 work: #35 reviews and reuses the savedata work in #12/#13;
#36 reviews and reuses Poryscript ABI work/evidence from #16/#20. Their branches
are based on current main, not those implementation branches. #35 changes eight
paths, including the existing `tests/mgba_bank_boundary.c`; #36 adds four
review-only files and does not change #16/#20 implementation files. Neither
review PR's own exact-head workflow evidence was verified. PR #36 cites run
#40506170513 at `58713218…`, which does not match PR #20's current `afb5fc17…`
head and is not PR #36 head evidence. Review those in-flight packets before
duplicating their work.

| PR | Parent / base | Stack finding |
|---|---|---|
| #2, #3, #4, #6, #7 | `main` | Root branches use older main SHAs than `de2a775…`; refresh/reconcile before integration. |
| #5 | #3 | Body says it carries #4's EEPROM packet. Treat #5 as the integration candidate for that shared content; compare actual trees before deciding whether #4 is independently needed. |
| #10, #8 | #7 branch | Siblings. #10's base equals #7's reported head; #8's base does not. Reconcile #7 first, then refresh both children as needed. |
| #11, #12, #14–18, #21 | #8 branch | Malformed recorded base literals were reconciled to the exact PR metadata SHA; current PR #8/head and merge-base evidence still show the child branches are stale. |
| #13 | #12 | Base equals #12's reported head; current run #40480788248 is green on the exact #13 head, but the available Actions result did not expose actual base SHA provenance. |
| #19 | #11 | Base equals #11's reported head. Run #40505350595 is green on exact head `8ba12ff…` (push/source-head evidence; no PR merge-base claim). |
| #20 | #16 | Base equals #16's reported head. Run #40506170513 is green on `58713218…`, not current #20 head `afb5fc17…`. |
| #22 → #24 → #26 → #28 | chained | Each recorded base equals its immediate parent head. #24 run #40525408728 is green on exact head; current exact-head evidence for #22, #26, and #28 was not verified. |
| #27 | #14 | Base equals #14's reported head; exact-head workflow evidence not verified. |
| #23, #25 | `main` | Both use old main `52796a8619b08d86f2f9fed024f8cbf95a0f5822`; refresh before review/integration. |

### Safe candidate order (not merge authorization)

1. Reconcile root candidates #2, #3, #6, #7, #23, and #25 with current main and
   revalidate their diffs. The manifest also flags #4/#5 overlap.
2. If #5's tree is confirmed to carry the needed #4 changes, assess #3 → #5 as
   one ordered stack and do not apply #4 twice.
3. Refresh #7, then reconcile its children #10 and #8. PR #8 is the first
   concrete blocker above.
4. Only after #8 has current base/head evidence, reassess #11, #12, #14–18, and
   #21; their recorded base targets the old handoff point.
5. Continue only on refreshed parent SHAs: #12 → #13; #11 → #19; #16 → #20;
   #18 → #22 → #24 → #26 → #28; and #14 → #27.
6. Require successful workflow evidence tied to current head and base
   provenance. Do not equate any source scan, CI run, or workflow artifact with
   independent semantic approval.

## Exact workflow evidence inspected

| PR | Run | Conclusion / tested SHA | Assessment |
|---|---:|---|---|
| #2 | 40216488315 | success / `b14bfc164aa623648342405c04ed7fcf475005eb` | Stale vs current head `69726db…`. |
| #8 | 40449595853 | success / `3f8fab19de2248aeee846cc344769ff069031398` | Stale vs current head `a03acca…`. |
| #11 | 40468447957 | success / `26402b704480cbeb3fe9fe467a1d4b2c75ac54c3` | Stale vs current head `a59756e…`. |
| #13 | 40480788248 | success / `9bf2b6f31c7e0ebf00e1ebaf6aee6f0930c90444` | Exact head; PR-event base SHA was not returned by the Actions read result. |
| #15 | 40492941829 | success / `7c283d21b48ef3b2276a225465b59ff492364a12` | Exact head; PR-event base SHA was not returned. |
| #19 | 40505350595 | success / `8ba12ff806248875856cd965f1265fbfec37334f` | Exact branch head; push event, not PR merge-base evidence. |
| #20 | 40506170513 | success / `587132181ef728b635968dd091b1cf171e78f753` | Not current PR head `afb5fc1714235f1349f51b256ba20ac4c78e2019`. |
| #21 | 40510922233 | success / `a324b99b486d56d57eab94049a2a25ad091a862b` | Exact head; PR-event base SHA was not returned. |
| #24 | 40525408728 | success / `b6f0cee6a4b5ec25c2eb39eaf4340b65e8da10d8` | Exact branch head; push event, not PR merge-base evidence. |

Run IDs and SHA values are recorded in the machine-readable manifest. Only the
runs listed above were queried directly here. Other workflow results mentioned
in PR descriptions are **unverified** in this audit, not promoted to confirmed
evidence.

Artifacts were available for #8, #20, and #24 only: #8 run #40449595853
artifact #12709673369 digest
`sha256:34417e0f2f2be8ce480a9789c480081c8e1ee179b0fe8319483726ead1422f79`;
#20 run #40506170513 artifact #12735216391 digest
`sha256:37cc5d0e03fd481c61721816533b8869709b1a23b7b9bc6f76df701252f988e5`;
#24 run #40525408728 artifact #12746115949 digest
`sha256:eb61d5d4565912a599429fc2cf3499384dca2bcf4a14faa562a99341971dc378`.
The first two artifacts correspond to stale PR heads; #24 is an exact branch-head
artifact but its push event does not prove a PR merge-base test.

The historical PR #21 failure run #40510851149 (job #122212051019) was also
inspected. It ran at `7558b8f17f776b00c3ab43c06d45da6817cf9119`; the pinned
FireRed verifier failed at `assert pad_to - origin == 16 * 1024 * 1024`. The log
shows the checker selected the EWRAM origin rather than ROM origin. The later
run #40510922233 passed at the current PR head `a324b99…`; the failed run is
historical, not current-head failure evidence.

## Tree/diff and current-main limits

- The PR listing and individual PR metadata were read for #2–8, #10–28. PR #8's
  full unified diff exceeded GitHub's 20,000-line response limit (HTTP 406), but
  the paginated file API returned all 130 changed paths (all marked added).
- Compared against the exact current-main tree at `de2a775…`, none of PR #8's
  130 added paths and none of PR #11's eight changed paths exist in main. This
  establishes path absence, not functional absence under different paths.
- PR #35's one existing path is `tests/mgba_bank_boundary.c`; its other seven
  paths are additions. PR #36's four review paths are additions absent by path
  from main.
- PR #11's actual file list contains its binary-triage scripts, integrity
  checker, tests, docs, and workflow. PR #19's diff extends the same triage code
  on top of #11; that shared code is an expected parent/child overlap, not
  evidence of independent duplicate work. File listings for other branches were
  inspected, but a full semantic tree comparison across every branch was not
  completed.
- Public unauthenticated REST access returned HTTP 403 in this environment. No
  PAT was introduced or used. The checker has live public-API mode and
  API-shaped offline mode; live failures are reported as blocked.
- PRs being open is not proof that none of their commits were cherry-picked to
  main. Commit ancestry/tree containment was unavailable, so what is already
  present in main is explicitly **unverified**.
- Exact source pins and evidence artifact/blob hashes were not available for
  every PR from the exposed metadata. No hashes are inferred from PR titles or
  prose. The workflow run head SHA above is the exact observed evidence SHA;
  artifacts were not downloaded or independently rehashed.

## Checker

Run `python3 tools/copilot_check_integration_readiness.py` to query public
GitHub read endpoints without credentials. Run with `--offline` to use only
observations already captured in the manifest, or provide an API-like snapshot
with `--snapshot FILE`. It fails closed for absent PR/dependency data,
changed head/base/main SHAs, malformed SHAs, absent successful evidence, stale
green runs, and PR merge-SHA runs lacking matching actual head/base provenance.
An exact PR-head run is accepted only when its executed SHA equals the current
PR head and its run PR record explicitly matches the current head and base SHA.
A merge-SHA run requires a direct commit lookup whose immutable commit object
has exactly the current base SHA as first parent and PR head SHA as second
parent; the mutable `merge_sha` field alone is not trusted.
`pull_request_target` runs executing only base code are rejected. The checker
also rejects empty/duplicate PR scopes, dependency cycles, and incomplete or
non-topological PR order.
Its only result is integration metadata readiness; it never edits approvals,
queues, gates, pins, branches, or PR state.

Workflow evidence is classified per required workflow as `executed_success`,
`executed_failure`, `action_required_zero_job`, `pending`, `missing`, or
`stale_head_base`. A successful conclusion alone is insufficient: the latest
applicable run attempt must have a complete, nonempty job list, and every
executed job must have completed successfully (skipped jobs are allowed only
alongside at least one successful job). If a newer current-head attempt is
authorization-blocked or pending, an older success does not override it.
Each completed job's recorded attempt must match the selected run attempt.
Blocker output includes the run URL, attempt, job URLs when available, tested
and reported head/base SHAs, and a specific next action. Authorization-blocked
runs are never retried or counted as green automatically. If public job details
are unavailable, evidence is reported missing/unverified rather than inferred
from the run conclusion.

### Focused live reconciliation — 2026-11-04

The recorded offline manifest remains a historical snapshot, not an assertion
that these are the latest live PR states. Current PR metadata and exact run/job
reads were made for #7/#8, #13, #27, and #35–37. A machine-readable supplement
is pinned in
[`live_observations_20261104.json`](../../tests/fixtures/copilot-integration-readiness/live_observations_20261104.json).

| PR | Live head / base | Exact-head workflow observation | Meaning |
|---|---|---|---|
| #7 | Head `03608155216b4f283fd92b7c5d795dd066698244`; base main `f848fb21d3056e3f5653154cd48a699a52c8d5a5` | Not included in this focused workflow query. | Still based on stale main. #8's current PR metadata base now equals this exact #7 head, unlike the older base SHA recorded in the offline manifest. |
| #8 | Head `995e00904384191170075e8a57d18161ef1a2ec2`; base #7 head `03608155216b4f283fd92b7c5d795dd066698244` | Not included in this focused workflow query. | The live #8 → #7 base relationship now matches; the stale-main parent #7 and current-head evidence remain blockers. This newer metadata does not rewrite the recorded offline snapshot. |
| #13 | Head `0bf5a496df18ef9e3c6cf39ef361ffbe93931c6a`; base #12 head `9ed9d2630a098525e7703853de0b804c56658da9` | Workflow `398059096`, run [#41853164293](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41853164293), attempt 2: success, 1/1 job; exact current head. | Actual CI success. The Actions read exposed the PR number and head but not the run-time base SHA, so exact base provenance remains unverified. |
| #27 | Head `2cb51ea83a3ef4c3186d19d2f9a80e88fa5d2f36`; base #14 head `618861ff17a4b9cfbb180f5531cf58d8414cbd03` | Workflow `399979453`, run [#41871074286](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41871074286), attempt 1: `action_required`, 0 jobs. | Authorization gate, not a code failure or success. A maintainer with write access must approve the existing run; do not retry or treat as green. The required workflow ID is not yet pinned for #27 in the manifest. |
| #35 | Head `9a31fb1dfa0a08f95a06a3c2bf8cd431aafccd29`; base main `de2a775184d69411016ff683a8075af72ef4a58d` | Workflow `401590285`, run [#41037997890](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41037997890), attempt 2: success, 1/1 job; exact current head. | Savedata review packet overlaps #12/#13. It is not stacked on either. Run-time base SHA was not returned; neither CI nor owner review is independent semantic approval. |
| #36 | Head `fc54588319aea2a798f2455fb594c367209f8b85`; base main `de2a775184d69411016ff683a8075af72ef4a58d` | Workflow `401588179`, run [#41850174614](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41850174614), attempt 2: success, 2/2 jobs; exact current head. | Poryscript ABI review packet overlaps #16/#20, but is not stacked on either. Run-time base SHA was not returned; CI is not semantic approval. |
| #37 | Head `9233dfe2800f4deeed729fade251047a35a793ed`; base main `de2a775184d69411016ff683a8075af72ef4a58d` | Workflow `401606059`, run [#41871673473](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41871673473), attempt 1: `action_required`, 0 jobs. | This PR's current workflow is permission-gated, not green. No retry was requested. |

#35, #36, and #37 are sibling branches based on main, not an ordered stack. The
run/job APIs returned current heads and job attempts, but did not expose the
base SHA used by those PR-event executions. The checker now rejects an exact
head run whose PR run record omits current head/base provenance; a green exact
head alone cannot silently substitute for base-bound evidence. For a merge-SHA
run, the checker still requires a verified merge commit whose ordered parents
are exactly the current base and PR head.

### Per-blocker reproducible triage

`development/copilot-integration/blocker-triage-20261104.json` contains one
source-linked record for every one of the **44** blockers emitted from the
recorded manifest: 7 stale-main bases, 9 stale dependency bases, 19 workflow
IDs not pinned in that snapshot, and 9 runs without acceptable exact
head/base provenance. Each entry retains its original checker issue, exact
manifest head/base, source URLs, and concrete closure action. The attached
live observations are supplemental and never clear historical offline
blockers. Regenerate the file with:

```bash
python3 tools/copilot_check_integration_readiness.py \
  --offline \
  --live-observations tests/fixtures/copilot-integration-readiness/live_observations_20261104.json \
  --triage-json \
  > development/copilot-integration/blocker-triage-20261104.json
```

The offline checker continues to return blocked (exit 1). Current PR metadata
shows #8's base relationship to #7 has advanced beyond the stale relationship
captured by the historical manifest; refreshing the stack, testing each
current head/base, and reconciling all other bases and workflow IDs remain
unresolved. The first actionable integration steps are to reconcile stale root
PRs against current main in the manifest order (#2, #3, #4, #6, #7, #23, #25);
PR #7 must be reconciled before its child PR #8. The
Phase 1 gate remains `FAIL_INCOMPLETE`, with zero independent semantic
approvals; source scans and CI do not change that gate.

The report is reproducible with `--triage-json`; it does not change the
checker’s exit status. By default it uses the recorded snapshot only. The
optional `--live-observations` file is a dated, read-only API receipt, not a
replacement for a fresh live query.

Focused fixtures: `python3 -m unittest discover -s tests -p test_copilot_check_integration_readiness.py`.

## Reusable read-only Phase 1 PR validation

The existing
[`copilot-integration-readiness-tests.yml`](../../.github/workflows/copilot-integration-readiness-tests.yml)
workflow is the single PR entry point for the supported, local-only validation
suites. The workflow must first be reviewed and merged into the target branch
through the repository's normal process; a PR cannot make its own modified
workflow trusted by declaring it so. Once present on the base branch, it runs
on relevant PR updates, grants only `contents: read`, uses no secrets, and
checks out `github.event.pull_request.head.sha` rather than the synthetic PR
merge ref. Before running any tests,
[`verify_phase1_ci_context.py`](../../tools/verify_phase1_ci_context.py) checks
that the event is `pull_request`, the repository and PR number scopes are
present, and `git rev-parse HEAD` exactly equals that event's head SHA. Its
negative tests reject a wrong executed SHA, missing PR scope, wrong event type,
and mismatched repository scope.

The workflow reuses these bounded suites without changing review state:

| Validation | What it establishes | Safe CI boundary |
|---|---|---|
| `phase1_independent_queue_validate.py` and `test_phase1_independent_queue.py` | Queue schema, source pins, and zero-approval invariants | Reads checked-out files and writes only unit-test temporary fixtures; it is not an independent reviewer. |
| `test_phase1_continuous.py` | Failure/retry state-machine behavior | Uses in-memory fakes; the workflow does not invoke the queue-writing worker or its Actions write permissions. |
| `test_xgba_rom_compatibility_preflight.py` | Synthetic-ROM inspect-only and malformed-input cases | Uses temporary synthetic files; it does not inspect or transform user ROMs. |
| `test_copilot_check_integration_readiness.py` and `--offline` check | Readiness-provenance fail-closed cases and the expected currently blocked audit | Uses pinned offline data; a passing test does not make the manifest ready. |
| `test_phase1_ci_context.py` | Exact-head and PR-scope enforcement | Exercises valid and negative event/checkout combinations without credentials or network access. |

This entry point deliberately does not run compiled FireRed, mGBA, or Porymap
validation. Those existing manual workflows require pinned upstream checkouts,
ARM/Thumb compilers, native libraries, or other toolchain setup and network
access; they remain separate evidence jobs and their output is not semantic
approval. The `phase1-continuous.yml` evidence-queue job is also excluded: it
has `actions: write`/`contents: write` permissions and mutates durable review
queue state. Only its isolated in-memory regression tests are reused here.

The workflow cannot override GitHub's fork-workflow approval policy. For
public-fork PRs, whether approval is required is controlled by repository,
organization, or enterprise Actions settings. A maintainer with write access
may need to approve a run under the configured policy; a workflow YAML change
cannot bypass that approval. The repository setting is under **Settings →
Actions → General**, in the fork pull-request workflow approval controls.
GitHub documents this in
[Approving workflow runs from forks](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)
and
[Managing GitHub Actions settings for a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository).
No `pull_request_target`, elevated token permissions, workflow inputs, or
secret-backed credentials are used to work around that platform setting.

CI is limited to code/test integrity. The authoritative Phase 1 gate remains
`FAIL_INCOMPLETE` with 0/14,834 independent semantic approvals, and neither a
green check nor a queue validation result can change that status.
