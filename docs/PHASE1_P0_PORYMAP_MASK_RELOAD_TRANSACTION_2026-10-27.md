# Phase 1 P0 — Porymap mask provenance, reload ordering and settings transaction

**27 October 2026. SOURCE-GROUNDED ANALYST TRACE ONLY.** Pinned Porymap: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`. **Gate: FAIL_INCOMPLETE. Independent approvals: 0/14,834.** This resolves the specific call-order question left open in [the packed-block dossier](PHASE1_P0_PORYMAP_PACKED_BLOCK_MASK_LIFETIME_2026-10-27.md); it does not certify the Qt editor, raw ROM reconstruction or any XGBA extension.

## Immutable source identities

All Git blob hashes below were obtained by fetching the named files at the exact pinned upstream commit. Anchors are 1-based line numbers in that commit.

| Pinned file | Git blob SHA-1 | Examined dependency |
| --- | --- | --- |
| [src/mainwindow.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/mainwindow.cpp#L772-L874) | `08ce1a7a599ef825967717b69626984cdc6d772b` | `openProject`, config loading, `loadProjectData`, `setInitialMap`; reload handler at 1068–1071; settings signal at 3069–3074; close at 3275–3299 |
| [src/project.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/project.cpp#L186-L227) | `d43b0949303433111d4478ad76117c2b3445dd13` | `Project::load` order; lazy `loadLayout` at 328–349; `readMapLayouts` at 621–691; `readFieldmapMasks` at 2437–2481; config save at 1489–1494 |
| [src/ui/projectsettingseditor.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/ui/projectsettingseditor.cpp#L554-L657) | `0df96149b86694d5c95e1489493b91d646b99b98` | Settings mutation and three unchecked save results; UI mask warning at 253–278; `closeEvent` prompt and optional reload at 836–855 |
| [src/config.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/config.cpp#L215-L270) | `9264f99bb18e0a725ef023f514c00df529d1d28d` | Config reset/parse, unchecked write length, mask key parsing at 956–961 and output at 1125–1127 |
| [src/core/maplayout.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/maplayout.cpp#L576-L626) | `44616ab6c9c3ea9b04eff011586b7ec29183588f` | Lazy binary Block decode, length normalization and odd-byte handling |
| [src/core/block.cpp](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/block.cpp#L8-L75) | `fc4fe774ccd75673c549734055907eb7c79c0fc2` | Static BitPacker mask rebinding through `Block::setLayout` |

These are **selected-function dependencies**, not new whole-file dispositions. Do not increase review-candidate or approval totals from this packet.

## PLOAD-001 — normal project opening binds masks before binary Block decoding

`MainWindow::openProject` first calls `projectConfig.load(dir)` and `userConfig.load(dir)` (809–814), creates a new Project (819–830), then runs `loadProjectData() && setProjectUI() && setInitialMap()` (840–846). `loadProjectData` calls `Project::load` (869–874). Within `Project::load`, `readMapLayouts()` **precedes** `readFieldmapMasks()` (192–211), but `readMapLayouts` constructs layout metadata rather than decoding binary block words (621–691). `readFieldmapMasks` reads the configured fieldmap defines, overrides available masks, and invokes `Block::setLayout()` (2437–2481). Actual blockdata decoding is deferred to `Project::loadLayout` (328–349) and `Layout::loadBlockdata`/`readBlockdata` (576–626); initial map selection occurs only after `Project::load` returns successfully (840–846).

**Source-level resolution:** for the examined normal successful `openProject` → initial map path, the mask packers are rebound before the first lazily loaded layout's binary words are decoded. Do **not** misreport the earlier `readMapLayouts` call as an immediate decode-order defect. This does not prove every plugin, custom script or alternate caller follows that order.

## PLOAD-002 — save-without-reload leaves a conditional live mask-identity split

`ProjectSettingsEditor::save` assigns the UI masks to `projectConfig.blockMetatileIdMask`, `blockCollisionMask` and `blockElevationMask`, then saves config files and sets `projectNeedsReload = true` (approx. 601–657). It does **not** call `Block::setLayout`. `closeEvent` explicitly permits declining the subsequent reload prompt and warns this may cause problems (836–855). The sole pinned `Block::setLayout` call identified in the relevant producer path is in `Project::readFieldmapMasks` (2481). The `reloadProject` signal is connected to `MainWindow::on_action_Reload_Project_triggered` (3069–3074), which reopens the same project root (1068–1071).

**Conditional obligation:** when editable masks actually change, the user saves, and the user declines reload, `projectConfig` can hold the new masks while the static Block packers still reflect the previously loaded masks. No claim is made that a specific corrupt export occurs: a later code path must be demonstrated to read or write a Block during that interval. Disabled controls for C-defined masks also constrain which edits are possible.

## PLOAD-003 — settings persistence is not a verified atomic transaction

`ProjectSettingsEditor::save` calls `projectConfig.save()`, `userConfig.save()` and `porymapConfig.save()` without checking their boolean returns before clearing `hasUnsavedChanges` and marking reload required (approx. 646–657). `KeyValueConfigBase::save` checks file-open failure but not `QFile::write`'s returned byte count, and returns true after `file.close()` (255–270). `MainWindow::openProject` closes the current project before attempting to load the new config and project (797–846), while `KeyValueConfigBase::load` resets the in-memory config before parsing (215–252).

**Compatibility obligation:** a future authoritative-source refresh must verify durable writes, detect partial settings persistence and preserve a recoverable pre-refresh snapshot; a successful settings dialog return or an editor reload prompt is not a commit protocol. These are source-level detection gaps, **not** proof that Qt writes fail in practice.

## PLOAD-004 — mask provenance is required at the point of decoding

`KeyValueConfigBase::load` parses the project config first; the `block_*_mask` config keys are bounded to `Block::maxValue` (956–961). Later, `Project::readFieldmapMasks` can override any mask with a C-defined value cast to `uint16_t` (2437–2481), warning but not rejecting truncation. That function also marks parsed defines as disabled settings. Thus the **effective** masks at the successful normal load are not necessarily the values originally persisted in `porymap.project.cfg`; the parsed define overrides must be captured along with their source-file identity. The Block packers are process-wide static state rather than per-Block provenance (see earlier packed-block dossier).

## Fail-closed Phase 1 review and interoperability gates

1. Record both persisted config masks and effective post-`readFieldmapMasks` masks, with source-file/define identities, before treating any Block stream as semantically interpretable.
2. Refuse to label an in-place project refresh lossless if settings changed but the active packers have not been rebound; explicitly detect the save-without-reload interval.
3. Require confirmed durable config writes, a recoverable original and no silent change of mask ownership, width, layout identity or decoded block triples.
4. Test the Qt editor with **both** reload accepted and declined, edited C-defined masks, changed config masks, malformed blockdata and save failures. Verify no-op project byte identity and separately verify exported ROM semantics.
5. Independently review the **entire** pinned source files before any whole-file approval; the selected-function anchors above are not signoffs. The authoritative machine gate must remain `FAIL_INCOMPLETE`.

**Evidence scope:** six pinned Git blobs and a source-level call-order trace. No compiled Qt run, no CI test added by this dossier, no observed data loss, no new review candidate, no Phase 2 implementation.
