# Pinned mGBA SaveConverter whole-file review — v1 (non-approving)

**Disposition:** `NEEDS_REVIEW` | **Evidence status:** `NEEDS_EVIDENCE`
**Semantic approval:** none; no approval receipt is created by this workpaper.

This is a source-grounded counter-review of the complete pinned file, not an
independent semantic approval. The reviewer is `@copilot`, the same Copilot
identity that authored the existing PR #13 witness. Genuine reviewer
independence is therefore unmet. Do not count this workpaper as a disposition
or change the shared gate, queue, register, or approval counts.

## Immutable provenance

- Repository/source: `mgba-emu/mgba`, commit
  `fd9dc5c2cbf234365068855851107e762fc6211b`,
  [`src/platform/qt/SaveConverter.cpp`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/platform/qt/SaveConverter.cpp).
- Original Git blob: `4c32280c9c5288e806ffd237119186e2a633c4a7`.
- Source SHA-256: `3a6498a4fa69064d9b3723b49398cfe9d8e827ada3d8be26215db3a5ead2184f`.
- Verified length: 22,226 bytes and **757 newline-terminated lines**. The
  request described 758 lines; that count does not match the pinned bytes.
- The file begins with an MPL-2.0 notice (lines 1–5). This records the
  file-level notice only; it is not an opinion on combined-work or
  distribution rights.

### Original machine-dossier provenance

The original compressed snapshot at PR #13 head `eefaa0a0942ab371c89a5e1fb391bec14d493ee1`
was checked against the tracked bytes:

- `semantic-snapshots/current/candidate_review_dossiers.jsonl.gz` Git blob:
  `3b982876c7d810a827af8c80c7e5d9231fdaa327`.
