# XGBA historical autonomous task queue — retired

**Status: RETIRED on 12 November 2026. This is historical context only, not an active development workflow.**

The original product-agent experiment used a finite, fail-closed sequence of R1–R6 tasks, exact-head GitHub Actions checks, a single active agent at a time and an atomic ledger. It was superseded by direct source implementation and real original-game mGBA acceptance tests, later consolidated into `main`.

The legacy scheduled/triggered Copilot product dispatcher and all pilot/manual Porymap task dispatchers have been removed from the active source tree. No workflow in this retired group should create agent tasks, issue bot commands, or read legacy Agent Task credentials. Their earlier implementation and execution receipts may remain in Git history and old GitHub workflow logs.

The original R6 proof and subsequent R7–R27 source-built native evidence are documented in the [root README](../README.md) and [evidence gallery](../evidence/README.md). Current XGBA engineering should continue through independently reviewed source changes and genuine CI results, not by reactivating a historical autonomous queue.

**Scope:** this retirement affects only obsolete Copilot dispatchers. It does not remove the game/emulator resource API, its real tests, or other unrelated development automations. Any new agent automation needs a new, expressly scoped design and its own authorization.
