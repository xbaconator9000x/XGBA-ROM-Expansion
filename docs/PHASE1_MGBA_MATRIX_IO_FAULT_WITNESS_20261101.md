# Phase 1 mGBA Matrix I/O fault witness — 2026-11-01

**Status: short-read witness byte indexing corrected; exact-head native rerun pending. No semantic disposition was created.** Run #41285768620 executed the pinned fixture but failed its short-read assertion: the harness compared `uint32_t` ROM elements using byte offsets. The source-pinned implementation writes mapping metadata before the read and ignores its return value; the failed assertion did not falsify that behavior. The corrected fixture now checks destination bytes explicitly. This is a bounded follow-up to the six-file ROM-memory pilot, centered on `src/gba/cart/matrix.c`; it does not change pinned upstream source, the Phase 1 gate, audit snapshots, or any approval count.

## Immutable candidate identity

| Evidence | Identity |
| --- | --- |
| Upstream source | `mgba-emu/mgba`, `fd9dc5c2cbf234365068855851107e762fc6211b` |
| `src/gba/cart/matrix.c` Git blob / SHA-256 | `9ccbe883235b98bcf56cd609015e7b4003aa832c` / `6e47afc6992d3631d67f89cb201d7fe9784ef8a9e8dcb305c1ab5de48550ef8f` |
| Original PR2 dossier archive SHA-256 / Git blob | `c47d1fea819e7df59f67bfe8d1bc4dc2650483d03563957145f7331ed099005b` / `143c373f9aae5b9cb24af39abb7d8244362d23b5` |
| Canonical original dossier SHA-256 for `matrix.c` | `8998fbe6e0afc9b9a566c1891055f7526949b728356c125504d163eab97529aa` |
| Updated native fixture Git blob / SHA-256 | `b0900bb2ef5932d2d4d299143c2a5249297cd929` / `5c0486fb61699782849bc32776ce375e946b8cd1d7b6cf8efc02c7b4645ab743` |
| Probe suite identifier | `native_matrix_vfile_fault_controls_v7` |

The fixture injects failures only through the test's `VFile` callback wrappers after the synthetic cartridge has loaded. It leaves all original mGBA source files untouched. The test runner and live verifier compare the six upstream source pins and the updated fixture's exact Git blob and SHA-256 before accepting native results.

## Whole-file source map and bounded claims

The complete pinned `matrix.c` translation unit contains the following behavior. The table is a source map, not a claim that the source has been mapped to an XGBA implementation.

| Function | Source-grounded behavior | Remaining semantic question |
| --- | --- | --- |
| `_remapMatrix` | Rejects virtual address, size, and virtual-end values outside its Matrix constraints; calculates the mapped 512-byte slots; writes mapping metadata; then calls the ROM VFile `seek` and `read` without checking either return value. It does not check `paddr + size` against backing length. | Whether XGBA's replacement mapping validates overflow and both virtual and physical extents before changing visible mappings; how short reads and failed seeks are handled atomically. |
| `GBAMatrixReset` | Clears all mapping entries, initializes a 4-KiB size, and makes two remap calls for the default mappings. | Whether reset can leave partially updated mappings or stale CPU prefetch when a backing operation fails. |
| `GBAMatrixWrite` | Stores the command and remaps for commands `0x01` and `0x11`; masks physical address to 26 bits and virtual address to the register mask; rejects zero unit count and stores nonzero size in 512-byte units; unknown commands/offsets are logged as stubs. | Which register arithmetic, command, and invalid-input behaviors are intentionally compatible with the prospective XGBA design. |
| `GBAMatrixWrite16` | Merges low-halfword writes with the current high half of each register and delegates to `GBAMatrixWrite`. | Whether partial writes and their side effects match the target contract for every register. |
| `GBAMatrixSerialize` | Stores command, physical/virtual address, size, and all 16 mapping slots; only logs if the configured slot maximum is not 16. | Whether serialization format, bounds, and backing identity are compatible with any XGBA state format. |
| `GBAMatrixDeserialize` | Sets size to 512 bytes, restores each of 16 physical mappings and invokes `_remapMatrix` for each, then restores command/address/size fields. | Whether restore validates backing identity and all offsets before changing mapping state, and how partial restore failure is rolled back. |

The directly included headers and object-symbol records are not a complete semantic dependency graph. `matrix.c` uses the GBA, memory, serialization, VFS, ARM macros, and logging interfaces. The configured compiler build establishes selected headers for its build flags; the object-symbol report provides candidate object relationships, not call-site, callback, data-flow, or runtime closure.

