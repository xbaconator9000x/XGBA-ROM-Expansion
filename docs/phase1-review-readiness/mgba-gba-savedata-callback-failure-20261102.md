# Phase 1 — GBA savedata sync failure and `savedataUpdated` callback

**Disposition:** bounded source-derived native-host evidence; not an
independent semantic approval. No mGBA source, gate, audit, main branch,
approval count, or runtime code was changed. Gate remains `FAIL_INCOMPLETE`;
independent approvals remain zero.

## Pinned provenance and machine-dossier rows

All source paths below were checked against mGBA commit
`fd9dc5c2cbf234365068855851107e762fc6211b`. Exact Git blobs, full-file
SHA-256 values, and canonical per-file dossier SHA-256 values are pinned by
`tools/phase1_mgba_vfs_fd_callback_native.py`.

| Pinned source path | Git blob | Source SHA-256 | Dossier row SHA-256 |
| --- | --- | --- | --- |
| `src/util/vfs/vfs-fd.c` | `2535bd0fb76740745ae038d5523ead28658f1035` | `0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44` | `bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942` |
| `src/gba/savedata.c` | `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` | `9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161` | `99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0` |
| `src/gba/gba.c` | `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e` | `e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b` | `d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056` |
| `src/gba/video.c` | `28f072ec0b880d272f4f9564cc5ca8f5af389caf` | `77f6bd32b19a5e78f06b0826cf3b5135abfcc3be24e08bd278829cdc564eda4d` | `20c76a3c969ef4b98f090290b1183872d6c87cb4f68521375e5f5369d16479c0` |
| `include/mgba/internal/defines.h` | `67b8ec8fd2f51ee2c0c6231443af752158397b03` | `167896b30ed7f1cd3f9e5cbc99ee994a48a094b3e95989ab2f9e1ebf8cf4b46b` | `05a6cd7248412bb03041f85841bf51db1f6a52e4b27bea5ac19c15ffa36a7bc2` |
| `include/mgba/core/interface.h` | `b5ffa3049749b9141aa09fc3693bf758a13f4e13` | `da6ea4e344c46be5943859a24c0149c12a803b3e951c07140cc795cab09651de` | `093b18935d1a1968f5ce81caa23611a578cc8810a03bde39f3e3f55d0d6b2830` |
| `src/core/scripting.c` | `7ccb51e897685ce24b37dabc76beb27427331b4f` | `8bb8d2ca9a744b51a96d5258b7a1cec49b724f92ae843a1504b22d4ae9d138b1` | `9975d4c10ec523f164e9e0292ae795ccb8522343d7b926c233bee159de08abc8` |
| `src/script/stdlib.c` | `f84b62515315c119ec4ff5b9fb6df4de4517c738` | `52c9fc2d9490f3f158f20c8eddfed07440ec22e4f174043f96e3704599c87b99` | `db8b3609ef7ae747d57b1b3a163dd9af6fbbf9c22d661b2a5261e274cbae6ad1` |
| `src/platform/qt/CoreController.cpp` | `183cea418a70963bd5332ef66bdff54a0dcccd46` | `8ca7ca7b26fa030ef76322085a6f634b5e3ca4fd40a4e6549b6a12abace260b2` | `1cbedd6e36f387b7c579bcea8c77bed82e9c3e8b18954974847c647dcf8b0f28` |
| `src/platform/qt/Window.cpp` | `af6592985329f08898cf078a666763954383c832` | `67fcb2da1d2990e20bf57fd78f51881ce6a62a193cbabb5af5c3ec8fae29dea3` | `21da719393e20ace0bb1a7080aa8fc1d674fb10072d27fbbe06c74454d4a2398` |
| `src/platform/sdl/main.c` | `91f22bd593d4952076c2a9a11da5a8d6951db2a8` | `8bf9ae94c051bb6b8fd2e5bdd974652de6109afab80753e66023281f3956b81b` | `9b9c93092a263d137e7392e87ff64707bbb555d61f5a7317add771537a391f2c` |
| `src/platform/libretro/libretro.c` | `12e79131c38e06a8ba46cef97e0872ec51544e38` | `da8800c76929e25729573760b6180452cdefa824aa6df21b51c3566553ad67ac` | `70da3c3b8a3280ad6d077f9998fc73d69b443505d2d13dfee3dae791105f5f18` |

