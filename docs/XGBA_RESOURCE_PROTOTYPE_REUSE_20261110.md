# XGBA early resource-prototype reuse — historical

**Status: historical implementation scope; Copilot dispatch retired 12 November 2026.**

The early R1–R3 work established a versioned resource sidecar, deterministic manifest/package handling, and a bounded opt-in host staging bridge. R4–R6 subsequently developed actual source-built FireRed/mGBA integration. Those **implemented resource components and their tests remain**; only the old automation that dispatched tasks for their development was retired.

Current work should reuse the verified native integration in `main`, not restart the historical task queue. Refer to the [README](../README.md), [source and memory architecture](xgba-integration-architecture.md), and [native verification evidence](../evidence/README.md).

The old dispatcher source, task templates, manual pilot and corresponding workflow entrypoints are no longer in the current tree. Their source history remains accessible through Git until a separate, coordinated history-redaction process is performed.
