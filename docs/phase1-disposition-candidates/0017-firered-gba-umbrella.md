# Candidate 0017 — FireRed GBA umbrella header

**State: analyst-prepared whole-file candidate; PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** File was read at the exact pinned upstream commit, including all output-section selectors and debug/discard directives. Neither passing CI nor this analyst record is independent semantic approval.

## Exact source identity
- Repository: `pret/pokefirered`; upstream commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Exact whole-file path: `include/gba/gba.h`; Git blob SHA verified by direct pinned GitHub file fetch: `4b5f2de954eea62e21c62c12d49536fcd7e65b7d`.
- [Immutable upstream source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/gba/gba.h); [pinned linker-variant source checker](../../tools/phase1_firered_linker_variant_contract.py); [source evidence](../PHASE1_P0_FIRERED_LINKER_VARIANTS_2026-10-26.md).

## Entire file semantics
The 12-line header contains the include guard `GUARD_GBA_GBA_H` and eight ordered includes: C library `<string.h>`; local `defines.h`, `io_reg.h`, `types.h`, `multiboot.h`, `syscall.h`, `macro.h`, and `isagbprint.h`. It has **no independent definitions, function bodies, inline assembly or resource tables**. The guard prevents duplicate inclusion within one preprocessing unit, not ABI incompatibility between header versions.

## Dependency/expansion boundary
This is a **compile-time API aggregation surface**. Any future XGBA-aware compilation must preserve the header's ordered transitive declarations/macros and build include-path resolution; no runtime ROM addressing or memory-bank semantics are established by the umbrella header itself. The included `syscall.h` has a separate pending review candidate. Transitive header definitions, macro collisions, language/compiler modes and all downstream translation units remain distinct review obligations.

## Reviewer obligations and verdict
Independently inspect each transitive include at the pinned commit, compare representative legacy/modern preprocessing and compilation, verify actual include resolution, and assess downstream consumers before whole-file signoff. **PENDING_INDEPENDENT_REVIEW; reviewer identity/date not supplied; gate contribution 0.**