- Compressed-byte SHA-256:
  `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.
- Target dossier is JSONL row 11,744; canonical per-file SHA-256:
  `dc4112a41e57a7496c02986e900cb3d089cc081ae36ee02f4df479d0fc890357`.
  The matching queue row is also row 11,744 and carries that same
  `evidence_sha256`.
- It reports P0, nine lexical sites, zero symbol candidates, and 14 direct
  include candidates (12 resolved candidates, zero ambiguous, two unresolved).
  Its status is `CANDIDATE_ONLY_SOURCE_HASH_VERIFIED`, reviewer is null, and
  semantic signoff is false. The dossier itself warns that it is automated
  triage—not semantic review—and may miss generated edges.

## Complete source coverage

All source lines were reviewed; ranges below form continuous coverage of lines
1–757. Blank lines are included in the ranges.

| Lines | Reviewed content |
|---|---|
| 1–30 | MPL notice, direct includes, feature guards, namespace |
| 31–65 | Dialog initialization, UI actions, signal wiring |
| 66–91 | Conversion dispatch and output-file handling |
| 92–163 | Input/output refresh and button eligibility |
| 164–202 | Savestate detection and serialized savedata-type selection |
| 203–267 | Size-based GBA/GB save-format detection |
| 268–319 | SharkPort and GSV header/payload detection |
| 320–358 | GBA/GB core-based savestate platform probes |
| 359–391 | State and extdata extraction/copying |
| 392–455 | `AnnotatedSave` construction and raw representation |
| 456–553 | Save-format labels and container formatting |
| 554–578 | `AnnotatedSave` equality |
| 579–656 | Candidate output conversion generation |
| 657–757 | GBA EEPROM and GB MBC2/MBC6 byte transformations |

The user-facing entry is `Window::setupMenu`, which registers “Convert save
game…” at pinned `src/platform/qt/Window.cpp:1372`; the `SaveConverter`
constructor connects dialog acceptance to `convert()` at lines 31–64.
`refreshInputTypes()` calls savestate, size, and header detection in sequence
(lines 92–121); `possibleConversions()` supplies the output choices
(lines 579–655).

## Source-grounded findings and disposition

### F1 — Core object is accessed after deinitialization

In `getStatePlatform()` (lines 320–357), both feature branches call
`core->deinit(core)` before the `state` branch calls
`core->stateSize(core)` to free the extracted state (GBA lines 325–337; GB
lines 340–352). At this pinned revision, GBA `_GBACoreDeinit` ends in
`free(core)` (`src/gba/core.c:309–329`), and GB `_GBCoreDeinit` ends in
`free(core)` (`src/gb/core.c:161–181`). Thus, whenever `mCoreExtractState()`
returns non-null, the subsequent `core->stateSize(core)` dereferences a freed
core object. This is a high-confidence source-level use-after-free; no runtime
crash, allocator result, or end-user impact was tested. A source repair would
need to obtain/cache the state size while the core is live and use that cached
size after deinit.

The separate `getState()` path (lines 359–372) obtains the size and deep-copies
the state before deinit. `getExtdata()` also deep-copies returned extdata before
deinit (lines 374–390); those two paths do not exhibit this same ordering.

### F2 — Output write and close errors are unchecked

`convert()` opens a direct `QFile` with `WriteOnly | Truncate` (lines 80–81),
then ignores `out.write(converted)` and closes without checking the write
count, `QFile::error()`, or close outcome (lines 82–83). Only `open()` failure
shows a warning (lines 84–89). The source therefore has no visible handling
for a short or failed write after truncation. This is a source-grounded risk,
not proof that a real filesystem write failed or that a user’s save was
corrupted.

The existing exact-head native Qt6 witness exercised the original pinned
`convert()` body with an injected `QIODevice`; it did **not** execute `QFile`
or a real filesystem/kernel failure. The logged cases were
`full=[22,22,22,1,0]`, `short=[22,1,1,1,0]`,
`negative=[22,0,-1,1,0]`, and `open_failure=[0,0,0,0,1]`.

### F3 — EEPROM endian conversion does not assign the accepted +16-byte tail

Size detection accepts GBA EEPROM sizes with an additional 16 bytes
(lines 218–227), and `possibleConversions()` creates an endian-swapped
candidate without dropping that suffix (lines 641–649). In the endian-changing
branch, `convertTo()` resizes to `target.size`, then transforms only through
`size & ~0xFF` (lines 674–687). For either accepted `EEPROM + 16` size, the
loop covers the EEPROM payload but no source statement copies or initializes
the remaining 16 bytes. This is a source-level omission; the resulting bytes,
Qt-version-specific allocation behavior, and persisted output were not
observed here. The native witness does not execute `AnnotatedSave::convertTo()`.

### F4 — Optional-core compile closure needs a build-matrix check

The source conditionally includes GBA headers (lines 16–20) and conditionally
compiles GBA/GB-specific conversion paths, but `detectFromHeaders()` contains
unconditional GBA SharkPort/GSV calls and GBA constants/types (lines 268–318).
The Qt CMake source list includes `SaveConverter.cpp` unconditionally
(`src/platform/qt/CMakeLists.txt:165`); the root only defines `M_CORE_GBA`
inside `if(M_CORE_GBA)` (`CMakeLists.txt:865–867`). This creates a
configuration-specific compile-closure concern when GBA is disabled. It was
not compiled with `M_CORE_GBA=OFF`, so this workpaper does not claim an
observed build failure. Verify that configuration or guard the GBA-only
header-detection code before closing this item.

### State-offset concern reviewed, not confirmed as an out-of-bounds read

`detectFromSavestate()` reads `state.at(offsetof(GBASerializedState,
savedata.type))` at line 180 without an adjacent empty-state check. However,
the pinned raw `mCoreExtractState()` path (`src/core/serialize.c:505–522`)
allocates the core’s fixed state size and returns null unless the read equals
that size; the GBA serialized structure is fixed at `0x61000`
(`include/mgba/internal/gba/serialize.h:275,333–496`). Therefore a short raw
state is not shown to produce a short `QByteArray` at this access. PNG state
validation and other error/race paths were not fully exercised, so this is not
a general safety certification.

## Dependency, compilation, and licensing ledger

The machine dossier’s 14 direct include candidates are:

| Line | Include | Dossier result |
|---:|---|---|
| 6, 11–14 | `SaveConverter.h`, `GBAApp.h`, `LogController.h`, `VFileDevice.h`, `utils.h` | Resolved candidates |
| 7 | generated `moc_SaveConverter.cpp` | Unresolved by tracked-source resolver |
| 9 | Qt `QMessageBox` | Unresolved external/system include |
| 17–19 | GBA core, serialize, SharkPort headers | Resolved candidates |
| 22–23 | GB core and serialize headers | Resolved candidates |
| 26–27 | memory and VFS headers | Resolved candidates |

`SaveConverter.h` conditionally imports GBA savedata declarations and GB
interface declarations; Qt CMake enables AUTOMOC and generates the UI header
through Qt’s UI wrapper. These build-generated files and Qt headers are not
tracked-source dossier entries. The dossier’s 12 “resolved” entries are path
candidates, not proof of complete transitive or semantic closure.

Input is a `VFileDevice` (`refreshInputTypes`, line 101); pinned
`VFileDevice::readData()` delegates to `VFile::read`, and its path constructor
opens a VFile. The output path is instead a direct `QFile` in `convert()`.
Consequently, the existing QIODevice fault injector does not establish
VFileDevice input behavior or QFile persistence/error propagation.

The source-level MPL-2.0 notice is retained in the pinned file. This review
does not expand that file-level observation into a conclusion about combined
distribution rights or the licensing of the full dependency closure.

## Executed evidence and open objections

GitHub Actions run [#41260407534](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41260407534),
attempt 2, completed successfully at exact PR #13 head
`eefaa0a0942ab371c89a5e1fb391bec14d493ee1`. Job
`124718485562` (`pinned-savedata-boundary-witness`) and steps 3–7 completed
successfully. The job log reports six mock-VFile witnesses and three mutation
controls; for the native Qt6 witness it reports the four arrays above,
11 evidence mutations rejected, three source mutations rejected, and the
original `convert()` body executed. The log also explicitly reports
`qfile_execution=false`, `native_filesystem_or_kernel_failure=false`,
`sav_file_interoperability=false`, `stock_gameplay=false`,
`physical_flash=false`, `independent_approvals=0`, and
`gate=FAIL_INCOMPLETE`.

The executed test compiles a bounded extracted `convert()` body with controlled
host interfaces; it is not a full mGBA Qt application build or a runtime test
of `getStatePlatform()`, `detectFromSavestate()`, or `AnnotatedSave` byte
conversion. No new test or duplicate native witness was run for this review.

| Evidence class | Status from this review |
|---|---|
| Pinned source/provenance | Verified for the complete 757-line target and machine dossier; source findings remain source-level |
| Controlled host/mock-VFile | Six bounded initialization cases and three source-mutation controls passed in job step 5 |
| Compiled | The witness compiled; this is not a full `SaveConverter.cpp`/mGBA Qt application build |
| Native Qt API | The extracted original `convert()` body ran against native Qt6 `QIODevice` fault injection |
| Native `QFile` / filesystem or kernel failure | Not exercised |
| `.sav` interoperability/restart, stock gameplay, physical Flash | Not exercised |

**Closure blockers:** obtain a genuinely independent whole-file review;
exercise/repair the core-lifetime path; run the applicable full-source Qt build
matrix (including the GBA-disabled configuration if supported); execute a
native conversion test for the EEPROM +16 suffix; and separately establish
real QFile error propagation, `.sav` interoperability/restart, and any
stock-gameplay or physical-Flash claims. These workpaper findings do not
establish those runtime outcomes.

The exact-head machine gate remains `FAIL_INCOMPLETE`, with 0 independent
semantic approvals. No source pins, upstream files, approval counts, or shared
gate were changed.
