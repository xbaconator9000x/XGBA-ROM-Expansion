# Phase 1 — pinned Porymap cross-file transaction and rollback boundary

**Status: NEEDS_EVIDENCE until exact-head CI succeeds; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This package is an original pinned Project/Qt experiment, not a product fix or complete-file review. It adds no upstream Porymap change and does not repeat the prior MainWindow watcher-permission package.

## Immutable dependency matrix

Porymap is pinned at `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`; FireRed is pinned at `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. The verifier checks each Git blob and full-byte SHA-256. The JSON artifact includes the complete machine-readable matrix and this dossier's exact SHA-256.

The new dependency closure is deliberately limited to map reload, event/script parsing, configuration path selection, and the actual FireRed inputs/outputs. Central Project/serializer sources are included only as reused writer anchors; their earlier evidence is not counted as new source coverage.

| Repository / pinned path | Git blob | Full-byte SHA-256 | Producer → consumer edge |
|---|---|---|---|
| Porymap `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | `225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b` | Reused `saveMap`, text helpers, `saveMapGroups`, and `saveAll` writer anchor |
| Porymap `include/project.h` | `50d3307cf618f4cd5e9603bdbe3e0ea8d9b5e354` | `7cc2225207fe2ddbbc463b91f24997f651141d84f7a79f3d8897daf6071c9b51` | Reused Project save API declarations |
| Porymap `src/lib/orderedjson.cpp` | `4d3a460c652541371a01132116e508db8c4c872c` | `a6acaf57872aa3bfc2fc98b02b743e550bead19cc85cf298c642c50a5f3f75ae` | Reused JSON serialization boundary |
| Porymap `include/lib/orderedjson.h` | `cb5139d37d955f2469ebd2eaaf089668b82884fe` | `06af4ab35f09263aa213673dbdca5640b840fddfb22f7e8fc35dc41ad91fdaa2` | Reused QFile-based serializer API boundary |
| Porymap `src/core/map.cpp` | `47b279919bd4afcc76b88f9eeecd459b3452989f` | `c2406bb2dd5950ee226a4e7fc8e1d198c70915cb638fd706a814b87de22ab332` | Script path selection, parser call, watcher invalidation and re-registration |
| Porymap `src/core/mapheader.cpp` | `689a52dc16a5cc5eea96e7c94924fd1f95a5c5b5` | `75ac866909595164cb242e0b8a13149b218a85546a2ddd6ca8baf59f79b74806` | Map-header setters used when persisted JSON is reloaded |
| Porymap `src/core/events.cpp` | `194a7ab17096d754295990e649a0c5c3ab816c78` | `36a5fadf65a0cd0b70ce02acef717aae60ac77052cd9f6f2bdfb56ed17cab886` | Event objects cloned into and reconstructed from map JSON |
| Porymap `src/core/parseutil.cpp` | `a1c3e69daed3f04d7ed64e1a34bd95db56137ae2` | `7c9e4028c74555c7b27b7fb6e3d255f406d8303277989887f69ddf8a44ece441` | Original `.inc` / `.pory` script-label parser used on reopen |
| Porymap `src/config.cpp` | `9264f99bb18e0a725ef023f514c00df529d1d28d` | `fe8b6e3e4780ae8a63321d157d6fea43f438af3ab7a7fc697a9f9a2b43d4419d` | Project path defaults and FireRed script/text mode |
| Porymap `include/config.h` | `539c5f3d416d22d847020cd324726b33725e5437` | `2a7a2621675e70b007fbc71f004a3cb0c44914f0a9c366ab974570ca8e2053ad` | `ProjectFilePath` keys join config paths to project assets |
| FireRed `data/event_scripts.s` | `88d75946a7300ccf952f4a36c283966c6aebf5c0` | `3b1bd10d26c0a74fb3452ab42fc9d14dfca785f8b71389db06c71f5dfdd50a27` | New-map writer's shared include append target |
| FireRed `data/maps/map_groups.json` | `8c382f504d208286161903244772c93138cd7662` | `ce296c9b54c8bb85cc35870b30a533ab017e72107fd40cf471224a42127af79a` | Original `saveAll` map-group output required for cold reopen |
| FireRed `data/maps/PalletTown/map.json` | `802d32dc6de7688fe2de8c833d4e040d9137f6c1` | `2816338934241bac34f52dae8b101ac3add59e0ebdde3e3fb6575f3b525b01c3` | Pinned map fixture cloned by the test |
| FireRed `data/maps/PalletTown/scripts.inc` | `1384b7d6c6bb5d2b93538ebaf5e92defde2d41e5` | `ca9ae01d210ebfeda42895a152145940b7c444a03b6416b26353ceb0adac9190` | Pinned assembly-script consumer fixture |
| FireRed `data/maps/PalletTown/text.inc` | `726aea8c67812ef2bc72e51b2d8ee38e21fd4863` | `6fe28872b8f6ad72ad26dc64a6f6922258cf187f5efb40dfeddc9e2d1f2469b2` | Pinned text-script consumer fixture |

