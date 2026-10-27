# Phase 1 P0 — FireRed map-script type 6 is implemented as a conditional dive fallback

**27 October 2026 · EXACT-PINNED SOURCE CALL-CHAIN · NOT APPROVED.** FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. This extends the Poryscript/map-script and Porymap/FireRed connection investigations. **Phase 1 FAIL_INCOMPLETE; independent approvals 0/14,834.** Source-callable is not equivalent to authored gameplay reachability.

## Exact source identities and anchors

| Exact pinned file | Git blob SHA-1 | Role and lines |
| --- | --- | --- |
| `include/constants/map_scripts.h` | `1353de360cf1e00b6efbb26ec59c4822c99b59bf` | 4–10, type 6 annotated `Unused` |
| `src/script.c` | `d0433bdda062b138e53d1a1d3184b4566ad7d9dc` | 382–406 map table reader; 458–461 type-6 wrapper |
| `src/overworld.c` | `339014da46ae8543143edc99ab72bf7496203a0d` | 508–514 reset; 661–668 fixed warp; 706–747 connection-first fallback |
| `src/field_control_avatar.c` | `b1b6465941133b927505be92d189a7c283e4722f` | 1118–1161 dive/emerge callers |
| `src/scrcmd.c` | `97b695ee2f6fca80a3b78f52f6a444f696fe5814` | 831–841 script command writer |
| `asm/macros/event.inc` | `142ad979d7d3093244087a247fa2b4883424f77f` | 487–495 documented `setdivewarp` opcode `0x40` |
| `data/script_cmd_table.inc` | `c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1` | 68 dispatch table slot `0x40` |
| `tools/mapjson/mapjson.cpp` | `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5` | 155–159 optional map-header connection pointer |

## DIVE-001 — `Unused` annotation does not mean the runtime ABI is free

The constant header defines `MAP_SCRIPT_ON_DIVE_WARP = 6` and annotates it `Unused`. Yet `RunOnDiveWarpMapScript` in `src/script.c:458–461` passes **that exact type** to the normal five-byte map-script table reader. `SetDiveWarp` in `src/overworld.c:722–738` first searches for a native connection of the requested dive/emerge direction. If one exists, it uses that connection directly. **Otherwise** it calls `RunOnDiveWarpMapScript`, rejects the still-dummy fixed warp, and uses `sFixedDiveWarp` if a script populated it.

This fallback has a matching script-side writer: `setdivewarp` emits opcode **0x40** (event.inc:487–495), dispatches to `ScrCmd_setdivewarp` (script_cmd_table.inc:68), reads map group/number, warp ID and VarGet-resolved coordinates, then calls `SetFixedDiveWarp` (scrcmd.c:831–841; overworld.c:661–668). `ApplyCurrentWarp` resets `sFixedDiveWarp` to a dummy after applying a warp (overworld.c:508–514). `field_control_avatar.c:1118–1161` calls `SetDiveWarpDive` and `SetDiveWarpEmerge` under diveable/underwater metatile conditions.

**Compatibility requirement:** retain type **6** and opcode **0x40** as implemented ABI surfaces even if current authored content does not use the symbolic type. Do not recycle type 6 merely because of the comment. This is a source-level executable control-flow path, **not** evidence that a particular stock map has a type-6 entry or that gameplay executes it.

## DIVE-002 — the fallback has a separate map-header pointer precondition

`GetMapConnection` reads `gMapHeader.connections->count` **before** testing whether its `connections` list pointer is null (overworld.c:706–713). `SetDiveWarp` calls it before trying the script fallback. But `mapjson` writes a **null map-header connection pointer** when a map has no included connections, including `connections_no_include=true` (mapjson.cpp:155–159). Thus, for a map with a null connection-header pointer, this local call chain has a **source-level null-dereference hazard before the fallback**. Whether an actual caller can reach this condition on stock data, or whether surrounding gameplay state prevents it, requires a separate caller/compiled/runtime proof. A map with a non-null cardinal connection list but no matching dive/emerge direction can enter the fallback without that specific null-header precondition.

This is distinct from `GetIncomingConnection` in `src/fieldmap.c`, which has build-conditional `UBFIX` null checks. A compatibility layer must preserve the different caller preconditions and avoid treating all native connection selectors as interchangeable.

## DIVE-003 — authored-content absence and required tests

The pinned-source checker `tools/phase1_firered_dive_fallback_contract.py` validates **seven exact Git blobs**, the conditional call order and **14 fail-closed source mutations**. It also scans pinned `data/maps/*/scripts.inc` files for the symbolic `MAP_SCRIPT_ON_DIVE_WARP` token. A zero result would establish only the absence of that **symbolic spelling in those authored files**, not the absence of numeric type-6 records, external scripts or a possible runtime path. The workflow `.github/workflows/phase1-poryscript-firered-abi.yml` runs it alongside the existing Poryscript/FireRed source checker and archives JSON evidence. [Exact-head CI #40428716567](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40428716567) **passed** at `ce6065993a1f10d0297702cd579c74ce16f878f4` ([artifact #12700597868](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40428716567/artifacts/12700597868), SHA-256 `080aa3eac400af3450794e32361d821a69b2cc79d95d540527636c55c074c617`). The checker verified **7 pinned blobs, 14 source anchors and 14 negative controls**, scanning **425 authored `scripts.inc` files** and finding **zero symbolic `MAP_SCRIPT_ON_DIVE_WARP` occurrences**. This is a source-level absence of that spelling, not proof that raw numeric type-6 records or runtime use are impossible.

To close the gate: verify the authored table's actual type-6 entries (including numeric/raw encodings), source-level caller and header-pointer preconditions, assembled script/connection records, dive/emerge runtime transitions, fixed-warp lifetime and save-state interaction under both compiler variants. Independently review complete affected source files. **No runtime certification or independent approval follows from this dossier.**

**Disposition: type-6 fallback and opcode-0x40 writer source-closed; stock authored reachability, null-header safety, compiled bytes, runtime and independent review OPEN. Phase 1 FAIL_INCOMPLETE.**