The compressed machine dossier is Git blob
`3b982876c7d810a827af8c80c7e5d9231fdaa327`, SHA-256
`1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.
The direct VFS compilation headers are pinned in the runner as well.
The inspected upstream files carry MPL-2.0 notices. No upstream file is
vendored or modified; this work does not determine rights for combined
distribution.

## Source-level callback/error chain

1. `mSavedataClean()` first clears `mSAVEDATA_DIRT_NEW` and records its frame;
   once the dirt age is strictly greater than 15 frames, it clears the dirty
   state and returns true (`defines.h:9–28`).
2. The pinned GBA video `_startHdraw()` VBlank case invokes `GBAFrameEnded()`
   after VBlank DMA/IRQ handling and before `mCoreSyncPostFrame()`, frame
   counter increment, and interrupt delivery (`video.c:176–198`).
3. `GBAFrameEnded()` captures `wasDirty` **before** calling
   `GBASavedataClean()` (`gba.c:967–970`).
4. For writable mapped data, `GBASavedataClean()` calls the VFile `sync`
   callback. It calls `GBASavedataRTCWrite()` only inside the branch where
   `vf->sync(...)` returned true; a false result logs sync failure and does not
   restore the already-cleared dirty bits (`savedata.c:586–604`).
5. After cleanup returns, `GBAFrameEnded()` calls `savedataUpdated` when the
   callback exists, `wasDirty` was nonzero, and the current dirty flag is zero
   (`gba.c:999–1007`). This predicate does not receive or inspect the VFile
   sync result. Consequently the source predicate can notify after a failed
   sync when cleanup consumed the dirty state. This is a callback condition,
   not proof that data persisted.
6. On the following clean frame, `wasDirty` is zero and the dirty helper does
   not schedule another sync. A future write that sets dirty again begins a
   new cleanup interval.
7. On Linux/POSIX, the pinned fd backend's mapped-buffer sync path returns the
   result of `msync(buffer, size, MS_ASYNC)` (`vfs-fd.c:246–270`). This is
   distinct from its no-buffer `fsync()` path. Unmapping calls `msync(...,
   MS_SYNC)` then `munmap()` and ignores both results (`vfs-fd.c:151–155`).
8. Teardown is a separate path: `GBASavedataDeinit()` unmaps savedata before
   clearing its VFile pointer (`savedata.c:71–105`), and `GBAUnloadROM()` calls
   it before closing `realVf` (`gba.c:140–178`). The runner pins and checks
   these full function bodies and ordering anchors; it does not execute this
   teardown path in the new callback case.

The public callback type is a `void (*savedataUpdated)(void* context)` member
(`interface.h:43–54`). The pinned core scripting layer registers
`.savedataUpdated = mCoreCallback(savedataUpdated)` and its context when
attaching a script context (`scripting.c:1484–1495`). The compiled original
callback macro triggers the script event named `savedataUpdated`; the script
API describes it as “The emulation has just finished modifying save data”
(`stdlib.c:90`), not as a persistence-success callback. In the exact pinned
Qt controller/window, SDL `main.c`, and libretro files checked here, there is
no `savedataUpdated` reference. This bounded lexical scan does not assert that
no other frontend, embedding, or downstream integration can register one.

The related pinned Game Boy code has a distinct `GBSramClean()` implementation
that calls its core callbacks after the clean interval even when the VFile
sync branch reports failure (`gb.c:391–416`). It was not included in the
native witness and no runtime consequence is inferred from that source
comparison.

## Native source-derived witness

The new runner checks the exact pinned commit, every listed source tree blob
and SHA-256, full-file dossier bytes and canonical rows, function-body hashes,
and unique source anchors. It compiles the complete pinned POSIX
`vfs-fd.c` translation unit together with the exact extracted
`GBASavedataClean()` and full `GBAFrameEnded()` bodies. It also compiles the
pinned core-scripting callback macro, `savedataUpdated` macro invocation, and
the exact callback/context designated initializer lines from
`mScriptContextAttachCore()`. A narrow host fixture supplies inactive GBA
subsystems and a script event sink; the full GBA core and frontend are not
compiled.

The controlled host injects `EIO` into the actual `msync(MS_ASYNC)` callback.
It then executes:

- failed sync: dirty becomes clean, RTC write count remains zero, and the
  registered script callback receives one event;
- next clean frame without another write: no sync retry and no second event;
- new dirty write followed by successful sync: a second sync attempt, one RTC
  write, and a second event.

The native fixture's expected output is:

```text
PHASE1_GBA_CALLBACK_CASE failure_async_ms=1 failure_rtc=0 failure_dirty=0 failure_script_events=1 retry_async_ms=0 retry_script_events=1 retry_rtc=0 new_write_success_async_ms=2 success_rtc=1 success_script_events=2
PHASE1_GBA_CALLBACK_DONE
```

The local run used individually retrieved original files with exact blob and
SHA checks (`--source-dir`), not a whole upstream Git checkout. GCC was
13.3.0; compile flags include C11, POSIX feature level 200809L,
`ENABLE_VFS_FD`, `-Wall -Wextra -Werror`, and `--wrap=msync`. Exact checkout
mode in the existing workflow additionally checks the full pinned commit and
tree blobs. Source mutations of the callback predicate, VFile sync expression,
and script event trigger are rejected. Eight contradictory or malformed
evidence mutations are rejected. Fixture SHA-256:
`4963287bf10a7e2a3cd5e52788bc3aa518d70319fafb8e580c1a9b935059b6d4`.
Local executable SHA-256:
`59b757bb3a6622e839e5832239637104d6c354fd7b69dbbcfb3da2eb17c67572`.

## Evidence limits and CI

This is a native, source-extracted Linux host observation with controlled
`msync` failure, not a full mGBA GBA translation-unit build or runtime. It does
not prove real power-loss durability, disk persistence or corruption, a real
frontend's presentation of the callback, Windows/Android/other VFile behavior,
save-file restart/interoperability, stock gameplay, or physical Flash. It
does not modify or fix the upstream behavior. The exact-head Actions result
will be recorded after the existing workflow runs; a permission-blocked
zero-job result will not be represented as success.

Baseline only: exact-head run
[#41485392440](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41485392440),
job `125414254600`, succeeded on the prior head `6abd6cb`. That run predates
this callback integration and does not validate the new witness.
