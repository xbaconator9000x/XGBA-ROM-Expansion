# Phase 1 — original FireRed root Makefile generated Poryscript object (2026-10-29)

**Status: exact-head CI pending; FAIL_INCOMPLETE; independent approvals 0/14,834.** This is not a whole-file disposition or a Phase 2 implementation.

## New boundary, distinct from the already-green isolated Makefile fixture

The earlier PR27 executable test built Porymap's default .pory using a minimal test-only Makefile and separately invoked FireRed's native preprocessing pipeline. This new test instead executes the **original pinned FireRed root Makefile** and its **real data/event_scripts.o target** after applying only the existing Poryscript README's documented generation rule in a disposable detached source checkout. The full original data/event_scripts.s is preserved with one appended test-only include. The source checker pins all original commits/blobs and rejects fifteen source-semantic mutations.

Exact upstream identities: pret/pokefirered ce6406d8c2eaf46d543c8a2606de0c3cb1951982, Makefile blob 8b454dbd18eb0069fa5851d788697190890a5b37, data/event_scripts.s blob 88d75946a7300ccf952f4a36c283966c6aebf5c0, tools/preproc/preproc.cpp blob 20c2de51b635a5d59f2b4e1ecd93d8fc2748ebe1; huderlem/poryscript c32481161c767b25a3425fa9f1f8729927ff3d55, README blob c77e022eb86e74a41b184daac5953d14c72cacc3; huderlem/porymap 26b919d7ff4b54152de010abd5bf344af2ebe116, src/project.cpp blob d43b0949303433111d4478ad76117c2b3445dd13.

## Mandatory maximum reuse

Use the existing Porymap default map script, existing Poryscript Go CLI and documented AUTO_GEN_TARGETS/data/%.inc rule, original FireRed root Makefile and preproc, C preprocessor and GNU ARM assembler. No replacement compiler, assembler, editor or exporter. The test requires root Makefile's generated target to discover the new script; executes root make to generate scripts.inc and compile build/firered/data/event_scripts.o; verifies the generated map-script symbol with GNU ARM nm; and records only SHA-256 identities and JSON. It requires unchanged input to avoid regeneration, removal of the rule to fail, malformed input to fail and recovery to reproduce identical bytes. Twenty-eight evidence mutations must fail closed.

The test modifies the **disposable checkout's working tree only**, restores the original Makefile and event_scripts.s in finally, and never commits or distributes upstream assets. Original upstream commits remain unchanged.

## Limitations and reviewer obligations

Even if CI passes, this is an original-root-build **object-level** integration, not a complete FireRed ROM link, real Porymap GUI new-map save, mGBA native map-script reader execution, malformed-table safety, or crash-consistent multi-file transaction. It does not address the native Trainer Tower special-sector transaction. The root Makefile may expose unanticipated dependency or tool ordering; preserve failure logs and fix only the actual failing assumption. Poryscript's pinned license is MIT, Porymap's inspected root is LGPL-3.0, and other upstream code/assets/toolchains require component-specific licensing review before distribution.

**Reviewer questions:** Does the root build retain the generated dependency in every build configuration? Can the real editor GUI save and reopen a new map with Poryscript mode? Are malformed records bounded in actual mGBA ARM execution? Do all relevant whole-file source identities receive independent review? No approvals are added here. All Phase 1 gates remain FAIL_INCOMPLETE.

## 2026-11-04 exact-head failure diagnosis and scoped build repair (CI pending)

