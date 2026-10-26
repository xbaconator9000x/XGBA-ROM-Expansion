# Phase 1 P0 — actual pinned FireRed mapjson executable confirms authored-input iterator failure

**27 October 2026 · COMPILED SOURCE-GROUNDED WITNESS · NO INDEPENDENT APPROVAL.**

This is the executable follow-up to [the source-level authored-order reachability dossier](PHASE1_P0_FIRERED_AUTHORED_CONNECTION_INCLUDE_ORDER_REACHABILITY_2026-10-27.md). It closes the *full pinned generator executable* witness gap for one GNU toolchain and the unmodified authored input. It does **not** close native assembler/linker, GBA runtime, editor round-trip, regression across compiler variants, or independent whole-file review.

## Source and experiment identity

- Exact FireRed repository commit: `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. GitHub Actions verified the checkout SHA and seven pinned file blob hashes, including `mapjson.cpp` blob `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5` and authored `map_groups.json` blob `8c382f504d208286161903244772c93138cd7662`.
- Source generator: `tools/mapjson/mapjson.cpp` lines 458–485 (sort comparator), 522–562 (independent map group/index constants), 565–587 (groups-mode producer), 675–706 (CLI dispatch). `map_data_rules.mk` lines 25–33 invokes the producer; `data/maps.s` includes the generated connections assembly; `src/overworld.c` lines 541–544 reads `gMapGroups[mapGroup][mapNum]`.
- Reproducible workflow: `.github/workflows/compiled-firered-mapjson-authored-order.yml`, passing run [#40420897444](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40420897444), pinned workflow commit `833c24877d09eb7e14dc881a4fe2b4f391aa297e`. The evidence archive contains compiler identity, stderr, exit codes, SHA-256 manifests, generated include files and JSON summary. Compiler: **g++ Ubuntu 13.3.0**.
- Normal mode: original pinned `json11.cpp` and `mapjson.cpp` built with `-std=c++11 -Wall -O2`. Debug mode: same original sources with `-std=c++11 -Wall -O0 -g -D_GLIBCXX_DEBUG`. No source modification in either executable.

## Executed results, not inferred results

| Full generator execution | Exit | Output evidence |
| --- | ---: | --- |
| Release-optimized executable + **unmodified authored** `map_groups.json` | **0** | All five generated files present; global `connections.inc` contains **425 unique per-map includes**. |
| Debug-iterator executable + **unmodified authored** `map_groups.json` | **134 (SIGABRT)** | libstdc++ `safe_iterator.h:934` reports an attempt to advance a start-of-sequence iterator **2,147,483,647 steps** outside its valid range. No generated files were written. |
| Debug-iterator executable + **synthetic completed-order control** | **0** | All five generated files present; global `connections.inc` contains **425 unique per-map includes**. |

The synthetic control appends the 362 omitted map names to the original 63-name `connections_include_order` without changing any map records or the original input file. It is **not** a claim that this is the correct production ordering fix. It tests whether eliminating the missing-name comparator branch permits the original generator to finish. The test stores the synthetic JSON beside the original input so `generate_map_constants_text` can still find its 425 sibling `map.json` files. An initial harness run [#40420828315](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40420828315) failed this control because the JSON was incorrectly placed outside that directory; the passing follow-up corrected the harness without altering pinned source.

The four outputs independent of global connection include sorting — `groups.inc`, `headers.inc`, `events.inc`, and `map_groups.h` — were **byte-identical** between the successful authored release and synthetic debug-control executions. The global `connections.inc` was deliberately **not** asserted byte-identical. It is the output under investigation. The release exit code **0 does not make its out-of-bounds iterator expression defined**.

## Follow-up authored-data coverage (compiled run #40421087366)

The follow-up [passing run #40421087366](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40421087366) at workflow commit `2bed8c378967bee3b87a6120d696d79d9a3c8ac6` inspected **every pinned per-map `map.json`** and compared the authored order against the actual generator output:

- **425 maps total; 63 with nonempty `connections` arrays.**
- **All 63 nonempty maps are explicitly present** in the 63-entry `connections_include_order`. Thus **none of the 362 omitted maps has a nonempty connection array**.
- Exactly **one nonempty-connection map** uses `connections_no_include`, and it is explicitly ordered. This is an authored header-pointer suppression flag, not evidence that the assembler necessarily omits its connection record.
- The **full 425-name release-generated include order differs** from the synthetic completed-order control, despite all four unrelated generated outputs remaining byte-identical. This confirms a visible build-time output ordering difference in this experiment; it does **not** by itself establish a linked-ROM difference.

**Critical remaining distinction:** a map with `connections: null` or a missing field yields a newline from `generate_map_connections_text`, but a map with `connections: []` can emit an empty `MapConnectionsList` plus an eight-byte count/pointer table. Therefore **zero nonempty connections among omitted maps does not alone prove their compiled includes are byte-empty**. A follow-up witness now distinguishes null/missing versus empty arrays and compares the order of all 63 active maps.

## Dependency and interoperability implications

The confirmed defect is in the **build-time source producer**, not a demonstrated ROM-side runtime crash. The pipeline is authored `map_groups.json` → `generate_connections_text` → generated `connections.inc` → `data/maps.s` → `maps.o` → native ROM map connection data. The global include sort can change the placement of per-map records. Per-map `connections` array iteration (generator lines 188–209) and map group/index ID allocation (lines 522–562) are separate channels; this compiled experiment confirms the four other generated outputs are unchanged by the synthetic order completion.

Porymap round-trip compatibility still requires preserving authored map identity, mirrored connection semantics, per-map connection array order, `connections_no_include`, and the distinction between source-project records and compiled header pointers. Native map pointers and map-header lookups have not been checked in a linked ROM here.

## Remaining fail-closed gates

1. Determine whether the 362 omitted maps contain **explicit empty arrays** rather than null/missing fields, and verify all 63 nonempty connection maps retain the authored relative order in the optimized output. An empty array may still emit an eight-byte table.
2. Inspect release-generated connection include ordering and the synthetic control ordering, then assemble/link both variants in a controlled original/modern FireRed build and compare pointer/layout bytes.
3. Run alternative compilers/standard library configurations and sanitizers as available; one GCC 13 debug-iterator abort is not a universal compiler outcome.
4. Verify actual map transition, editor import/export and save/asset regression boundaries separately.
5. Obtain **independent whole-file semantic review** for each affected pinned file; this document is an analyst dossier, not an independent approval.

**Disposition:** Full pinned generator debug-iterator failure with ordinary authored data is **CONFIRMED** on GCC 13.3.0; release generation succeeds but its source comparator has undefined iterator arithmetic. This is stronger than the earlier minimal fixture. No Phase 2 implementation, no new independent approval, no semantic completion credit. Phase 1 remains `FAIL_INCOMPLETE`.
