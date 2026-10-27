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

## Exact authored null/empty and active-order classification (compiled run #40421156293)

The [passing pinned run #40421156293](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40421156293), at workflow commit `e5608c5a2735f1bef681b164b182deb812573776`, resolves the critical remaining distinction from the previous coverage run:

| Connection field in 425 pinned `map.json` files | Count |
| --- | ---: |
| Nonempty connection arrays | **63** |
| Explicit `null` | **362** |
| Explicit empty arrays `[]` | **0** |
| Missing field | **0** |

All **63 nonempty maps are the exact 63 explicitly ordered names**; all **362 omitted maps have `connections: null`**. The pinned `generate_map_connections_text` returns a single newline for null, rather than a connection count/pointer table. The optimized executable's order of the **63 nonempty maps exactly matches the authored explicit order**, and the synthetic control preserves that same nonempty relative order. Nevertheless the **full 425-name include sequences differ**, and the debug-iterator build still aborts on the unmodified authored input.

**Narrowed native-risk assessment:** for these specific pinned inputs, the sort discrepancy appears confined to the placement of 362 null-connection includes, which emit no connection records, while all nonempty connection includes preserve their relative order. This materially reduces the evidence for a *native connection-data layout difference* from the comparator bug in this exact build. It does **not** prove identical `maps.o` or ROM bytes: assembler state, include alignment, other generated files and linker placement still require direct compiled comparison. The C++ iterator operation remains undefined and fails under the actual debug-iterator toolchain.

## Native FireRed `maps.o` byte comparison — modern GCC (passing run #40421312981)

The controlled [passing native build #40421312981](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40421312981) at workflow commit `acd2ab3b99d50982b3aa2d3d296763133ed4a264` compiled the **same exact pinned FireRed checkout** with `GAME_VERSION=FIRERED MODERN=1`, first with unmodified authored `map_groups.json`, then after replacing **only** the `connections_include_order` array in the disposable checkout with the original 63 names followed by the 362 omitted names. The original source pin and JSON blob were checked **before** the first build. The second build was incremental, using the same toolchain and object path; build logs, generated includes, both object files and a JSON comparison were archived.

| Generated artifact | Authored input SHA-256 | Synthetic completed-order SHA-256 | Comparison |
| --- | --- | --- | --- |
| `data/maps/connections.inc` | `3c2ef81589d9bf09784350da0714a8a07d891c795c00024cdb1da5ea743e98cf` | `7c6201e043905d641bb0bc9c22af54ed428044ec707f675f8697179a63d3d960` | **Different** |
| Native `data/maps.o` | `1b52f4efdb9c7125e5860af211f8097882f2dadc6ee0d997a020945c1cd4ef98` | **same SHA-256** | **Byte-identical** |

**This closes the native modern `maps.o` comparison gate for this one pinned input and one compiler/build configuration.** The C++ iterator bug remains genuine: debug-iterator execution aborts on ordinary authored input. The optimized generated include text differs, but because the 362 reordered omitted maps are null-connection maps, their changed placement did **not** change the native compiled map object in this controlled modern build. The result does not establish linked ROM equivalence, original agbcc/revision-10 equivalence, behaviour under other source inputs (especially explicit empty arrays), Porymap editor round trips, or independent approval. Do not generalize the object identity beyond this exact pinned source and toolchain configuration.

## Dependency and interoperability implications

The confirmed defect is in the **build-time source producer**, not a demonstrated ROM-side runtime crash. The pipeline is authored `map_groups.json` → `generate_connections_text` → generated `connections.inc` → `data/maps.s` → `maps.o` → native ROM map connection data. The global include sort can change the placement of per-map records. Per-map `connections` array iteration (generator lines 188–209) and map group/index ID allocation (lines 522–562) are separate channels; this compiled experiment confirms the four other generated outputs are unchanged by the synthetic order completion.

Porymap round-trip compatibility still requires preserving authored map identity, mirrored connection semantics, per-map connection array order, `connections_no_include`, and the distinction between source-project records and compiled header pointers. Native map pointers and map-header lookups have not been checked in a linked ROM here.

## Remaining fail-closed gates

1. **Resolved for pinned input:** all 362 omitted maps contain explicit `null`, no omitted map has an empty array, and the optimized output retains the exact authored relative order of all 63 nonempty maps. Re-run this classification on any future source pin.
2. **Modern `maps.o` comparison complete:** original and synthetic order produce byte-identical native objects in pinned modern build. Still inspect linked ROM and original agbcc/revision variants; do not infer these from one object hash.
3. Run alternative compilers/standard library configurations and sanitizers as available; one GCC 13 debug-iterator abort is not a universal compiler outcome.
4. Verify actual map transition, editor import/export and save/asset regression boundaries separately.
5. Obtain **independent whole-file semantic review** for each affected pinned file; this document is an analyst dossier, not an independent approval.

**Disposition:** Full pinned generator debug-iterator failure with ordinary authored data is **CONFIRMED** on GCC 13.3.0; release generation succeeds but its source comparator has undefined iterator arithmetic. This is stronger than the earlier minimal fixture. No Phase 2 implementation, no new independent approval, no semantic completion credit. Phase 1 remains `FAIL_INCOMPLETE`.