## New fault witness cases

The existing fixture was extended with controlled `VFile.seek` and `VFile.read` wrappers:

1. `native_matrix_valid_physical_range_maps` is an in-bounds positive control.
2. `native_matrix_short_read_fault_injection_reproduced` asks for 512 bytes while the wrapper delegates a 511-byte read, then records whether `_remapMatrix` still commits the requested mapping and leaves the final destination byte untouched. It reads the destination through a byte pointer, matching the VFile byte count. The paired observation is `native_matrix_short_read_commits_mapping=true`.
3. `native_matrix_seek_failure_fault_injection_reproduced` positions the original memory VFile four bytes before EOF, injects a failed seek, and records whether the subsequent read still occurs and the requested mapping metadata is committed. The paired observation is `native_matrix_seek_failure_commits_mapping=true`.
4. The existing past-end physical-range case requests a 512-byte mapping with only 256 backing bytes remaining and records `native_matrix_accepts_physical_range_past_end=true`.

These are intended to characterize upstream failure behavior, not to assert safe handling. A reproduced commit after a failed seek or truncated read is a semantic hazard finding and a reason to keep the item `NEEDS_REVIEW`, never a safe-congruence pass. The native verifier now requires 37 named cases and six named observations, rejects missing/duplicate/altered records, and keeps its result classification at `PASS_PINNED_NATIVE_MGBA_REGRESSION_ONLY`.

The native run uses the existing `.github/workflows/compiled-mgba-semantics.yml`; no workflow file or permission was added. On the exact source pin and updated test source, the workflow's build runner records the case stdout/exit codes, test and source digests, Actions run/job metadata, and artifact. At this change's start the local checkout did not contain `upstream/mgba`; local native execution was therefore not attempted. The prior 34-assertion run is evidence only for the old fixture SHA and is not evidence that these new fault cases executed.

## Unresolved symbol-reference evidence

`tools/compiled_dependency_graph.py` now emits `compiled_unresolved_symbol_references.csv` alongside the existing candidate-edge CSV. Each undefined symbol reported by `nm -u` from inspected static archives is represented if there is no other in-archive provider, the provider set exceeds the enumeration limit, or the consumer source cannot be attributed. Rows carry one of:

- `NO_PROVIDER_IN_INSPECTED_STATIC_ARCHIVES`
- `PROVIDER_SET_EXCEEDS_ENUMERATION_LIMIT`
- `CONSUMER_SOURCE_ATTRIBUTION_MISSING`
- `PROVIDER_SOURCE_ATTRIBUTION_MISSING`

The summary reports the number of undefined-symbol rows and unresolved/unattributed rows. This closes the previous *report omission* for inspected archives; it does not establish final-link resolution, every CMake configuration, indirect calls, or whole repository consumer closure. Any provider outside inspected archives (such as a frontend/platform library) is unresolved from this artifact until a corresponding final-link analysis proves otherwise. Synthetic tests cover an in-archive provider, a missing provider, missing consumer and provider attribution, provider overflow, and deterministic output ordering.

## License and distribution scope

At this pinned revision, `LICENSE` is MPL-2.0 and `matrix.c` carries an MPL-2.0 file notice. In broad terms, MPL-2.0 §§3.1–3.2 impose source-availability, license-notice, and corresponding-source duties for covered source and executable distributions; §3.3 allows a larger work under other terms while preserving MPL obligations for covered software; §3.4 protects existing source notices.

The repository README describes this as a source-pinned research/test environment and says no XGBA unlimited-ROM runtime has been implemented or released. That does not determine the distribution form of a future product, and release of audit/test artifacts is not evidence that covered mGBA source or an executable containing it was distributed. The repository does not establish whether XGBA will redistribute modified mGBA source, a binary containing covered software, both, or neither. No legal or compatibility opinion is made; project-specific distribution clearance remains `NOT_ASSESSED`.

## Disposition and current blockers

`matrix.c` remains `NEEDS_REVIEW`. No receipt was created. To qualify any whole-file disposition, the project still needs: executed claim-specific fault evidence on the updated exact-head fixture; complete relevant dependency and consumer closure including final-link resolution; an XGBA-side semantic counterpart covering all functions/register cases in the source map; project-specific distribution facts and licensing clearance; and resolution of all source, dependency, prefetch, DMA/peripheral, state-restore, and compatibility objections. Historical external-review metrics and the authoritative `FAIL_INCOMPLETE` gate remain unchanged.
