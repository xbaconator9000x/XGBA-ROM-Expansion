# Current authoritative Phase 1 checkpoint — 26 October 2026

**Decision: FAIL_INCOMPLETE. No XGBA unlimited ROM architecture has been implemented or runtime-certified.** This status overrides the old "latest v2.6" heading retained below for historical continuity.

- **Immutable mapping baseline:** 14,834 tracked files across five pinned repositories, 4,685 source/config content blobs verified, 14,834 machine-generated source-hash-pinned dossiers, 338 P0 review candidates. **Independent whole-file semantic dispositions approved: 0/14,834.** The [machine mapping gate](../semantic-snapshots/current/phase1_mapping_gate.json) remains fail-closed.
- **Native emulator regression:** [mGBA CI run #40204719637](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40204719637) executed 34/34 passing synthetic-ROM tests, reproducing 4 unsafe native behaviours (prefetch staleness, unchecked physical mapping extent, warning-only savestate ROM CRC, external bank resource drift during restore).
- **Fail-closed test evidence verification:** [CI run #40205086061](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40205086061) independently verified all 34 required named checks, test source SHA, log/summary consistency, all four hazardous observations and 10 negative fixtures. Its verdict is **PASS_PINNED_NATIVE_MGBA_REGRESSION_ONLY**, *not* a Phase 1 mapping completion decision.
- **Source-anchored design constraints:** [External bank identity and safety contract](PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md) and [original 25-test baseline](PHASE1_NATIVE_MGBA_25_TESTS_PASS_2026-10-26.md). mGBA native Matrix supports only a 26-bit (64 MiB) physical bank offset, cannot provide unconstrained storage and is not an XGBA replacement.
- **Editor interoperability P0 review:** [Porymap/Poryscript source-anchored authoring ABI](PHASE1_P0_PORYMAP_PORYSCRIPT_AUTHORING_ABI_2026-10-26.md) pins raw 16-bit map blocks, configurable tile/collision/elevation masks, source-vs-generated script labels and lossy import hazards. [Compiler-backed reference verification source](../tools/porymap_block_semantic_reference.py) models all 65,536 default-mask words and now defines **19** malformed-input rejection fixtures (up from the historical 10); [strictness evidence](PHASE1_PORYMAP_STRICT_ADAPTER_CHECKPOINT_2026-10-26.md) and [binary-view boundary evidence](PHASE1_PORYMAP_MEMORYVIEW_BOUNDARY_2026-10-26.md) document the changes. [Prior Porymap CI run #40209978387](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40209978387) completed successfully **before** the memoryview update; the 19-fixture revision has not yet been verified by a resulting workflow. **Reference model, not a certified Qt editor round trip.**
- **Native FireRed map/script ABI semantic trace:** [Pinned producer→linker→script interpreter→save-data contracts](PHASE1_P0_FIRERED_MAP_SCRIPT_POINTER_ABI_2026-10-26.md) source-interprets map mask/tileset attribute distinctions, finite virtual map buffers, direct code/data/function pointer operands, Poryscript/Porymap dataflow and a conditional original `SavedMapViewIsEmpty` out-of-bounds read. The default original `MODERN=0` source selects the 512-entry read on a 256-entry array; `MODERN=1` defaults to `UBFIX` and the bounded `NELEMS` path. [Build-attached source variant checker](../tools/firered_map_view_variant_semantics.py) is under [verified compiled CI run #40212095204](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40212095204), **source branch check PASS**. Independent whole-file review remains pending.
- **Script execution lifetime P0 review:** [FireRed direct script PC, return stack and six call-opcode paths](PHASE1_P0_FIELD_SCRIPT_RETURN_STACK_LIFETIME_2026-10-26.md) traces a **19-successful-push limit** in a 20-address array plus `ScriptCall` continuing after a failed `ScriptPush`. [Pinned verifier](../tools/field_script_stack_lifetime_semantics.py) requires exact Git source hashes and seven negative control mutations. **Earlier compiled CI run #40212610996 failed in the audit tool's C function-definition matcher**, after both FireRed compiler variants built successfully. The [failure diagnosis and synthetic matcher regression checkpoint](PHASE1_FIRERED_TYPED_MATCHER_CI_REGRESSION_2026-10-26.md) records corrective commits and 3 positive/4 negative fixtures; [subsequent compiled-variants CI run #40217148233](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40217148233) **passed** with compiled ABI evidence artifact 12608227355. This is source-level candidate interpretation, not emulator proof or whole-file signoff.
- **Curated whole-file semantic review queue (source-interpreted, not signed off):** [29 pinned high-risk source files across all five upstream repositories](../semantic-snapshots/curated/p0_semantic_review_candidates_2026-10-26.json) now have explicit per-file semantic roles and unresolved review obligations, distinct from the 14,834 machine-generated generic dossiers. [Cross-repository source-identity verifier](../tools/verify_curated_p0_semantic_registry.py) verifies each Git blob and runs five false-approval negative controls. [Census run #40214802383](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40214802383) **passed**; [nested checker trigger checkpoint](PHASE1_NESTED_CURATED_CENSUS_TRIGGER_CHECKPOINT_2026-10-26.md) records newly covered verifier/registry push paths, with [new census run #40222453857](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40222453857) **in progress** at inspection. **0 independently approved dispositions**. The historical 25 source assertions remain unchanged, with [16 additive P0 assertions](../tools/verify_p0_additive_source_contracts.py) archived separately.
- **Artifacts and procedures:** `tests/mgba_bank_boundary.c`, `tests/run_pinned_mgba_boundary.sh`, `tools/verify_native_mgba_regressions.py`, `tools/compiler_bindings_semantics.py`. Source revision SHA, test code SHA, full logs and a test-result JSON are preserved by the existing `compiled-mgba-semantics.yml` CI workflow. Preserve chronological evidence; never overwrite pinned snapshots or mark a source file reviewed by machine-only evidence.

**Next required work:** source-grounded per-file semantic dispositions with independent review and exact evidence/contract SHA; finish remaining P0 cross-engine prefetch, peripheral, compiled ABI, script/editor producer obligations; design versioned opt-in XGBA sidecar with checked bounds, exact resource identity, atomic remap semantics, emulators/editors fallback, and negative controls. Runtime expansion remains outside Phase 1.

---

# Latest verified checkpoint: v2.6

[**Read the current Phase 1 v2.6 status and compiled ABI evidence**](PHASE1_STATUS_v26.md). The cumulative source and mapping work is preserved across v2.5 and earlier releases. **Phase 1 semantic signoff remains FAIL_INCOMPLETE.**

---

# Current Phase 1 checkpoint — v2.5

**Status: INCOMPLETE — no release-ready XGBA runtime.**

The actively maintained source-map checkpoint is [v2.5](PHASE1_STATUS_v25.md). Five immutable source repositories, both FireRed compiler variants and native mGBA/Porymap build evidence are preserved. All 14,834 pinned files are inventoried, 39,530 function-scope dossiers are generated, and the native ROM/save/graphics/bytecode limits are source linked. Automated dossiers are not semantic approvals. The fail-closed Phase 1 gate still requires independent file dispositions.

[Latest verified permanent archive — v2.4](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/releases/tag/phase1-semantic-v2.4) · [v2.5 save/ABI status](PHASE1_STATUS_v25.md)

---

# Current status: v2.0

The latest verified semantic evidence and remaining completion requirements are in [PHASE1_STATUS_v20.md](PHASE1_STATUS_v20.md). Prior v1.8 and v1.5 sections below are historical. **Phase 1 is NOT complete.**

---

# Phase 1 checkpoint — v1.5 (2026-10-25)

**Decision: FAIL_INCOMPLETE. Phase 1 source mapping has not received independent semantic approval.**

## Verified GitHub Actions evidence
- [Successful 5-repo source audit, second-pass dossiers and mapping gate](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40159337299).
- All **14,834** tracked files from five pinned upstream Git revisions are inventoried.
- All **4,685** source/config files have been read and Git-blob SHA checked.
- **14,834** machine-generated, hash-pinned per-file dossiers; **0** independently approved file dispositions.
- **5,711** lexical candidate occurrences; **8,315** symbol candidates.
- **13,729** include syntax references: **8,676** single-path candidates, **62** ambiguous, **4,991** unresolved. Provisional unresolved classes: **2,384** standard library, **1,015** Qt, **230** generated, **155** platform/third-party, **698** local basename hypotheses, **509** unknown.
- Heuristic review queue: **338 P0**, **1,297 P1**, **8,658 P2**, **4,541 P3**. Priorities are not semantic signoffs.

## Source mapping register (v1.5)
- Original **11,024** mapping entries source-reconciled: **0 missing paths, 0 blob hash mismatches, 0 revision mismatches**.
- **4,315** novel source-line lexical candidates appended from the complete census, with original IDs untouched.
- **13,729** typed include-reference candidates appended as a separate dependency class.
- Combined **29,068** register records spanning **2,631** different files.
- 500-record checkpoints at **11,500–29,000**. New entries explicitly state candidate-only status.
- The 29,068 mapping register is a **candidate discovery and provenance index**, not 29,068 approved semantic findings.

## Source-backed constraints
See [new v1.5 contracts](CRITICAL_SOURCE_CONTRACTS_v15.md) for save-state identity, ROM remap sequencing, raw script bytecode execution, and FireRed save-block relocation/encryption.

## Validation
- GitHub Actions evidence pipeline: SUCCESS.
- Fail-closed Phase 1 mapping gate: FAIL_INCOMPLETE, **0/14,834** independent signoffs.
- Offline local integration tests: 11/11 PASS.
- Preserved v1.4 offline tests: 18/18 PASS.
- No XGBA emulator/ROM expansion patch or end-to-end runtime tests have been implemented.

## Persistence and next step
The reproducible pipeline is committed to this repository. The complete 11.5MB mapping workpack generated in ChatGPT must be copied to `imports/XGBA_Phase1_v1.5_Complete_Workpack.zip` for permanent GitHub persistence; the connected GitHub API cannot import a local binary attachment automatically. [Import workflow](../.github/workflows/import-workpack.yml) verifies each ZIP entry SHA256, the 29,068 record counts, and the non-completion status when the archive is uploaded.

Once imported, continue ranked semantic review, source/asset dependency proofs, versioned adapter contracts and independent per-file approvals. Phase 2 compilation/runtime/compatibility checks are a separate release gate.

Do not count initial source scans, guessed paths, or unsigned dossiers as completed semantic review.
