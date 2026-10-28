# Phase 1 P0 — full pinned Porymap Qt Project save/reopen and write failure experiment

**Status: EXPERIMENT PENDING / FAIL_INCOMPLETE.** This dossier specifies a reproducible full-project Qt test; it does not claim the test has passed or confer independent semantic approval.

Source pins: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116` and real `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` source project. The workflow validates Porymap `src/project.cpp` blob `d43b0949303433111d4478ad76117c2b3445dd13`, `src/core/map.cpp` blob `47b279919bd4afcc76b88f9eeecd459b3452989f` and `src/lib/orderedjson.cpp` blob `4d3a460c652541371a01132116e508db8c4c872c`, then executes the existing six-blob source boundary checker from draft PR #14.

Unlike the earlier isolated `OrderedJsonDoc::dump` /dev/full witness, this test builds the **entire pinned Porymap Qt application** with a test entrypoint substituted for `src/main.cpp`. It loads an isolated copy of the real pinned FireRed source project through `Project::load`, loads PalletTown, modifies an existing map connection offset, calls **actual `Project::saveMap`**, reads the resulting `map.json` and independently reopens the full project to verify the connection survived. It then makes a second dirty connection change, redirects the same map.json pathname to Linux `/dev/full`, executes the same `Project::saveMap` path, restores the original on-disk file, and checks the return status, dirty flag and persisted content. The experiment must fail closed if the full Qt project cannot load, the on-disk round trip fails, or the negative device cannot be injected.

Expected source-level risk (NOT yet a runtime result): the pinned writer returns true and clears `Map::setClean()` without inspecting the JSON writer's buffered write/flush error, potentially losing an edit after failed persistence. The observed result must come from CI, not this prediction. The test does not simulate GUI click handlers, crash consistency, editor conflict merges or XGBA expansion behavior. No raw ROM or user data are uploaded.

Machine-triage count remains **0 newly indexed files**, shortfall **1,000** from the target; historical 14,721/14,721 triage pool exhausted. Newly registered complete-file reviews **0**, historical analyst-prepared candidates **113** pending register verification, independent approvals **0**. Every Phase 1 gate **FAIL_INCOMPLETE**; Phase 2 untouched.

## Actual MainWindow GUI save pathway (new pinned experiment; results pending)

This additional harness builds the **complete pinned Porymap Qt application** with a separate test entrypoint. It instantiates the real `MainWindow`, real `Editor` and actual `Project`, loads the pinned FireRed PalletTown and Route1 maps, installs the same `Project::mapLoaded -> MainWindow::onMapLoaded` signal connection used by `MainWindow::openProject`, and triggers the **real QAction** `action_Save` and `action_Save_Project`. The project is attached through the public `Editor::setProject` API (not the private GUI open-project dialog); the two actions are explicitly enabled because that dialog was bypassed. No save function is patched. A positive test requires mirrored connection offset changes to dirty both maps, current-only save to persist PalletTown but not Route1, and Save Project to persist the Route1 mirror. A negative test injects `/dev/full` at PalletTown's map.json path, triggers the actual current-map QAction again, and checks the dirty flag, mirror dirty state and restored on-disk bytes. This extends PR #27's standalone Project proof to the real GUI handler and signal chain, without pretending to test a human mouse click, crash consistency or all editor features.

Pinned source Git blobs: `src/mainwindow.cpp` `08ce1a7a599ef825967717b69626984cdc6d772b`, `src/editor.cpp` `34112f6355b13d9381de7188624c36e5efeba151`, `src/core/mapconnection.cpp` `d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4`; all at `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. The test operates on a separate isolated FireRed project copy. Results must be read from **exact-head CI** before any runtime claim. All Phase 1 gates remain `FAIL_INCOMPLETE`, no independent approval.

## GUI crash reproduced and harness corrected — source/CI evidence

