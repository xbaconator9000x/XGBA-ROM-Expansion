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
the proposed topological sequence. SHA-1 strings below are transcribed from
GitHub PR/Actions read responses; malformed or unavailable values are not
repaired or inferred.

Manifest SHA-256:
`77bd93912da0d95c1eed90b1e0105a9615972a8091cad3a9ac5b8371eeba3445`.
Checker SHA-256:
`cad01530abd61506f26ee835c477ec6fdac9fe43cdcd7fadc4926e2cdd2c5628`.

## First concrete blocker

PR #8 is based on `8eb234e3508d55621ecc03531823036d336fa4d1`, while its declared
parent PR #7 currently has head `03608155216b4f283fd92b7c5d795dd066698244`.
Those SHAs do not match. PR #8's queried green run #40449595853 is on
`3f8fab19de2248aeee846cc344769ff069031398`, not PR #8's current head
`a03acca40614db990756aa88730688dcf084ee31`. Resolve the intended parent/base,
refresh the branch, and obtain current-head evidence before considering its
children.

There is an additional data-integrity blocker: the PR API returned the base
string `18dee74bf3042326645eb850f6f1a4fea29f6` (37 characters) for PRs #11, #12,
#14–18, and #21. It is not a full Git SHA and is preserved verbatim in the
manifest. The checker rejects it rather than padding or guessing missing
characters.

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
| #11, #12, #14–18, #21 | #8 branch | Their base value is the older `18dee…` handoff checkpoint, not #8's current `a03…` head. Base SHA from the API is malformed (37 chars) for this group. |
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
PR head. A merge-SHA run requires a direct commit lookup whose immutable commit
object has exactly the current base SHA as first parent and PR head SHA as
second parent; the mutable `merge_sha` field alone is not trusted.
`pull_request_target` runs executing only base code are rejected. The checker
also rejects empty/duplicate PR scopes, dependency cycles, and incomplete or
non-topological PR order.
Its only result is integration metadata readiness; it never edits approvals,
queues, gates, pins, branches, or PR state.

Focused fixtures: `python3 -m unittest discover -s tests -p test_copilot_check_integration_readiness.py`.