PR run [#41850711284](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41850711284), job `126702199587`, failed at the original-root integration step in `make -qp NODEP=1`. The verifier rejected exit 2 at its return-code assertion; pinned FireRed Makefile line 161 raises that error when its parse-time `$(MAKE) -f make_tools.mk` bootstrap fails. The earlier verifier included only the final 1,500 bytes of captured stderr and discarded stdout, so the exact failing tool/compiler diagnostic was not present in the Actions job log. A diagnostic-only follow-up prints both captured streams, but its push run `#41870642628` and PR run `#41870656189` are `action_required` with zero jobs; no new diagnostic-bearing execution is available yet.

The successful exact-head runs [#40738376717](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40738376717) and [#40738391158](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40738391158) used `ubuntu-24.04`, `build-essential 12.10ubuntu1`, and `libpng-dev 1.6.43-5ubuntu0.7`. The failing run used `ubuntu-26.04`, `build-essential 12.12ubuntu2.26.04.2`, and `libpng-dev 1.6.57-1ubuntu0.1`. This establishes runner/toolchain environment drift between the successful and failing runs, but does **not** identify which incidental helper-tool compilation emitted the hidden diagnostic.

The test now disables the root Makefile's unrelated `SETUP_PREREQS` bootstrap only for the parse query and explicitly selected test targets. It still builds the pinned Poryscript CLI and the exact pinned FireRed `tools/preproc` target; the original root Makefile's generated target, Poryscript rule, and `build/firered/data/event_scripts.o` recipe remain exercised. `tools/preproc/Makefile` is now pinned as an additional dependency (blob `606318944c63673ec2488bb2f89712a1cc4e4950`). A regression control invokes that unchanged Makefile with a test-only compiler that emits a unique marker and fails; the strict command wrapper must reject it and preserve the diagnostic. This does not whitelist new Make exit codes or suppress failure from a required tool build.

The root query continues to accept only GNU make's documented `-q` statuses 0 and 1; exit 2 remains rejected. The new exact-head run must pass before this repair is considered runtime-verified. CI, this dossier, and the synthetic tool-build negative do not confer independent approval; Phase 1 remains FAIL_INCOMPLETE, 0/14,834.

## 2026-11-04 exact-head missing map-event header failure (repair pending CI)

PR run [#41927912652](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41927912652), attempt 2, job `126919997308`, step 7 `Execute original root Makefile generated target and data/event_scripts.o`, actually failed at commit `8fd2619144b92655fbd46dec0893313717fae74c`. The failed command was:

```text
make NODEP=1 SETUP_PREREQS=0 build/firered/data/event_scripts.o
```

Its assembler/preprocessor pipeline stopped because `data/event_scripts.s` includes `include/constants/event_objects.h`, which includes the absent `include/constants/map_event_ids.h`. This is a missing prerequisite in the **test harness**, not evidence of a defect in the immutable FireRed source. The root Makefile normally runs `make generated` during parse-time setup when `SETUP_PREREQS=1`; setting it to `0` deliberately skipped that generation, and `NODEP=1` also disables scanned `.d` dependency inclusion. Therefore compiling the selected object alone did not create its generated header dependency.

The repair keeps those scoped flags and builds the pinned FireRed `tools/mapjson` using its original Makefile. It then invokes the original root rule directly:

```text
make NODEP=1 SETUP_PREREQS=0 include/constants/map_event_ids.h
```

Pinned provenance added to the checker/workflow: `map_data_rules.mk` blob `b32b85a91d9460642345ca983c37d165e820741f` declares the generated target and rule `$(MAPJSON) event_constants firered $^ $(INCLUDECONSTS_OUTDIR)/map_event_ids.h`; `include/constants/event_objects.h` blob `9d8c514f9e2d634d40d215bf657f33041c55c28e` consumes that header. The original `tools/mapjson/Makefile` blob `100e809c6c27e6c04d3b6f2406ff288922d80c13` builds the pinned `mapjson.cpp`, `json11.cpp`, and `mapjson.h` inputs. Their blobs are checked as well: `mapjson.cpp` `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5`, `mapjson.h` `6e961a28ec0e2c6a017e7dda2e9d81f07e3e3ceb`, `json11.cpp` `fcacdbeb39c3110e4564f57a8f26b7bb34678a7e`, and `json11.h` `c04c4362f9784006c7a45ad04729fab1c77dd1d9`.

The harness first requires the generated header to be absent in the fresh checkout, then requires the original root target to generate it from all pinned map JSON inputs. It deletes only that generated output and reruns the same rule (absent-output regeneration control); it also ages the generated file's mtime without changing contents, requires the original Make rule to regenerate the stale output, and checks byte-identical recovery. Both controls use the pinned `mapjson` executable and original FireRed rule; no generated header contents are hand-authored. The resulting evidence reports the exact root target/command, input count, a SHA-256 manifest of input paths and bytes, generated-header SHA-256, built `mapjson` executable SHA-256, and that the generated header existed before compiling the original event object.

The additional `mapjson` dependency is still part of the pinned FireRed checkout; no package or external dependency is added. Its bundled `json11` source carries its own MIT notice. Only text evidence is uploaded; the executable and FireRed project/assets remain in the disposable runner checkout.

The repair code was pushed at `6fbbc092da451e6e316d0b44dda4e19fff331e3a`. Its exact-head push run [#41930282775](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41930282775) and PR run [#41930295902](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41930295902) both completed `action_required` with zero jobs. Thus the repair has **not** been executed by CI; the confirmed missing-header failure remains the only runtime result for this integration. Do not treat either zero-job run as verification. Phase 1 stays FAIL_INCOMPLETE with 0/14,834 independent approvals.

## 2026-11-05 second generated-header dependency and expanded original target (CI pending)

The repair advanced beyond the previous missing `map_event_ids.h` failure, but exact-head PR run [#41930529314](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41930529314), attempt 2, job `126977573777`, step 7, failed compiling the original object with:

```text
data/event_scripts.s:7:10: fatal error: constants/layouts.h: No such file or directory
make: *** [Makefile:346: build/firered/data/event_scripts.o] Error 1
```

Pinned `data/event_scripts.s` also includes the generated `constants/layouts.h`. The unchanged `map_data_rules.mk` declares that header in `AUTO_GEN_TARGETS` and generates it from `data/layouts/layouts.json` through the pinned `mapjson layouts` rule. The same file declares `map_groups.h` from `data/maps/map_groups.json`. The earlier harness invoked only the map-event target, so it had not closed the full original generated-header set before compiling the event object.

The harness now builds the pinned `preproc` and `mapjson` tools, then invokes the original root target `make NODEP=1 SETUP_PREREQS=0 generated` before the event-object build. The pinned root target covers all three original generated headers: `map_groups.h`, `layouts.h`, and `map_event_ids.h`. It requires all three to be initially absent, deletes them and requires byte-identical regeneration, then makes each older than its JSON input and requires the original target to regenerate it. The evidence records each generated-header SHA-256, its input count and path/content manifest SHA-256, plus the tool identity. Source checks and scoped source-mutation controls now include the groups and layouts target/rule/recipe and the event-script `layouts.h` include. The existing required-preproc compiler-failure negative remains active; no generated contents are hand-authored and no pinned source is modified.

This is the harness repair and source-grounded diagnosis, not a successful runtime result. The failed run uploaded no root-Make evidence artifact. Exact-head push run [#41930521496](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41930521496) also failed at the same `layouts.h` prerequisite. Runtime verification of the expanded prerequisite chain requires new exact-head push and PR jobs. Phase 1 remains FAIL_INCOMPLETE with 0/14,834 independent approvals.

## 2026-11-05 original `jsonproc` tool prerequisite (CI pending)

The expanded original `generated` target reached the JSON-backed FireRed targets and then failed in exact-head PR run [#41951099483](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41951099483), attempt 2, job `127105399134`, step 7:

```text
tools/jsonproc/jsonproc: No such file or directory
make: *** [json_data_rules.mk:6: src/data/wild_encounters.h] Error 127
```

This is another omitted prerequisite in the test setup. The original root `make_tools.mk` includes `jsonproc` among its tools, while the targeted harness had built only `preproc` and `mapjson`. The actual root `generated` target also includes JSON-derived headers from `json_data_rules.mk`; it correctly invokes the original `$(JSONPROC)` recipe and failed because the harness had not built that executable.

The harness now builds the unchanged pinned `tools/jsonproc` with its original Makefile (`make -C tools/jsonproc -j2`) after `preproc` and `mapjson` and before invoking root `generated`. It pins the connected `json_data_rules.mk`, JSONPROC Makefile, C++ source, headers, and bundled template/JSON headers by exact Git blob identity, and records the built executable SHA-256. It continues to execute and validate the original generated target and rejects genuine preprocessor build failure through the existing controlled compiler-negative test. No generated file is fabricated and no validation is disabled. The bundled Inja and nlohmann headers each contain MIT notices; this test uploads only text evidence and does not distribute those upstream sources or binaries.

The failure run uploaded no root-Make JSON artifact. Its repaired exact-head execution is still required; Phase 1 remains FAIL_INCOMPLETE with 0/14,834 independent approvals.
