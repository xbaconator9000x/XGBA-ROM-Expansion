# Phase 1 whole-file analyst candidate — FireRed mapjson fatal-error interface

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, path `tools/mapjson/mapjson.h`, exact verified Git blob `6e961a28ec0e2c6a017e7dda2e9d81f07e3e3ceb`. [Pinned source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/tools/mapjson/mapjson.h).

## Complete source inventory
A single guarded C++ header (`MAPJSON_H`) imports `<cstdio>`, exposes `std::fprintf` and `std::exit` via using declarations, and imports `<cstdlib>`. It defines one `FATAL_ERROR(format, ...)` variadic macro under two compile branches. With `_MSC_VER`, it calls `fprintf(stderr, format, __VA_ARGS__)`; otherwise it uses GCC-style `##__VA_ARGS__` to support empty variadic arguments. Both wrap the statements in `do { ...; exit(1); } while (0)`, and both always terminate on invocation. There are no other declarations, structs, exported symbols or runtime state in the header.

## Cross-file contract and expansion significance
`tools/mapjson/mapjson.cpp` (candidate [0032](0032-firered-mapjson-generator.md)) invokes this macro for invalid JSON, unsupported event kinds, missing layout, wrong CLI arguments and file open failures. The macro only guarantees a diagnostic print and process termination; it does **not** validate output-file completion or guarantee rollback of partially written generated artifacts. A build tool or editor importer must distinguish a failed generator from an authoritative source-map update and preserve existing authoring data on failure. Platform-specific macro preprocessing must be verified rather than assuming the two branches are identical for all call shapes.

## Reviewer obligations
Compile controlled invocations with zero and multiple variadic arguments under supported GCC/MSVC preprocessors; inspect actual CLI exit codes and partial-output behaviour. Check all `FATAL_ERROR` callers and generated-file atomicity, and verify that the build pipeline fails closed. Pinned source and hash inspected in full; no compiler/runtime/editor evidence or independent reviewer. **Verdict pending; approval credit 0; Phase 1 FAIL_INCOMPLETE.**
