# Phase 1 — pinned Linux fd VFile and GBA savedata cleanup

**Disposition:** bounded source/native-host evidence, not independent semantic
approval. No upstream source, shared gate, approval count, or runtime behavior
was changed. Gate remains `FAIL_INCOMPLETE`; independent approvals remain `0`.

## Pinned provenance

- mGBA revision: `fd9dc5c2cbf234365068855851107e762fc6211b`
- `src/util/vfs/vfs-fd.c`: blob
  `2535bd0fb76740745ae038d5523ead28658f1035`, SHA-256
  `0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44`
- `src/gba/savedata.c`: blob
  `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb`, SHA-256
  `9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161`
- `src/gba/gba.c`: blob
  `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e`, SHA-256
  `e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b`
- `include/mgba/internal/defines.h`: blob
  `67b8ec8fd2f51ee2c0c6231443af752158397b03`, SHA-256
  `167896b30ed7f1cd3f9e5cbc99ee994a48a094b3e95989ab2f9e1ebf8cf4b46b`
- Direct VFS compile headers are pinned too: `vfs.h` blob
  `6c9bd299153af4c3c9cd5487f2425a2481331ee5`, `vector.h` blob
  `c837379e2102ca6535db2b292233bd4983c3532c`, `common.h` blob
  `923e93086adfa09c9a55fcc2f0f6fa4d560e5888`, and `dllexports.h` blob
  `a44480df6ec26821b8616650b2575ba794848eca`. The runner checks each blob
  and SHA-256, plus the exact commit and tree blobs in checkout mode.
- Compressed machine dossier: Git blob
  `3b982876c7d810a827af8c80c7e5d9231fdaa327`, SHA-256
  `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.
  Canonical row SHA-256 values:
  - `vfs-fd.c`: `bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942`
  - `savedata.c`: `99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0`
  - `gba.c`: `d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056`
  - `defines.h`: `05a6cd7248412bb03041f85841bf51db1f6a52e4b27bea5ac19c15ffa36a7bc2`
- Each inspected upstream file carries an MPL-2.0 notice. No upstream source
  was copied into the repository or modified; the exact cleanup body is
  extracted into a temporary build directory. This does not resolve rights for
  any combined distribution.

## Source and dependency closure

The relevant pinned chain is:

1. `GBASavedataInit()` assigns both `savedata->vf` and `savedata->realVf`,
   enables `MAP_WRITE`, and resets dirty tracking (`savedata.c:46–63`).
2. `GBAFrameEnded()` calls `GBASavedataClean()` with the video frame counter;
   it invokes `savedataUpdated` when the savedata dirty state transitions to
   clean (`gba.c:967–1007`).
3. `mSavedataClean()` first records the frame for `DIRT_NEW`, then cleans only
   when `frameCount - dirtAge > mSAVEDATA_CLEANUP_THRESHOLD` (15)
   (`defines.h:9–28`). At equality, 15 frames have not expired.
4. On that transition, the original `GBASavedataClean()` body calls
   `savedata->vf->sync(savedata->vf, savedata->data, size)` for writable mapped
   savedata (`savedata.c:586–604`).
5. On POSIX mapped files, `_vfdMap()` uses `MAP_SHARED` for `MAP_WRITE` and
   `MAP_PRIVATE` otherwise, with `PROT_READ | PROT_WRITE` in both cases
   (`vfs-fd.c:134–149`). `_vfdSync()` uses `msync(..., MS_ASYNC)` for a
   non-null buffer and nonzero size; it uses `fsync()` on the distinct
   no-buffer path (`vfs-fd.c:246–270`). `_vfdUnmap()` calls `msync(...,
   MS_SYNC)` then `munmap()` and ignores both return values (`vfs-fd.c:151–155`).
6. `GBASavedataDeinit()` unmaps savedata before clearing `savedata->vf`
   (`savedata.c:71–105`); `GBAUnloadROM()` calls it before closing
   `realVf` (`gba.c:168–176`). The POSIX `_vfdClose()` closes/frees the VFile
   wrapper but does not track/unmap mappings (`vfs-fd.c:102–116`).

The runner compiles the complete pinned `vfs-fd.c` translation unit and
executes the original extracted `GBASavedataClean()` body plus the original
inline `mSavedataClean()` from `defines.h`. It verifies the pinned
`GBAFrameEnded()` and `GBASavedataDeinit()` function bodies and call/order
anchors, but does **not** compile those functions or the full GBA core. The
harness substitutes only a narrow savedata struct and the size/unmask/RTC
support functions. The `VFileReadline()` symbol is a link-only stub and is not
called.

## Native Linux execution

The local run used individually retrieved original files with exact Git-blob
and SHA checks (`--source-dir`); that mode does not attest a full upstream tree
identity. The existing workflow invokes the same runner with
`--checkout /tmp/xgba-mgba-boundary`, which additionally enforces the pinned
commit and source tree blobs.

Command:

```sh
python3 tools/phase1_mgba_vfs_fd_native.py \
  --source-dir /tmp/mgba-vfs-review \
  --harness tests/phase1_mgba_vfs_fd_native.c
