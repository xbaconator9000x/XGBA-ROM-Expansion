# Pinned mGBA ROM-memory semantic-index pilot

**Status: source-index evidence only.** This pilot does not create whole-file semantic dispositions, approvals, an emulator modification, or expanded-ROM compatibility evidence.

## Reproduce

From the XGBA repository root, provide an extracted source tree from the immutable mGBA archive at `fd9dc5c2cbf234365068855851107e762fc6211b`:

```sh
python tools/phase1_mgba_memory_semantic_pilot.py \
  --mgba-source-root /path/to/mgba-fd9dc5c2cbf234365068855851107e762fc6211b \
  --firered-source-root /path/to/pokefirered-ce6406d8c2eaf46d543c8a2606de0c3cb1951982
python -m unittest discover -s tests -p test_phase1_mgba_memory_semantic_pilot.py -v
```

The generator checks the original compressed dossier archive, queue and gate Git blob identities; validates all 14,834 canonical dossier records; and binds each selected source file's Git blob and SHA-256 to its original dossier. It then verifies pinned source anchors, direct include/build-manifest/linker-selection edges, test-source presence and license notices before emitting deterministic JSON:
[`mgba-rom-memory-semantic-index-pilot-20261101.json`](mgba-rom-memory-semantic-index-pilot-20261101.json).

The original machine dossier for upstream `LICENSE` has a null `source_content_sha256`. The output preserves that null rather than fabricating a dossier hash; the generator independently checks the pinned license Git blob and tracked byte count. The other six selected dossiers contain and match their source SHA-256.

## Pilot coverage and boundaries

The bounded pilot indexes **9 file records**: four mGBA ROM-window/load/memory files, the GBA CMake source/test manifest, the existing GBA core test source, the pinned mGBA MPL-2.0 `LICENSE`, and the pinned FireRed original `Makefile` plus `ld_script.ld`. It maps five source/test observations and six direct-include, build-membership or linker-selection edges. The observations cover the 32 MiB ROM-window constants, shared backing for ROM waitstate selectors, the loader/patch size boundary, the registered `loadNullROM` test, and the FireRed linker's ROM placement/build padding contract. The test only checks null-ROM rejection; no existing test source in this pilot tests the alias or 32 MiB/32 MiB+1 boundaries. Test source presence is not test execution.

The generator fails closed on changed source blobs, changed dossier/snapshot identities, absent test evidence, ungrounded or unverified documentation claims, and missing MPL-2.0 license evidence. Its six unit tests include those negative controls. Upstream documentation references are listed for future context only: retrieval was unavailable in this run, no document claim is used to support a pilot invariant, and the links are not immutable source pins.

**Safe-generation count:** 9 of 9 explicitly allowlisted source/test/license/build identities are verified in this pilot. This is not a projection over the other 14,825 files; their safe coverage remains unestablished. The FireRed linker/Makefile records provide source context only: no XGBA expanded-ROM build or binary placement is verified. Porymap/Poryscript are not dependencies of this cartridge-window contract and remain covered by the separate reuse matrix. No mGBA native test or build, stock gameplay, save/restart, physical Flash, or combined-distribution license clearance is claimed. mGBA package-specific MPL obligations and FireRed distribution rights remain to be assessed before distribution.

The output preserves the authoritative `FAIL_INCOMPLETE` gate, 338 P0 candidates and 14,834-file inventory, with **zero** added whole-file dispositions and **zero** approvals. Existing Copilot receipt records are not changed.
