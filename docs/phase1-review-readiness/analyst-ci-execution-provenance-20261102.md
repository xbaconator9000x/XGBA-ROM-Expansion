# Phase 1 exact-head CI execution provenance and authorization recovery — 2026-11-02

This is a **non-approving CI provenance record**, not a source semantic dossier, review receipt, independent approval, new P0 partial, policy change, or permission bypass. It belongs only to the existing draft PR #8 branch. Original pinned source revisions, seven receipt bodies, machine dossiers, and the main semantic gate are not modified.

## Verified immutable source and receipt context

- mGBA original source revision: `fd9dc5c2cbf234365068855851107e762fc6211b`.
- Seven append-only user-defined Copilot review claims were introduced at PR8 commit `487da72f27dfc4e634cecc11b4dbdd596ec05e00`; receipt register Git blob `0c5b50003b89d346d04c86e52774c4e01e9d321b`.
- Four earlier Copilot receipts passed the separate v5 live validator at PR2 commit `2aec2ff18f40604cc72f8899d35f92d0364570cd`, executed GitHub Actions run `41337689699`. These are user-defined Copilot-reviewed source items, **not** historical external-human approvals.
- Three newer whole-source records (decoder, emitter and Thumb headers) have canonical receipt SHA-256 digests respectively `68d40e2e26b63751fd5ebe5b2c6d8088d1ee4435174946782d87c24dc2eb7361`, `a9a92f196fb14985d9d7dbe36e647ed5bc17ab67c74c9426c0b7c2f92dfe3bf8`, and `f4fa4d806cb13b7b8518a675e244bb476fe9ac73d31ef1f04e7c3fdbdbcec2ad`. None is counted without the prescribed attributable attestation and executed exact-head push and PR CI.
- Non-Copilot substantive evidence is in `docs/phase1-review-readiness/mgba-arm-three-headers-chatgpt-source-evidence-20261102.md` at prior commit `e2cae6f1c073be4ee04691a57915adf740868279`. Host isolated probes are **not** native linked/runtime/gameplay/save-restart/physical Flash evidence.

## Actual GitHub workflow evidence, not inferred green

1. Original receipt-introduction head `487da72f27dfc4e634cecc11b4dbdd596ec05e00`: PR workflow run [41349105412](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41349105412) completed **success**, attempt 2. Copilot separately checked all 41 jobs, including the nested census, and re-fetched the three pinned original source/dossier hashes.
2. The distinct `push` census [41349099551](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41349099551) on that same head remains **completed/action_required with zero jobs**. Do not treat it as a test failure or as passing CI.
3. PR2 v6 seven-record adapter commit `8a7ecde44e21532df9aa1abbdb3935afb8b734e3` has a `push` run [41354042534](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41354042534) also **action_required with zero jobs**. Its v6 live validator has not executed at that head.
4. PR13 pinned mGBA SaveConverter sanitizer [41322907862](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41322907862) remains **action_required with zero jobs**; no native sanitizer CI result is asserted.
5. After the repository owner adjusted fork-PR approval settings, an attempted GitHub Actions `rerun-failed-jobs` API request for each of those three blocked runs returned **403: This workflow run cannot be retried**. This is a workflow authorization limitation, not an executed code-test failure. No unauthorized approval or security bypass was attempted.

## Scoped recovery and acceptance

A new expected-parent fast-forward commit on this **existing PR8 branch**, with this substantive provenance record under the pre-existing census push path filter `docs/phase1-review-readiness/analyst-*.md`, provides a fresh eligible push event after the owner's policy change. This is **only a retry opportunity**, not evidence that a new run will execute. Inspect the resulting **new exact-head** push and PR workflow runs and their executed jobs. Do not reuse the old successful PR run as proof for a different head.

If both new-head runs execute and pass, the independent Copilot reviewer must still produce three original bot-authored, unquoted, post-introduction receipt-bound attestations or explicit objections. Any v6 adapter re-pin must preserve all seven original receipt bytes/digests, distinguish the original receipt-introduction commit from a later CI-only head, require original pinned source/dossier/licensing checks and exact-head PR+push CI, and pass adversarial tests. Do not silently weaken the original checks to green the workflow.

Historical external semantic approvals remain **0/338 P0** and **0/14,834 overall**; authoritative `semantic-snapshots/current/phase1_mapping_gate.json` stays `FAIL_INCOMPLETE` (blob `dab5789433dc55cf325a917a220d060088bf1d29`). No Phase 2 work, external paid inference, new PR, new scheduler, main/audit write, or self-approval is authorized by this record.
