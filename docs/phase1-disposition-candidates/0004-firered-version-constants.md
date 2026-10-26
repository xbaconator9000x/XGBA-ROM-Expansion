# Phase 1 semantic disposition candidate 0004 — FireRed assembler version constants

**Disposition state: PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** Entire-file source analysis only. The authoritative Phase 1 gate remains `FAIL_INCOMPLETE`, with **0/14,834** independently approved whole-file dispositions.

## Exact pinned identity
- Repository: `pret/pokefirered`; commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Entire source: [`constants/version.inc`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/constants/version.inc); exact Git blob SHA-1: `c5bef93d867c66816f73616e0136125c5aca6cd7` (checked against the pinned upstream file response).
- Direct source consumers/producers inspected: [`src/crt0.s`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/crt0.s), blob `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14`; [`Makefile`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/Makefile), blob `8b454dbd18eb0069fa5851d788697190890a5b37`; [`config.mk`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/config.mk), blob `c07d31fc083fa341cca29c340e560ed107d5364a`.
- The source's complete 13-line scope has **two independent conditional blocks**, no includes, data emissions, executable instructions, labels, functions or storage declarations.

## Whole-file conditional semantics
1. `.ifdef FIRERED` defines assembler symbol `GAME_VERSION = 4`; its `.else` defines `GAME_VERSION = 5`. There is no explicit `LEAFGREEN` test in this file: **any build without `FIRERED` takes the 5 branch**, whether or not `LEAFGREEN` was defined.
2. `.ifdef ENGLISH` defines `GAME_LANGUAGE = 2`. Only when `ENGLISH` is absent does its `.else` test `.ifdef GERMAN`, defining `GAME_LANGUAGE = 5` when present. **Neither defined leaves `GAME_LANGUAGE` undefined in this file**; both defined selects English's value 2. There is no unconditional default, validation or error branch in this include.
3. The `.equiv` declarations are assembler-time symbol definitions, not runtime variables or ROM layout records. No address or byte layout follows from this file alone.

### Exhaustive branch truth table (source interpretation, not an assembled test)
| FIRERED defined | ENGLISH defined | GERMAN defined | GAME_VERSION | GAME_LANGUAGE |
| --- | --- | --- | --- | --- |
| yes | yes | either | 4 | 2 |
| yes | no | yes | 4 | 5 |
| yes | no | no | 4 | not defined here |
| no | yes | either | 5 | 2 |
| no | no | yes | 5 | 5 |
| no | no | no | 5 | not defined here |

## Build and cross-file dependency interpretation
- `Makefile` sets `ASFLAGS` to include `--defsym $(GAME_VERSION)=1` and `--defsym $(GAME_LANGUAGE)=1`, so the assembler's actual conditional branch depends on resolved build configuration. `config.mk` defaults to `FIRERED` and `ENGLISH`, and rejects game versions other than `FIRERED` or `LEAFGREEN` in its own build-name branch. **That config guard is not present in `version.inc`**.
- `src/crt0.s` directly includes `constants/version.inc`; this confirms an assembly dependency, **not** which downstream symbols are referenced or whether all flag combinations assemble successfully.
- `config.mk` derives cartridge title, game code and build name separately. Do not equate the assembler `GAME_VERSION` and `GAME_LANGUAGE` numeric values with the final ROM header bytes without inspecting their consumers and post-link processing.

## Expansion relevance and independent-review obligations
An XGBA-compatible toolchain must preserve build-variant symbol interpretation when comparing source, linked ELF and cartridge bytes; a missing or conflicting define could change source branches without changing this file. This is a build-identity dependency, **not** evidence of a larger ROM address space or a usable bank selector.

Before any whole-file approval, an independent reviewer must: (a) independently confirm exact pinned bytes and all six logical branch cases; (b) enumerate references to both emitted symbols across pinned assembler, generated assets and linker inputs; (c) test actual assembler behaviour under normal FireRed/LeafGreen and deliberately conflicting/missing language defines; (d) reconcile build config, final ELF and post-link ROM header transformations; and (e) record a distinct reviewer identity, date, evidence and disposition in the authoritative gate's supported format.

**Verified now:** entire pinned source, blob identity and cited Makefile/config/CRT0 declarations. **Not verified:** assembled truth-table fixtures, all consumers, resulting cartridge bytes, editor interoperability, runtime behaviour, independent reviewer signoff.

**Checkpoint: candidate 0004 prepared; independently approved 0/14,834 (0.000%). Phase 1 FAIL_INCOMPLETE.**
