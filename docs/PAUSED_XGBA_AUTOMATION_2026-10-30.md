# XGBA automated Actions hold — 2026-10-30

Owner requested reduction in high-volume automated GitHub usage without proportional product progress. **Stop automatic XGBA runs until a targeted restart is authorised.** Do not change Shattered or Essentials Studio workflows here.

- GitHub repository remains public. Existing source, all evidence, PR branches, tests, and archived artifacts remain intact.
- The separate ChatGPT hourly automation `Continuous XGBA Phase 1` was paused.
- All 26 GitHub workflow files on main are changed to `workflow_dispatch` only in sequential preservation commits. The workflows remain manually runnable and are **not** deleted.
- Historical billing screenshot gross XGBA usage $36.30, while public Actions standard runners normally receive applicable free-use discounts. Gross is not an invoice.
- No further automatic tests, evidence archives, 15-minute watchdogs or workflow_run fanouts should execute from main after all 26 edits. Existing PR-head workflows can still run if somebody pushes to those older branches; do not push to them while paused.
- Already queued/running workflows may finish. Manual runs remain possible by explicit action.
- Future resumption: review measured runner cost, use a specific working expansion milestone (not exhaustive no-signoff inventories), and selectively restore ONLY the needed triggers from commit history. No paid overages without explicit approval.

Last checked Phase 1 status: no implemented unlimited-memory/ROM architecture; 0 independently approved whole-file semantic dispositions despite 14,834 inventoried files. Reassessment should prioritize a small testable prototype rather than further low-yield dossiers.
