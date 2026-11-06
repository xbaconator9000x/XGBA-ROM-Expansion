# Porymap QtGifImage and FEX vendor closure (2026-11-06)

## Status and scope

This is a non-approving source, build-edge, and notice handoff for 40 complete
files from `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`.
It does not change vendored sources or decide legal distribution compliance.
Every new source row is `NEEDS_EVIDENCE`; there are no independent semantic
approvals. The imported candidate inventory remains machine triage, not a
review receipt.

The reproducible machine report is
`phase1-evidence/vendor-license-closure.json` in the exact-head artifact from
the existing **Phase 1 full pinned Porymap Qt project save/reopen** workflow.
For each of the 40 files it records the original Git blob ID, computed full
source SHA-256, exact candidate-dossier row SHA-256, inventory status,
component, notice caveat, complete-file scope, caller/build edges, unresolved
objection, and `NEEDS_EVIDENCE` disposition. The report also includes reused
context-file identities and negative-control counts.

Immutable inventory provenance:

- Workpack ZIP SHA-256:
  `5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4`
- Compressed candidate dossier member SHA-256:
  `fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac`
- The workpack contains 14,834 machine inventory rows. The verifier filters
  for the exact Porymap repository and pin before matching paths, then checks
  every original row, Git blob, and any supplied source SHA-256. It computes a
  full-byte SHA-256 even where the original row omitted one.

## Source and build closure

- `porymap.pro` includes
  `src/vendor/QtGifImage/gifimage/qtgifimage.pri`. That file includes
  `src/vendor/QtGifImage/3rdParty/giflib.pri` and builds `qgifimage.cpp`.
  The application call sites are `src/ui/loadingscreen.cpp` and
  `src/ui/mapimageexporter.cpp`. The GIFLIB qmake fragment lists six C files:
  `dgif_lib.c`, `egif_lib.c`, `gif_err.c`, `gif_hash.c`, `gifalloc.c`, and
  `quantize.c`. `gif_font.c` is tracked but not listed as a build input.
- The application project lists FEX `lexer.cpp` and `parser.cpp`, and the
  corresponding public headers. `src/core/parseutil.cpp` uses
  `fex::Lexer`/`fex::Parser`. `parser.h` includes the separately noticed
  `include/lib/orderedmap.h`; this is reused context, not re-counted as new
  source work.
- `src/lib/fex/parser_util.cpp` is present in the pinned source inventory but
  is not listed in `porymap.pro`; it includes
  `lib/fex/parser_util.h`, which is absent from the pinned include tree. The
  application build therefore does not establish a compiled caller or working
  edge for that file.
- The qmake application build is the only compiled evidence for this package.
  It does not test GIF decoding/encoding behavior, the standalone QtGifImage
  project/documentation targets, or platform-specific builds. The existing
  workflow's broader GUI/project tests are not GIF runtime tests.

## Notice boundary and source objections

The pinned Porymap root has an LGPL-3.0 notice. QtGifImage's implementation
and public/private headers contain an MIT-style notice; GIFLIB has a separate
`COPYING` notice; FEX has duplicate MIT `LICENSE` files under `include/lib/fex`
and `src/lib/fex` (the two copies match). The FEX README copies also match.
The qdoc files, snippets, build fragments, and other files without a
file-specific notice are not assigned a license by inference from neighboring
files. The prior OrderedJson work already covers `include/lib/orderedmap.h`
and the serializer boundary; it is reused only as a dependency/provenance
reference. Its dossier SHA-256 is
`33f91d91a214fa66469e6be10c9c98114e4eb8d90d246716e67bcd1eabc583bf`.

The pinned `qgifimage.cpp` also presents unresolved source-level behavior
concerns: device-mode tests use bitwise OR, `EGifSpew`'s return is ignored,
`EGifCloseFile` is commented out, and the `DGifSlurp` error path returns
before `DGifCloseFile`. These are source observations only; this package does
not reproduce them at runtime or claim exploitability. The orphaned FEX
`parser_util.cpp`/missing-header edge is likewise recorded without changing
the upstream source.

No Poryscript or FireRed source is part of this dependency closure. Their
existing immutable pins and all approval/gate records remain untouched.
OrderedJson is reused context and is not counted among the 40 new files.

## Reproduction and bounded controls

The existing workflow checks out the pinned Porymap commit, verifies the
workpack and compressed dossier hashes, and runs:

```sh
python3 tools/phase1_porymap_vendor_license_closure.py \
  --porymap upstream-porymap \
  --workpack imports/XGBA_Phase1_v1.5_Complete_Workpack.zip \
  --output phase1-evidence/vendor-license-closure.json
```

The checker rejects source-byte/Git-blob mismatches, candidate row provenance
or approval mutations, workpack/dossier hash changes, and evidence-boundary
mutations that would imply approval, a legal conclusion, or runtime/full-GUI
verification. These controls are limited to this inventory/build handoff;
they are not GIF failure-injection tests. No source was edited, and no
rollback, filesystem durability, gameplay, or distribution-compliance claim
is made. The Phase 1 gate remains `FAIL_INCOMPLETE`.