The first GUI build failed to compile at [CI #40597008309](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40597008309): the test took a C++ pointer to private `MainWindow::onMapLoaded`. The next build compiled but [CI #40597487850](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40597487850) segfaulted. Instrumented [CI #40597962299](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40597962299) reproduced it after `Editor::setMap` and mirror lookup. Its actual gdb stack: `QString::operator=` → `MainWindow::updateMapList` → Qt signal dispatch → `MapConnection::setOffset` → test main. The test bypassed `MainWindow::openProject`, including `setProjectUI`/map-list initialization; this is a **harness setup defect**, not proof of a defect in Porymap's normal GUI path.

The corrected harness configures a temporary recent-project entry and calls real `MainWindow::initialize` → private `MainWindow::openProject` through the application's own startup flow, including actual `Project::mapLoaded` wiring and `setProjectUI`. It no longer directly attaches a Project or manually enables save actions; it **asserts** the real GUI actions are enabled after project open. Both mirrored-connection positive tests and injected `/dev/full` negative test remain, with gdb fallback on failure. Results pending exact-head CI. Pinned upstream Porymap sources are unchanged.

## GUI recent-project config identity correction

[CI #40598356756](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40598356756) failed closed because the real `MainWindow::initialize` did not open the configured project; no GUI save result was claimed. The test created the Porymap recent-project config **before** the `MainWindow` constructor assigned the application's canonical name `porymap`. Qt's `QStandardPaths::AppDataLocation` is application-name dependent, so the test had written under the test executable's name while `MainWindow::initWindow` reloaded from the canonical app name. The corrected test sets organization `pret` and application name `porymap` **before** loading/saving the recent-project config, asserts persistence and logs the post-initialize recent path and flags. This is harness setup only; no pinned upstream source is modified. GUI success still requires exact-head CI.

## Post-failure Save Project retry: on-disk mirrored-connection integrity (new test pending)

This follow-up extends the **actual** pinned MainWindow GUI QAction harness, not the isolated serializer. After a successful mirrored PalletTown/Route1 save, it injects `/dev/full` into a second PalletTown current-map save. The previously green CI established that the failed current-map save clears PalletTown's dirty state while leaving the Route1 mirror dirty. The new experiment then triggers the **real Save Project QAction a second time**, observes the on-disk connection offsets of *both* maps, and tests whether they remain reciprocal.

The test requires the remaining dirty Route1 mirror to persist its second offset and records whether PalletTown's incorrectly cleared dirty state causes a **durable inconsistent map-connection pair**. It accepts either a source-backed recovery (both disk offsets reciprocal) or a reproduced inconsistency (PalletTown still old, Route1 new), but cannot label the latter as verified before exact-head CI. It does not patch the pinned application or claim crash consistency. The pinned Porymap `src/mainwindow.cpp` blob `08ce1a7a599ef825967717b69626984cdc6d772b`, `src/editor.cpp` `34112f6355b13d9381de7188624c36e5efeba151`, `src/core/mapconnection.cpp` `d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4` remain unchanged.

**Review question:** Does Save Project iterate only dirty maps or all loaded maps after an unsuccessful current-only save? Can the editor silently persist nonreciprocal connection offsets? This is a partial subsystem test; all Phase 1 gates remain `FAIL_INCOMPLETE` and independent approvals zero.

## First post-failure retry CI and observation-timing repair

At `8d68348fa1b65581d317374c8e7354c86d2f93f9`, [CI #40604243040](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40604243040) **failed**, but the full pinned Qt application executed the new GUI retry and emitted a valid runtime result: after `/dev/full` failure, **Save Project persisted both PalletTown offset +2 and mirrored Route1 offset −2**, leaving no divergent disk pair and both maps clean. This agrees with pinned `src/project.cpp` blob `d43b0949303433111d4478ad76117c2b3445dd13`, lines 1315–1326: `Project::saveAll` saves **all loaded maps**, not only dirty maps. It does not erase the earlier verified hazard: the failed current-only save still returned apparent success and cleared its dirty flag before any retry.

The CI assertion failed because the new harness populated the JSON field `failed_gui_save_disk_offset` **after** Save Project retry, reading the repaired offset +2 instead of the original post-failure offset +1; it compared this to in-memory +2 and incorrectly concluded that the earlier mismatch was absent. This is a **harness measurement timing bug**, not a Porymap product failure. The correction captures the failed-save disk snapshot **before** triggering Save Project and preserves separate post-retry fields. Do not claim this new commit green until exact-head CI passes. All Phase 1 gates `FAIL_INCOMPLETE`, zero independent approvals.

## Isolated-map failed GUI Save → real MainWindow close (pending exact-head CI)

The previous green mirrored-connection test left Route1 dirty after the
PalletTown `/dev/full` failure, so it could not determine whether
`MainWindow::closeProject` would warn when the **only** edited map's dirty
flag had been falsely cleared. Pinned `src/mainwindow.cpp` blob
`08ce1a7a599ef825967717b69626984cdc6d772b` checks
`Project::hasUnsavedChanges()` before displaying the SaveChangesMessage,
and `MainWindow::closeEvent` delegates to `closeProject`. Pinned
`src/project.cpp` blob `d43b0949303433111d4478ad76117c2b3445dd13`
checks loaded maps/layouts and project data flags. Pinned
`src/core/map.cpp` blob `47b279919bd4afcc76b88f9eeecd459b3452989f`
has `Map::setClean` clear `m_hasUnsavedDataChanges`.

The new full pinned Qt GUI test follows the already green Save Project retry,
then changes a PalletTown-only custom attribute and marks only that map
dirty. It asserts that Route1 remains clean, injects `/dev/full` for the
real current-map QAction, verifies the actual on-disk JSON stayed unchanged
and the unsaved attribute never reached disk, checks map and project dirty
flags, and finally invokes `QWidget::close()` to exercise the actual
`MainWindow::closeEvent -> closeProject` chain. A project that is still
dirty causes the test to fail closed **before** invoking a modal close
dialog; no automatic dismissal or invented GUI result is permitted.

**Pending:** this is a source-grounded test design, not a verified
no-prompt-close result until the exact-head CI passes. The harness invokes
QAction and QWidget::close programmatically, not a physical mouse click.
All Phase 1 gates FAIL_INCOMPLETE; independent approvals zero.

## First isolated close-path CI: actual Qt result, stale harness assertion (2026-10-28)

At `a9515c0c8f8f554bdf730be2910ca3865910e797`,
[CI #40616686720](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40616686720)
**failed**, but the full pinned Qt application compiled and executed all
new GUI stages. Its native `PHASE1_GUI_RESULT` reported that an isolated
PalletTown-only `/dev/full` current-map Save left the physical JSON
unchanged while **both map and project dirty flags became false**,
and `QWidget::close()` accepted the actual MainWindow close event.
No Route1 mirror was dirty in this case.

The job then failed a **stale Python harness assertion** expecting two
current-map QAction triggers; the new isolated-map scenario correctly
raised that count to three. This was a CI verifier bookkeeping defect,
not an upstream Porymap compile or runtime crash. Because the exact-head
job failed, the new GUI result is **observed but not yet green-certified**.

The follow-up adds a stronger positive control: first save the isolated
custom attribute successfully through the same real GUI QAction and
assert it appears in physical `map.json`, then change its value and
inject `/dev/full`. The second value must not appear on disk, while the
previous value remains. The workflow now asserts all new result fields
and the updated four-action count, rather than accepting a JSON record
without checking the new evidence. Await its own exact-head CI.
