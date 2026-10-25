# Phase 1 v2.7 — final-ELF resolution of compiled external references

**Verified:** [Passing compiled FireRed source/ELF job](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40189756147). [Permanent checksummed v2.7 release](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.7). Both variants use the same immutable FireRed commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.

**Gate:** `FAIL_INCOMPLETE` for comprehensive per-file semantic signoff. No source file is marked approved purely from compiler symbols.

## Linker and external-reference reconciliations

Every one of the **946** object-level symbol references without an internal compiled provider match has been classified against the actual final ELF and the consuming object's relocation table:

| Outcome | Classic agbcc | Modern GCC |
| --- | ---: | ---: |
| Reference names that exist in the final linked ELF | **479** | **399** |
| Names absent from final ELF and **not referenced by object relocation records** | **34** | **34** |
| References absent from final ELF **but requiring a relocation** | **0** | **0** |
| Total reviewed external/linker symbol sites | **513** | **433** |

The nine distinct absent names in each build are six map connection constants (`CONNECTION_NORTH`, `SOUTH`, `EAST`, `WEST`, `DIVE`, `EMERGE`) and `STR_VAR_1`, `STR_VAR_2`, `STR_VAR_3`. These originate in original assembly/source conventions. The [pinned map macro source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/asm/macros/map.inc#L137-L153) defines directional connection aliases with `.equiv`; the compiled-object check establishes that the remaining undefined symbol names **do not have corresponding relocation references**. They therefore do not prove outstanding final-link errors or missing XGBA dependencies.

For the other **878** symbol reference sites, presence in the linked ELF verifies the binding name and address, **not the exact library/archive object selected**. Many involve compiler arithmetic helpers, ARM/Thumb interworking veneers, `memcpy`, `memset`, and other library/runtime functions. Actual helper behavior and third-party ABI upgrades remain outside this proof.

## Why this matters to future XGBA plugins

- Don't mistake an undefined symbol in an intermediate `.o` file for an unresolved reference in the final ROM.
- The correct confidence ladder is **source symbol → compiled object → relocation evidence → final linked ELF binding → verified runtime role**. We have evidence for the first four, but not path-complete proof for all runtime roles.
- A changed compiler runtime can alter helper implementations and relative addresses without changing Pokémon source revisions. Re-run ABI preflight and runtime tests before patching.
- The v2.7 archive extends [v2.6's 402,287 compiled symbol entries and 1,298 source-linked object files](PHASE1_STATUS_v26.md); it does not change the 29,068 historical/candidate mapping register or imply complete semantic review.

**Remaining completion blocker:** file-by-file semantic dispositions and the demonstrated resource lifecycle/pointer/relink tests are not independently approved. `tools/firered_external_symbol_reconciliation.py` remains reproducible and fails on incomplete or mismatched source provenance.