Porymap's pinned root `LICENSE.md` has Git blob `65c5ca88a67c30becee01c5a8816d964b03862f9`, SHA-256 `da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768`, and LGPL-3.0 text. The bundled OrderedJson source/header have separate MIT/Dropbox notices. No root `LICENSE`, `LICENSE.md`, `COPYING`, or `COPYING.md` exists in the pinned FireRed tree; this is not a licensing or redistribution determination.

Poryscript pin `huderlem/poryscript@c32481161c767b25a3425fa9f1f8729927ff3d55`, `README.md` blob `c77e022eb86e74a41b184daac5953d14c72cacc3`, SHA-256 `d7aa099a6bcdd43745e746527589907d3cd4cd4b3db109319ccf8c609dec36f3`, is recorded as **not exercised**. This run requires the pinned FireRed Porymap mode to select raw `.inc` scripts; the separate existing Poryscript generated-include evidence is reused, not repeated.

## Native test and transaction boundaries

The existing pinned native Qt Project harness is extended; only its test entrypoint replaces Porymap `src/main.cpp`. It uses a disposable copy of the real FireRed tree, creates four synthetic maps, and calls the unchanged Porymap `Project` methods. No human GUI interaction is claimed.

| Boundary | Injected condition and observed state | Rollback / reopen assertion |
|---|---|---|
| Script output | A matched Qt `/dev/full` failure prevents the first new-map script while `map.json` and the shared include persist; a retry skips the missing script. | The original Project is reopened in a second OS process; script absence and the persisted map/include state are checked. |
| Map JSON output | Making `map.json` a directory causes two original `saveMap` open failures after script/text creation and include appends. | Removing the obstruction allows a real third save; duplicate includes remain and the new map is published by original `saveAll`. |
| Shared include output | The test temporarily redirects `data/event_scripts.s` to `/dev/full`; syscall tracing must observe a >1-byte `ENOSPC` write after the case marker. Script, text, and map JSON still persist, their map is clean, while their include is absent. | Before/after bytes and device/inode of the original event file must match after test-fixture restoration. |
| Partial append | `RLIMIT_FSIZE` limits the original append to exactly eight bytes; syscall evidence must show a larger write request returning eight. `saveMap` still reports persisted/clean. | The test fixture truncates its appended prefix, then requires exact prior bytes and device/inode. This is harness cleanup, **not application rollback**. |
| Script `QSaveFile` | In the cold process, a new-file control in the same read-only directory must fail with OS `EACCES`; `QSaveFile::commit` must fail with `RenameError` and leave existing script bytes/inode unchanged. A succeeding commit must replace the inode. | The original map script watcher must report replacement invalidation; a subsequent original script read must re-register it and observe a further change. |
| Fresh Project state | Original `saveAll` writes the persisted map group after mixed new-map outcomes. | A separate native process opens the same project and loads all four maps, checks their JSON/script/text state and uses Porymap's original script-label parser. |

The strict verifier rejects mutations to every pinned source file, every transaction/cold-reopen assertion, and trace conditions for missing stage, wrong errno, wrong file, and altered partial byte count. The previous new-map retry verifier remains intact and continues validating its original record.

## Scope and limitations

- Labels: **native** means unchanged pinned Porymap Project/Map/Qt code in CI; **synthetic** means test-created map names and injected failures; **host filesystem** means Linux runner observations.
- `QSaveFile` is used by the test harness and is not represented as Porymap's writer. The Porymap map/event/script writers continue to use their pinned original implementations.
- `/dev/full`, `RLIMIT_FSIZE`, and permission changes do not model every filesystem or operating system. The transaction's partial append is restored by test code.
- The test does not inject `fsync`, claim power-loss or physical-media durability, execute Poryscript, build a ROM, or exercise the full GUI.
- Source/blob/hash checks and green CI are not independent semantic approval. No source file receives a complete-file disposition here; preserve `NEEDS_EVIDENCE`, `FAIL_INCOMPLETE`, and zero approvals.
