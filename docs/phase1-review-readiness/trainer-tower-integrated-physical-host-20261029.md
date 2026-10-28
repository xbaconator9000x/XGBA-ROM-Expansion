# Phase 1 — original FireRed paired CEReader and physical-sector wrapper execution (2026-10-29)

**Partial integration evidence; not a complete-file disposition.** Phase 1 gate FAIL_INCOMPLETE; independent approvals 0/14,834.

## Reuse and source identities

Reuse unchanged pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, specifically `src/cereader_tool.c` Git blob `395be0bcbed8454e645a9f5670cde3024eda508e`, `src/save.c` Git blob `36b960f375c92711aa49b99bdfe9c6b3a99d6b1c`, and `include/cereader_tool.h` blob `5cb5a9ebc32db23de07800ccce124bcb28d3ef15`. No replacement Flash driver, editor, linker, serializer, upstream patch or ROM is produced. Preserve the original save-sector ABI and the original split of 3,976/3,968 bytes.

## New dependency closure and controls

This test connects the **unchanged extracted original C functions** for CEReaderTool producer/consumer, validation and both special-sector save wrappers in **one compiled host executable**. The test-only physical-sector shim represents sectors 30 and 31, tracks writes, simulates a second write failure and flips sentinels. The positive test checks both physical sentinels and a complete 7,944-byte roundtrip, followed by a failed second-sector update, mixed-generation checksum rejection *after destination mutation*, successful retry, first-sector sentinel failure with unchanged destination, and second-sector sentinel failure with first-half destination mutation.

Six source-semantic and eight output mutations must fail closed. The harness pins source commits and blobs before extraction, and CI archives text-only results. This is new integrated function evidence beyond prior independent CEReader-only and special-sector-only host experiments.

## Unresolved limits and interoperability

This is **host C with a fake Flash backend**, not original-agbcc compiled ARM execution, mGBA, physical Flash timing, or an observed stock gameplay transaction. The original `ReadTrainerTowerAndValidate` returns FALSE, so the stock external path remains blocked; the simulated failure does not establish player reachability. Further work requires actual original-agbcc ARM/mGBA execution and independent whole-file review. Confirm applicable upstream licensing before redistribution; absent root license does not authorize copying assets. Never increment semantic approvals on the strength of this test.