```

Compiler: GCC 13.3.0. The source compiled with C11, POSIX feature level
`200809L`, `ENABLE_VFS_FD`, `-Wall -Wextra -Werror`, and linker wrapping for
`msync` and `fsync`. The system headers selected
`_POSIX_MAPPED_FILES=200809L`; the witness does not force that mapping macro.
`HAVE_FUTIMENS`/`HAVE_FUTIMES` are not enabled in this standalone compile.
Temporary files are created only under a fresh `/tmp` directory and removed.

Observed output:

```text
PHASE1_VFS_CASE mappings shared_child=165 private_child=34
PHASE1_VFS_CASE cleanup async_ms=1 sync_ms=1 fsync=0 rtc=1 dirty=0 age=100
PHASE1_VFS_CASE close active_mapping_survives=1
PHASE1_VFS_DONE
```

The child process read the shared mapping's updated byte (`0xA5`) through a
separate file descriptor, while a modified private mapping left its backing
file byte at `0x22`. The original cleanup body did not sync at frame 100 or
frame 115, then called the actual fd VFile `sync` callback at frame 116. The
wrapped syscall counts observed one successful `MS_ASYNC`, no `fsync` on this
buffer-sync path, and one `MS_SYNC` during explicit unmap. The original cleanup
body continued to its RTC-write call after sync succeeded. A separate case
observed that closing the POSIX VFile wrapper did not invalidate its live mmap;
the harness then explicitly unmapped it. This matches the inspected GBA
teardown order, which unmaps savedata before closing the retained file handle.

The published fixture SHA-256 is
`4062a96262dbc118876d6170b7d1a2aff5593d2cba003053e3d4cd2a3e734b7f`.
Three source mutations (shared/private mode, async/sync mode, and cleanup
callback) and four contradictory/malformed evidence mutations were rejected.
The local executable SHA-256 was
`c769fd003677fb1a4db54f9e61132d2e2c04433b25c1105ff112450c408ccbee`.

## Evidence limits and CI

This is the pinned Linux/POSIX fd backend only. It does not test Windows or
other VFile implementations, the no-buffer `fsync` branch, syscall failure
handling, power-loss durability, a full mGBA runtime, stock gameplay, real
`.sav` restart/interoperability, or cartridge/physical Flash. In particular,
successful `MS_ASYNC`/`MS_SYNC` calls and cross-process page-cache visibility
are **not** a power-loss durability guarantee. The harness is not a Qt/QFile
test and does not establish save-file behavior at the Qt boundary.

Exact-head PR Actions run
[#41477561270](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41477561270)
was created for head `2f533a1a693f356760e69544747739d221664f83` and is
`action_required` with **zero jobs**. This is a workflow-permission blocker;
there is no job log or Actions execution evidence for the new step, and no
claim is made that CI or checkout-mode tree verification passed. The native
execution above is local evidence from individually pinned source files.
Earlier successful run #41438931700 predates this witness and does not validate
it. No retry or permission bypass was attempted. No approval or gate count is
changed.

## Failed-sync and fsync fallback follow-up (2026-11-03; pending exact-head CI)

The existing pinned native fixture now injects `EIO` from the actual
`msync(MS_ASYNC)` callback during original `GBASavedataClean()` execution.
It checks the cleared dirty flag, suppressed RTC write and lack of automatic
retry absent another dirty write. It also calls the distinct no-buffer
`sync(NULL, 0)` `fsync` path and checks its injected failure return. These
are host-level controlled failures, not full mGBA runtime or power-loss
proof. Original upstream files remain unchanged. The dossier parser rejects
forged failure-path records and duplicate original dossier identities.
New fixture SHA-256: `0669521df7e63cbe3e21a461e37fc1bc46ff802e9594c977830cf063f06c8374`. New synthetic parser tests and native
execution are **pending** an exact-head CI run; earlier green checks do not
validate this update.
