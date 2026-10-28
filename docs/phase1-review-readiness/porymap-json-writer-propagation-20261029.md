# Phase 1 — Porymap six JSON writer result-propagation audit (2026-10-29)

**Status: PENDING exact-head CI; FAIL_INCOMPLETE; independent approvals 0.**

## New source-level finding, separate from prior native GUI proof

The previously green full pinned Qt GUI experiment in PR #27 verified a **real failed map.json Save**: private \`QFile::error()\` was 4 before and after close, yet \`Project::saveMap\` returned apparent success and cleared the map's dirty flag. This packet **does not repeat that GUI experiment**. Instead, it traces the same unchecked \`OrderedJsonDoc::dump\` → \`QFile::close\` → success pattern through **six source-level Project writers**, then follows the existing failure propagation into \`Editor\` and \`MainWindow\`. The five additional paths are **potentially vulnerable by source inspection only**; no real I/O failure has been executed for those five.

Pinned \`huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116\`, immutable blobs: \`src/project.cpp\` \`d43b0949303433111d4478ad76117c2b3445dd13\`, \`src/editor.cpp\` \`34112f6355b13d9381de7188624c36e5efeba151\`, \`src/mainwindow.cpp\` \`08ce1a7a599ef825967717b69626984cdc6d772b\`. No upstream source is changed.

| Project function | QFile handle | Source result | Native failed-save evidence |
| --- | --- | --- | --- |
| \`saveMapLayouts\` | \`layoutsFile\` | dump → close → true without post-dump error check | Not tested |
| \`saveMapGroups\` | \`mapGroupsFile\` | dump → close → true without post-dump error check | Not tested |
| \`saveRegionMapSections\` | \`file\` | dump → close → true without post-dump error check | Not tested |
| \`saveWildMonData\` | \`wildEncountersFile\` | dump → close → true without post-dump error check | Not tested |
| \`saveHealLocations\` | \`file\` | dump → close → true without post-dump error check | Not tested |
| \`saveMap\` | \`mapFile\` | dump → close → map setClean → true | **Yes**, separate PR #27 Qt GUI evidence |

Each of these writers has an initial \`QFile::open(QIODevice::WriteOnly)\` failure guard. That does **not** guarantee that a subsequent dump or close succeeded. \`Project::saveGlobalData\` checks the boolean returns of five global writers, \`Project::saveAll\` checks \`saveMap\` and \`saveGlobalData\`, \`Editor::save\` propagates these booleans, and \`MainWindow::save\` displays an error only when the propagated result is false. A falsely successful writer therefore bypasses the already existing UI failure reporting. The checker requires the actual pinned source chain, rejects nine deliberate source-semantic mutations and six output-evidence mutations. This is partial-function coverage, not six complete-file dispositions.

## Mandatory maximum-reuse decision

**Do not build a replacement JSON serializer, map editor or project model.** The existing \`OrderedJsonDoc\`, \`Project\`, \`Editor\`, \`MainWindow\`, \`QFile\` and Qt \`QSaveFile\` APIs are the natural integration points. Phase 2 should investigate the smallest upstream-compatible change that checks actual persistence success **before** clearing dirty flags, propagates failure through existing booleans, and avoids partial replacement of an existing file. Consider Qt's existing \`QSaveFile\` transaction API rather than a home-grown atomic file writer, but do **not** assume it is drop-in compatible: check serializer device signature, file-watcher notifications, backup/retry, filesystem permissions and all six writer callsites. Preserve current successful save semantics and Save Project recovery. This is a review recommendation, not an implemented fix.

## Unresolved review requirements

1. Execute controlled write failures against each of the other five native Qt writer paths, including their callers and disk snapshots; do not extrapolate the one observed map failure.
2. Verify whether other JSON/text/asset writers outside these six have equivalent unchecked I/O.
3. Assess \`QSaveFile\` compatibility with \`OrderedJsonDoc\` and Porymap's file watcher, and distinguish failed flush, failed close and failed atomic commit.
4. Determine which existing Qt upstream APIs or adapters can preserve the project format without introducing a new editor or serializer.
5. Obtain independent whole-file semantic review for all affected source identities. No self-approval.

**Accounting:** zero new complete-file dispositions, zero independent approvals. All Phase 1 gates remain \`FAIL_INCOMPLETE\`; Phase 2 untouched.
