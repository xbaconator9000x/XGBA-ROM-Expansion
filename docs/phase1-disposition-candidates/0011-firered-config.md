# Phase 1 whole-file analyst candidate 0011 — FireRed build configuration

**State: PENDING_INDEPENDENT_REVIEW.** Source-grounded analyst preparation, not independently approved and not counted by the authoritative semantic gate.

## Exact upstream identity
- Repository: `pret/pokefirered`
- Pinned commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`
- Whole path: `config.mk`
- Git blob SHA: `c07d31fc083fa341cca29c340e560ed107d5364a` (verified from the pinned upstream file response).
- [Entire source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/config.mk); [linker/build consumer trace](../PHASE1_P0_FIRERED_LINKER_VARIANTS_2026-10-26.md).

## Entire-file semantic inventory
1. **Overridable defaults:** `GAME_VERSION ?= FIRERED`, `GAME_REVISION ?= 0`, `GAME_LANGUAGE ?= ENGLISH`, `MODERN ?= 0`, `COMPARE ?= 0`, `KEEP_TEMPS ?= 0`. These are Make conditional assignments, not unconditional enforcement of build settings.
2. **Goal-triggered overrides:** if `MAKECMDGOALS` equals `modern` *exactly*, `MODERN := 1`; if it equals `compare` *exactly*, `COMPARE := 1`. This equality does not by itself prove what happens for multi-goal invocations or externally supplied variable overrides; those must be checked with Make and the consuming Makefile.
3. **Fixed assignments:** `MAKER_CODE := 01` (commented as `gbafix` input) and `BUILD_DIR := build`.
4. **Version branch:** `GAME_VERSION=FIRERED` assigns `TITLE := POKEMON FIRE`, `GAME_CODE := BPR`, `BUILD_NAME := firered`; `LEAFGREEN` assigns `POKEMON LEAF`, `BPG`, `leafgreen`. Any other version invokes Make's `$(error unknown version ...)`.
5. **Revision suffixes:** `GAME_REVISION=1` appends `_rev1`; `GAME_REVISION=10` appends `_switch`. Other revision values are not rejected locally and append neither suffix. The separate conditionals do not both fire for the same ordinary scalar revision value.
6. **Compiler suffix:** `MODERN=1` appends `_modern` to the build name after any revision suffix. The file alone does not select compiler flags or the linker script; the consuming Makefile does.
7. **Language suffix:** `GAME_LANGUAGE=ENGLISH` appends `E` to `GAME_CODE` (so defaults give `BPRE`). For non-English values, **this file does not append any suffix or issue an error**. Do not infer that all other languages produce valid headers or that `GAME_LANGUAGE` is ignored elsewhere.

## Dependency and XGBA implications
- Makefile consumers determine whether `MODERN`, `GAME_REVISION`, `GAME_VERSION`, `GAME_LANGUAGE`, `TITLE`, `GAME_CODE`, `MAKER_CODE`, `BUILD_NAME` and `BUILD_DIR` actually select distinct source/assembler flags, linkers, `gbafix` arguments or binary output paths.
- Cross-reference `constants/version.inc` for assembler version/language symbols, `ld_script_modern.ld` for modern ROM/RAM placement, and both legacy scripts for revision-specific placement. A build-name suffix or game-code field is not proof of a compatible ROM format.
- A future XGBA manifest must capture the **effective expanded Make variable set, compiler/linker variant and final binary/header identity**; the default `?=` values alone are insufficient.

## Evidence class, exclusions and independent review
- **Verified:** full pinned file and exact Git blob; all branches, assignments, defaults and error clause described above.
- **Unverified:** actual Make evaluation across command-line/environment/multi-goal cases, downstream `gbafix` bytes, alternate-language and revision build outcomes, editor recognition, compiled/runtime compatibility.
- Reviewer must independently validate every branch and consumer, inspect relevant Makefile invocation rules, and record identity/date/verdict before gate ingestion.
- Reviewer identity/date/verdict: **not supplied / pending**. No independent approval claimed.

**Phase 1 remains FAIL_INCOMPLETE; independent whole-file approvals 0/14,834.**
