# Phase 1 curated source-evidence Git blob pinning — 2026-10-26

**Authoritative gate: FAIL_INCOMPLETE. Independent whole-file semantic dispositions: 0/14,834.** This checkpoint records an audit provenance improvement, not new semantic approval or XGBA runtime certification.

## Source-backed reproducibility gap

The 29-file curated review registry already pinned each upstream source file's exact Git blob and listed five source-interpretation documents. The previous verifier only required those Markdown files to exist. Their contents could change without changing the registry or invalidating its claimed evidence provenance. That was a local audit verification gap, not an upstream project defect.

## Bounded correction

- Commit `37cd8a9fb7dbd2a117c2f7f99834a71b60b8741a` adds `source_documentation_git_blob_sha1` for all five listed source-interpretation documents. The expected hashes were obtained from the repository's GitHub content API, using the existing checked-in documents.
- Commits `3d637c5df7c34f5528dee670f1ad5fb91d7fda0f` and `e0a7c492ffb17fe9ef92e15b73e5625b8ba673b1` require exact 40-character lowercase Git blob hashes and compare against the checked-out document bytes. Two new negative fixtures reject a missing document pin and an altered pin, while preserving the existing unsafe-path rejection behavior. The suite now defines ten negative controls (eight previously CI-verified, two newly added and pending CI confirmation).
- Commit `f04098af47c3f80773ebda9bc5b573e91a649ff3` adds the five pinned document paths to the existing Phase 1 census workflow push triggers. Documentation changes alone will therefore require fresh audit verification rather than silently inheriting an old green run.

## Verification boundary

The committed registry, verifier and workflow were read back from GitHub. All five source documentation entries have syntactically valid pinned Git hashes; the verifier checks actual Git blob identity, and all five paths are present in the workflow trigger. This is a **static read-back check only**, not a completed execution of the two new negative fixtures. [Earlier census run #40226474522](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40226474522) passed the previous eight-guard suite, **before** these commits. A new post-change census result must be inspected before calling the ten-guard suite CI-verified.

No upstream source revisions, signed reviews, native runtime implementations, or other repositories were changed. The Phase 1 semantic mapping gate remains the authority.
