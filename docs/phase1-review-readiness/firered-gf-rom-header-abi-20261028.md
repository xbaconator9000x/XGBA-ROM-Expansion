# Phase 1 P0 — FireRed's second ROM header: GF resource and save-layout ABI

**28 October 2026. Source-grounded whole-file review preparation only; independent signoff 0/14,834.** This packet is intentionally isolated from the main XGBA Phase 1 worker and the Flash/save review PRs. It does not change any upstream source, build, emulator, or Phase 2 implementation.

## Immutable, complete inputs

All five inputs are from `pret/pokefirered` at commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; the verifier retrieves their complete bytes and checks the actual Git blob identity.

| File | Git blob SHA-1 | Role |
| --- | --- | --- |
| `src/rom_header_gf.c` | `60696d810a8154c350fa293104477638061bc5c9` | Entire GF header structure and static initializer |
| `src/rom_header.s` | `c98c89992a128b82ef3bc8f75c791cd1c6cbdcb9` | Separate cartridge boot/header layout |
| `Makefile` | `8b454dbd18eb0069fa5851d788697190890a5b37` | Legacy/modern linker selection, gbafix, ELF→GBA |
| `ld_script.ld` | `9a4b45031e93c1e1da8186d8c697332710526048` | Legacy placement of `rom_header_gf.o(.text*)` |
| `ld_script_modern.ld` | `e930243522bd21da40cc1a05de9a42b8ad409b46` | Modern `*(.text*)` placement |

## Whole-file semantic preparation and architecture consequences

The complete `src/rom_header_gf.c` contains eight header includes, one `struct GFRomHeader` with **74 unique members**, and one `static const` instance with **74 uniquely initialized members**. Its initializer contains **75 textual designators** only because `gameName` is initialized separately under the mutually exclusive `#ifdef FIRERED` and `#else` branches. A naive designator counter would falsely report a duplicate field.

This GF header is **not** the 192-byte GBA boot header. `src/rom_header.s` reserves 156 bytes for the Nintendo logo and separate game-code/checksum fields, which the Makefile's `gbafix` step populates. The GF header instead embeds version/language, resource-table pointers, counts, save block sizes, and layout offsets. The source explicitly places it in `.text.consts`, selected by both the legacy object-specific `.text*` linker rule and the modern wildcard `.text*` rule. Actual linked addresses, survival through garbage collection, and third-party discovery of this table require ELF/map and external-consumer evidence.

**Save-layout dependency:** 19 GF header members use `offsetof(struct SaveBlock1/SaveBlock2, ...)`; three use `sizeof(struct SaveBlock1/SaveBlock2/EnigmaBerry)`. This is a compiled layout-description contract, not a fixed constant independent of build flags. Both `unkFlagOffset` and `unkFlagOffset2` point to `SaveBlock2.unkFlag2` in the pinned source. That duplicate target is an observed alias, **not** an established bug. The header also contains direct pointers to species, moves, items, icons, sprites, palettes, names, and other ROM resources; a future address-translation/sidecar design cannot assume these fields become automatically bank-safe.

## Reviewer obligations and limitations

1. Verify both actual linked ELF variants: complete field sizes, packing, endianness, pointer widths, final GF header address, and location relative to the cartridge header.
2. Trace all external consumers (including tools and any GameCube/communication compatibility) before treating this GF table as a stable public ABI. This packet proves no consumer reads it.
3. Compare compiled `SaveBlock1`, `SaveBlock2`, `EnigmaBerry` and table-pointer layouts under the supported build variants, and determine migration requirements if any field moves.
4. Trace resource producers and relocations, especially ROM pointers that would cease to be directly addressable under an external-storage architecture. Test with negative and boundary cases.
5. Obtain actual independent whole-file review, authenticated provenance, and the separate required compiler/emulator/editor evidence before approval.

## Reproducibility and accounting

`python3 tools/phase1_firered_gf_rom_header_abi.py --output phase1-evidence/gf-rom-header-abi.json`

The verifier checks complete pinned Git blobs, 74-member declaration/initializer coverage, both conditional names, all 19 offset targets and three size targets, cartridge-header distinction, both linker rules, and the build producer chain. Ten source-mutation negative controls must fail. This is a proposed complete-file analysis packet, **not a new registered prepared disposition**. The official baseline remains 113/14,834 registered substantive candidates (0.7618%), 0/14,834 independently approved (0.0000%), 14,721 distinct historical source-verified machine-triage records, and 14,834/14,834 inventoried (100%). No gate counts are changed.

**Gate: `FAIL_INCOMPLETE`. No Phase 2 changes.**
