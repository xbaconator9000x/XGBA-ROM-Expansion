# Phase 1 — Trainer Tower ARMv4T Clang layout cross-check

**27 October 2026 · new compiler ABI witness, not original agbcc or runtime certification.**

This extends the [exact-pinned host C layout model](PHASE1_P0_FIRERED_TOWER_LAYOUT_HOST_MODEL_2026-10-27.md). The source checker reads the **seven pinned FireRed blobs** from the same upstream commit, extracts the actual `BattleTowerPokemon`, `TrainerTowerTrainer`, `TrainerTowerFloor`, `EReaderTrainerTowerSet` and `SaveSector` declarations, and emits a freestanding C translation unit. It compiles the translation unit using `clang -target armv4t-none-eabi`, verifies ELF32/ARM using `readelf`, and enforces ten compile-time size/offset assertions.

Expected ARM-target layout: Pokémon record 44 bytes; trainer 328; floor 992; full set 7,944; split at floor 4 offset **3,976**, remaining **3,968**; ordinary sector counter offset **4,092**. These match the independent host model and the source producer/consumer copy boundaries. The compiled object SHA and Clang version are retained in the evidence artifact, not assumed stable across toolchain versions.

**Proof boundary:** An ARMv4T Clang object validates the source-extracted C struct ABI under that compiler; it does **not** establish identical original agbcc or modern GCC binary output, runtime Trainer Tower persistence, flash corruption handling, mGBA save-state interoperability, or editor round trips. Those remain fail-closed Phase 1 obligations. This adds no complete-file candidate or independent approval, and does not begin Phase 2.
