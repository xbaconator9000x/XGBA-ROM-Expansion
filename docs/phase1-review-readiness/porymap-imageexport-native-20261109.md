# Phase 1 — pinned Porymap indexed 4-bit PNG export boundary

**Disposition: `NEEDS_EVIDENCE`; Phase 1 remains `FAIL_INCOMPLETE`, with zero independent approvals.** This package is a bounded native witness for the original indexed-PNG encoder. It does not change pinned upstream source or certify the full Porymap GUI.

## Immutable scope and provenance

Pinned source: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`.

| File | Git blob SHA-1 | Full-source SHA-256 | Original dossier-row SHA-256 | Role |
|---|---|---|---|---|
| `src/core/imageexport.cpp` | `b57c6dd976fa016f00f7344f00e0cce86cd5f325` | `6766bd924ef9f71a8f432d0304c020cf4b1114ed7f35ad66b785820e69cd1791` | `7c973a6ad0c38a54a91dcde77dfbaf55dfcf231d8321333af016326129086ebb` | Focal encoder |
| `include/core/imageexport.h` | `d195e47180b0317e22bc1b3ed72f8db7770e0dbf` | `175b3d98f491cfba99ad012b7e9b7c8485016c276d6e54ad138c6f84e78afbd5` | `cc84e91b7a7cda9df78cb7d6a8fb7399463b381ea639f26552eb6743da8febfd` | Focal API |

Original inventory provenance is the workpack ZIP SHA-256 `5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4` and compressed `evidence/candidate_review_dossiers.jsonl.gz` SHA-256 `fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac`. These are machine-triage identities, not semantic-review receipts. The checker verifies the pinned checkout, full bytes, Git blobs, original row hashes, and the workpack hashes before compiling.

The pinned `porymap.pro` includes the focal implementation and API in the Qt application. Its only direct callsite is `src/ui/tileseteditor.cpp`; that file is included only as caller context and is not re-reviewed here. The native harness supplies a test-only `logError` implementation. The pinned root `LICENSE.md` contains LGPL-3.0 text; this is not a distribution-compliance conclusion.

## Native observations

The workflow compiles unchanged `src/core/imageexport.cpp` with Qt 6 and exercises:

- **Positive:** a 4×2 indexed image writes a PNG with indexed-color type and 4-bit depth, then decodes with matching dimensions and pixel colors.
- **Negative—odd scanline width:** a 3×2 indexed image is written, but the decoded result does not match the input. In the pinned implementation, the nibble-pair counter is initialized once before the row loop, while each row begins with a filter byte. The result is a reproducible scanline-packing boundary defect for this input, not a claim about all image sizes or user data.
- **Negative—empty image:** the null-image input logs an error and does not create an output file.

Local native execution against the exact raw pinned source passed the even-width and null-image controls. The 3×2 odd-width image was written but Qt's PNG reader rejected it with `libpng error: Not enough image data`. This is a local native result, not an exact-head workflow result.

The harness and evidence validator also reject mutated source identity and forged positive/negative result fields. Native execution is limited to this helper and Qt image decoding; it does not exercise the complete UI, disk-failure behavior, project persistence, gameplay, or hardware. Exact-head workflow results must be checked before reporting runtime observations as CI-verified.

## Changed-path boundary

This package adds its native harness, source/provenance verifier, dossier, and a step/path trigger in the existing PR #27 Porymap workflow. It does not edit upstream Porymap, source pins, semantic approval gates, shared registers, main, or another repository. The test record remains non-approving.
