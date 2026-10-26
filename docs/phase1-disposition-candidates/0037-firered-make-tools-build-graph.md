# Phase 1 whole-file candidate 0037 — FireRed tool build dispatcher

**PENDING INDEPENDENT WHOLE-FILE REVIEW — NOT APPROVED.** Pinned upstream `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. This is analyst source mapping only; no independent signoff, compiled binary equivalence, emulator or editor certification.

**Exact source:** `make_tools.mk`; Git blob `d7b9315ad7beb37116793d8f805160679d3b4001` (verified against pinned upstream). [Pinned source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/make_tools.mk). **All 22 lines** inspected.

## Whole-file semantic disposition candidate
- The leading comment establishes the file's purpose: tool executables under `tools/`, invoked standalone or from the root `Makefile`. `MAKEFLAGS += --no-print-directory` suppresses recursive directory chatter.
- `TOOLS_DIR := tools`; `TOOL_NAMES := bin2c gbafix gbagfx jsonproc mapjson mid2agb preproc ramscrgen rsfont scaninc wav2agb` is the complete inclusive list. `TOOLDIRS := $(TOOL_NAMES:%=$(TOOLS_DIR)/%)` expands one directory per tool.
- `RULES_NO_SCAN += tools check-tools clean-tools $(TOOLDIRS)` marks these goals as not requiring a FireRed dependency scan; `.PHONY: $(RULES_NO_SCAN)` makes them always execute when requested. The file defines `tools: $(TOOLDIRS)` as an aggregate target.
- `$(TOOLDIRS): @$(MAKE) -C $@` recursively delegates each tool to its local Makefile. `clean-tools` iterates the same directories with `$(MAKE) clean -C $(tooldir)`. There is **no** local C++ compilation rule, file-hash pinning, or proof of binary output equivalence in this dispatcher.
- The root `Makefile` (blob `8b454dbd18eb0069fa5851d788697190890a5b37`) includes this file. The local `tools/mapjson/Makefile` (candidate 0034) compiles `json11.cpp` and `mapjson.cpp` and omits `json11.h` from its target prerequisites; recursive delegation does not repair that local omission.

## XGBA build and independent review obligations
For reproducible generated map IDs, map tables and expansion-aware tooling, track both dispatcher tool enumeration and each local tool's complete dependencies, host-platform/compiler variants and output bytes. A successful recursive tool invocation is not a clean rebuild proof. Independently review all callers, `check-tools` implementation outside this file, generated outputs and clean/incremental builds. **Verdict: PENDING; reviewer: none; approval contribution: 0.**
