# Pinned POSIX VFile allocation-failure ownership witness

Status: **NEEDS_EVIDENCE / FAIL_INCOMPLETE**. This bounded package is not an approval, compatibility verdict, or durability claim.

## Pinned source and call path

The witness is pinned to mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`, tree `5863e657d270d0fe3ccaa4299f48d5689d74fa1f`. The primary source is `src/util/vfs/vfs-fd.c` (Git blob `2535bd0fb76740745ae038d5523ead28658f1035`, full-source SHA-256 `0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44`, dossier-row SHA-256 `bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942`). The compiled interface dependency `include/mgba-util/vfs.h` is blob `6c9bd299153af4c3c9cd5487f2425a2481331ee5`, SHA-256 `4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656`, dossier row `5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd`. Both sources are MPL-2.0.

The pinned `src/util/vfs.c::VFileOpen` selects the POSIX `VFileOpenFD` backend. `VFileOpenFD` opens a path and passes the returned descriptor to `VFileFromFD`. `VFileFromFD` closes the descriptor if `fstat` rejects it, then allocates `struct VFileFD`. Its allocation-failure branch returns `NULL` without closing the already-open descriptor. The dispatcher is blob `3158c52659a83333cb23aeb0dd7ea4bba35908fc`, full-source SHA-256 `7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06`, dossier-row SHA-256 `47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2`. The relevant function-body SHA-256 values and the original compressed dossier identity (blob `3b982876c7d810a827af8c80c7e5d9231fdaa327`, SHA-256 `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`) are in the machine-readable receipt.

## Executed bounded matrix

`tools/phase1_mgba_vfs_fd_allocation_native.py` verifies pinned source, function bodies, tree and dossier records, then compiles the original POSIX VFile dispatcher and complete `vfs-fd.c` translation unit with the C harness. The harness invokes `VFileOpen`; linker wrappers inject failure only for the target VFile allocation size after a successful target-path `open`.

The host run recorded:

- Normal open: the caller receives a VFile; closing it closes the descriptor.
- Injected VFile allocation failure: the caller receives `NULL`; no close occurs in the pinned allocation branch; `fcntl` confirms the descriptor remains open in that process.
- Open-failure control: the caller receives `NULL` on `ENOENT`, without an allocation attempt.

Three source mutations and five contradictory/malformed output mutations are rejected. The committed receipt is checked against the observed matrix by both the runner and unit tests.

## Evidence boundary and objections

This is compiled pinned POSIX backend code with **host allocator fault injection**, not a full mGBA caller/frontend execution or naturally observed memory-pressure failure. The open descriptor is cleaned up by the harness after it records the leak; the observation does not establish save corruption, user-visible behavior, `.sav` interoperability, stock gameplay, persistence, power-loss behavior, or physical Flash behavior. Only the Linux/POSIX mapped-file path is tested; no claim is made about other VFile backends. Scope is limited to the `VFileOpenFD` → `VFileFromFD` ownership boundary, not a whole-file review.

The machine receipt remains non-approving: independent approvals `0`, status `NEEDS_EVIDENCE`, overall `FAIL_INCOMPLETE`.
