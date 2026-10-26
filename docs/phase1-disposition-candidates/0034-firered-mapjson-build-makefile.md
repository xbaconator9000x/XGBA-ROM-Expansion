# Phase 1 whole-file candidate 0034 — mapjson build Makefile

**PENDING INDEPENDENT WHOLE-FILE REVIEW — NOT APPROVED.** Pinned upstream `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. This is analyst source mapping only; no independent signoff, compiled binary equivalence, emulator or editor certification.

**Exact source:** `tools/mapjson/Makefile`; Git blob `100e809c6c27e6c04d3b6f2406ff288922d80c13` (verified from the exact upstream commit). [Pinned source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/tools/mapjson/Makefile). The **entire 24-line file** was inspected.

## Entire-file semantic disposition candidate
- `CXX ?= g++` selects a default C++ compiler only if not already defined; `CXXFLAGS := -Wall -std=c++11 -O2` is the local compile policy. External `LDFLAGS` are appended to the link command; exact toolchain and compiler output are not pinned here.
- `SRCS := json11.cpp mapjson.cpp` declares the two compilation inputs. `HEADERS := mapjson.h` declares only **one** header dependency. Both `json11.cpp` and `mapjson.cpp` include `json11.h`, but **`json11.h` is not a prerequisite of the executable target**.
- `ifeq ($(OS),Windows_NT)` chooses `.exe`; other platforms use the bare `mapjson` executable name. `.PHONY: all clean`; `all` depends on the platform-specific executable and runs `@:`. `mapjson$(EXE)` rebuilds only when a declared source/header prerequisite is newer (or the executable is absent); its recipe compiles both sources in one C++ invocation. `clean` deletes both executable spellings via `$(RM)`.
- The upstream `make_tools.mk` (blob `d7b9315ad7beb37116793d8f805160679d3b4001`) includes `mapjson` in `TOOL_NAMES` and recursively invokes `make -C tools/mapjson`; `Makefile` includes `make_tools.mk`. The separate `map_data_rules.mk` drives mapjson-generated outputs. These are build-graph edges, **not** evidence of the final ROM bytes.

## Reproduced bounded make dependency witness
Using a **verbatim copy of the 24-line pinned Makefile** in an isolated temporary directory with placeholder `json11.cpp`, `mapjson.cpp`, `mapjson.h`, `json11.h`, and a preexisting newer `mapjson` executable, GNU Make `make -n mapjson` reported **"mapjson is up to date"** when **only `json11.h`** had a later timestamp. Making the declared `mapjson.h` newer produced the expected `g++ -Wall -std=c++11 -O2 json11.cpp mapjson.cpp -o mapjson` recipe. This is an isolated dependency-resolution proof, **not** a full pinned FireRed build, tool-output regression or observed stale generated map file. Reproduce with timestamp-controlled placeholders and `make -n mapjson` against the exact pinned Makefile.

## Expansion implications and reviewer blockers
A stale mapjson binary can survive a header-only edit to `json11.h` in incremental builds; clean rebuilds are unaffected by this missing dependency. Before accepting generated map metadata as reproducible, pin the executable build inputs and check both clean and incremental rebuild behaviour. Independent reviewer must verify the full source, make include/call chain, Windows variant, and actual build outputs. **Verdict: PENDING; reviewer: none; approval contribution: 0.**
