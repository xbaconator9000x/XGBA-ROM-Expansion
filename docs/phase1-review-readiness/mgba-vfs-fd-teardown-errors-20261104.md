# Phase 1 — pinned Linux VFile teardown error propagation

**Disposition:** bounded source-extracted/native-host evidence, not independent
semantic approval. No upstream source, shared gate, approval count, or runtime
behavior was changed. Gate remains `FAIL_INCOMPLETE`; independent approvals
remain `0`.

## Pinned provenance and licensing

All source identities below are from `mgba-emu/mgba` revision
`fd9dc5c2cbf234365068855851107e762fc6211b`. The verifier checks each Git blob
and complete-file SHA-256, the corresponding canonical source row in the
machine dossier, and—when run with `--checkout`—the checkout commit and tree
blobs. The compressed dossier is Git blob
`3b982876c7d810a827af8c80c7e5d9231fdaa327`, SHA-256
`1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.

| Pinned file | Git blob | Source SHA-256 | Canonical dossier row SHA-256 | Review disposition |
|---|---|---|---|---|
| `src/util/vfs/vfs-fd.c` | `2535bd0fb76740745ae038d5523ead28658f1035` | `0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44` | `bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942` | Full pinned TU compiled and native failure paths executed. |
| `src/util/vfs/vfs-mem.c` | `048194e2dd2d0b3b395a852d2092c694663c88a2` | `6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b` | `3c95e0a322b5aff0655ec59a1c1f5d34a740a21676da0bf5cce444d2434248ce` | Full pinned TU compiled and memory-backend controls executed. |
| `src/gba/savedata.c` | `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` | `9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161` | `99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0` | Seven exact bodies extracted, compiled, and executed with bounded support stubs. |
| `src/gba/gba.c` | `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e` | `e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b` | `d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056` | `GBAUnloadROM` extracted, compiled, and executed; `GBADestroy` source-pinned and audited only. |
| `src/gba/core.c` | `6bfc518bb8899205c07d1d0fc091a287cb42f874` | `47a213e3f4de2299c8859822459a82ef1ae7784b0341ba49d9dd1433b8339596` | `3431f140bdc22e29d591eacae07aadc5b4b0ae20b4c9036ef3d7e89dc9528784` | `_GBACoreDeinit` audited only; exact `_GBACoreSavedataRestore` body executed in the bounded writeback witness below. |
| `src/core/scripting.c` | `7ccb51e897685ce24b37dabc76beb27427331b4f` | `8bb8d2ca9a744b51a96d5258b7a1cec49b724f92ae843a1504b22d4ae9d138b1` | `9975d4c10ec523f164e9e0292ae795ccb8522343d7b926c233bee159de08abc8` | Callback/error path source-pinned and audited only; not compiled or executed. |
| `src/script/stdlib.c` | `f84b62515315c119ec4ff5b9fb6df4de4517c738` | `52c9fc2d9490f3f158f20c8eddfed07440ec22e4f174043f96e3704599c87b99` | `db8b3609ef7ae747d57b1b3a163dd9af6fbbf9c22d661b2a5261e274cbae6ad1` | Script-facing registration path source-pinned and audited only; not compiled or executed. |
| `include/mgba-util/vfs.h` | `6c9bd299153af4c3c9cd5487f2425a2481331ee5` | `4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656` | `5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd` | Direct harness compile input; interface contract inspected. |
| `include/mgba-util/common.h` | `923e93086adfa09c9a55fcc2f0f6fa4d560e5888` | `ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f` | `b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec` | Source/header pin and dependency-closure validation only. |
| `include/mgba-util/dllexports.h` | `a44480df6ec26821b8616650b2575ba794848eca` | `96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4` | `5a0c3158c1515885d4f326ea52cc891074b5e0cd54e40460eab89d55a1746070` | Source/header pin and dependency-closure validation only. |
| `include/mgba-util/vector.h` | `c837379e2102ca6535db2b292233bd4983c3532c` | `ae8d9ed36475bda93ab3d2ff581163cedd289b2275c5254b76ba9e4285696375` | `6a1179a47870dc93b443eff57599611d1b8d43d87560de25863a9e5805d83eb7` | Source/header pin and dependency-closure validation only. |
| `include/mgba-util/memory.h` | `325f748f6fddc33a5539739ebc6eff6f3bb42bad` | `509b56f31b2a279d954a16799501a1585cf7aa55f917a180432283b0205c198c` | `cf858e1e109d1346cab0d7b30bcd119c207cfb84e9b45a3e73321c1e3576315e` | Direct harness compile input; allocation contract inspected. |
| `include/mgba-util/math.h` | `f7b3269c9d51967765379b951ba6f43d24c61865` | `04f5ee1686f4b30744d4e62caef4cf16f2f4b80682b88a87e7e18cf117fd421e` | `87d819c03b064e4665a27b5563f4a7261cfcdad051913229884d4f72cfd813f9` | Source/header pin and dependency-closure validation only. |
| `include/mgba/core/core.h` | `64ddf851ef00ab09416a9c1c9b5a88798fcd6fc8` | `e77d0b72af5b76d9b66292968359122a15ab5c4c624d684af7ad339fa700e7a9` | `0fb39db4601aad348aa35a4adbb7a4a41b05a26128957595547a95bc72208a87` | Core teardown interface source-pinned and audited only. |
| `include/mgba/gba/core.h` | `5cb0e468c100730a65199e9daeda78c2a885227d` | `9e9eb686f85856a6c9b659f0c99d4eb5f5c831120970d616f8554a448f558c8d` | `08637ccef3dea51935b64aeea0a34d40008862ebc3eed75f7385df0394ebbd22` | GBA teardown interface source-pinned and audited only. |
| `include/mgba/internal/gba/gba.h` | `65e994dc63a304cc9fb207536f09bb2c8a6cf3e5` | `b50fc8ae1467f9ac1c6be3ba8452e22027571ff5c886695edb9be529d7962d4e` | `d6e61894ce31db089d3fd04e64e0938d1e689fb6c7498a8056fced405bf2bba0` | GBA structure/source closure pinned and audited only. |
| `include/mgba/internal/gba/savedata.h` | `6227be25e8c9d2c1cc14c06ded34389b96138577` | `30481cada83cc0e3a88b55298f3081cc660e18e55ca7f5a57356e6f2a75224dc` | `eaee2c8bdb65c51e4f40daeb80af916f57ed430c48c88286562363f687ca6de9` | Savedata structure/source closure pinned and audited only. |

These source files and headers carry MPL-2.0 notices. Only source-derived
function bodies are extracted to a temporary build file; no mGBA source is
copied into this repository or modified. This does not resolve rights for any
combined distribution.

## Source closure and return propagation

Pinned line anchors and extracted original function-body SHA-256 values:

| Source function/contract | Line(s) | Body SHA-256 / relevant contract |
|---|---:|---|
| POSIX `_vfdUnmap` (`vfs-fd.c`) | 151–155 | `6fa24bf9ba88d150e66baf99e3dc62fee2f8facfb439c616cd4709f307be61af` |
| `_vfdClose` (`vfs-fd.c`) | 102–117 | `047a214a51b79ddf2e6b01c50bdbb2fc201fb601c9e7d2fb67c917138a258af5` |
| `_vfmUnmap`, `_vfmSync` (`vfs-mem.c`) | 284–289, 326–331 | `a9abf736086c31862111fbb4f2050f68be14f09b19908ffb9bf81f892b0f08b8`; `aa681292c67cd4a34400bb3b247d30bfb2f66ed1f46a93c91436a0153c426a28` |
| `GBASavedataInit`, `GBASavedataDeinit` (`savedata.c`) | 46–64, 71–105 | `e7acccd1db65be1be7e20e49b23167b4c237d6e6646bac75d16be857269be408`; `830e75777a5a94797eb4a5cc0d6294952340887bc5d5457ca4ea3d228a94f7d2` |
| `GBASavedataMask`, `GBASavedataUnmask` (`savedata.c`) | 107–118, 120–135 | `713b702618c61c33848bf9d88c9c4799d4f133471369df394747275c3e739277`; `6517182aaa42db3fdc6fc4eb8582a5c9f5ff2e4364fedbf1abe4e7b7fc644709` |
| `GBASavedataSize`, `GBASavedataLoad`, `GBASavedataForceType` (`savedata.c`) | 169–192, 194–226, 228 onward | `9f3e0774073a8f44195f2b1b8c2d4c20977dedd1eb8c4d7ec4c1c42e467b02d1`; `f272ab49e19f5be2284c9dc851f53b070606fd75b626db60a92b499c2d05c2b2`; `7ffbdeaf9944c79c2fc2811070817427e071c9e49faa5f865b58d50e12b25cea` |
| `GBAUnloadROM`, `GBADestroy` (`gba.c`) | 140–178, 180–196 | `1c7090ddfe712b836048af6492dedb4f8c4d2ec94ac0f30f3b8e92648071b7f6`; `45831c7737fc196fa77546805aa6f0cca2fd34565bd3d7a77d65d58e1a858535` |
| `_GBACoreDeinit` (`core.c`) | 309–330 | `f118627b62bee1476c5351def9c9d5378e31091277913b6a71615ffcb789a04f` |
| `VFile` / `mCore` interfaces | `vfs.h:35–45`; `core.h:57` | `VFile.unmap` returns `void`, `VFile.close` returns `bool`; `mCore.deinit` returns `void` |

The path is `GBACoreDeinit` → `GBADestroy` → `GBAUnloadROM` →
`GBASavedataUnmask` → `GBASavedataDeinit` and then close of the retained real
VFile. The relevant caller in `GBAUnloadROM` ignores `realVf->close()` and
clears `realVf` regardless. `GBASavedataDeinit` invokes a `void` unmap callback
and clears `vf`/`data`; there is no return value through which either
`msync(MS_SYNC)` or `munmap` failure could travel. POSIX `_vfdUnmap` calls both
syscalls in order and checks neither result. `_vfdClose` returns `false` on
`close(fd)` failure before freeing its wrapper; the `GBAUnloadROM` caller does
not inspect that boolean.

The conditional masked-save path is independently relevant: `GBASavedataMask`
deinitializes the real mapping and selects a temporary VFile; `GBASavedataUnmask`
restores the real VFile, calls `GBASavedataLoad` when `maskWriteback` is set,
clears the flag, then closes the temporary VFile. The original unmask body
checks neither `GBASavedataLoad` nor `close` results. A short read from the mask
file makes original `GBASavedataLoad` return false; that failure does not stop
unmask or ROM teardown.

The separately pinned memory VFile backend has a different contract:
`_vfmUnmap` is a no-op, `_vfmSync` returns true, `VFileFromMemory` close frees
only the wrapper, and `VFileMemChunk` close owns and frees its buffer. These
are not POSIX fd semantics.

`GBAUnloadROM` has no `savedataUpdated` or script callback reference. The
existing callback witness covers the distinct `GBAFrameEnded` dirty-to-clean
event; that notification describes an emulation save-data modification, not
successful persistence. This teardown package does not claim a native script
error callback or GUI notification. The GBA core deinit callback is `void`, so
these teardown failures are not returned through the core deinit interface.

## Native Linux fault-injection matrix

The existing witness compiles the complete pinned `vfs-fd.c` and
`vfs-mem.c` translation units. It additionally compiles and executes the exact
extracted original `GBASavedataInit`, `GBASavedataSize`, `GBASavedataDeinit`,
`GBASavedataMask`, `GBASavedataLoad`, `GBASavedataUnmask`, and `GBAUnloadROM`
bodies. `GBASavedataForceType`, memory allocation, and GBA support functions
are narrow fixture stubs; the full GBA core, `GBADestroy`, and
`GBACoreDeinit` are source-pinned and audited but not compiled. Syscall
wrappers inject `EIO` into selected `msync(MS_SYNC)`, `munmap`, and `close`
calls. The `close` injection fails before invoking the real syscall, explicitly
leaving its fd open for safe, deterministic retry testing.

The local executable used a fresh temporary directory and was compiled by
GCC 13.3.0 with C11, POSIX feature level 200809L, `ENABLE_VFS_FD`,
`-Wall -Wextra -Werror`, and linker wrapping for `msync`, `munmap`, `close`,
and `read`. The source files were fetched individually at the immutable pin;
local `--source-dir` mode verifies all Git blobs, full-file hashes and dossier
rows but does not attest whole-tree identity.

```sh
python3 tools/phase1_mgba_vfs_fd_teardown_native.py \
  --source-dir /tmp/mgba-teardown-source \
  --harness tests/phase1_mgba_vfs_fd_teardown_native.c
```

Fixture SHA-256:
`c731670c511ceaf53db2fac8372efe5bfa36ad443bf8808b675b740e4e2cbe9f`.
The local run compiled and executed successfully with GCC 13.3.0 and observed
`_POSIX_MAPPED_FILES=200809L`. The native executable SHA-256 was
`52484a99978b046220d89e3ad9832043f07775c0a308dbf76c6adf404c9036c5`.
All 20 targeted parser tests passed. The runner rejected six source mutations
and eleven contradictory or malformed evidence mutations. Local native
observations:

| Case | Observed result |
|---|---|
| Successful teardown | One `MS_SYNC`, one `munmap`, one close; state pointers cleared; event order `SUC`. |
| Injected `MS_SYNC` `EIO` | `munmap` still called; deinit clears savedata pointers; a child process opening the same file reads the modified byte. This is page-cache visibility, not durability. |
| Injected `munmap` `EIO` | Sync succeeds, savedata pointers are cleared, but the externally retained mapping remains readable. The fixture manually unmaps it after observation. |
| Injected real-VFile close `EIO` | GBA teardown clears `realVf` despite ignored close failure; the captured wrapper remains usable and a second close succeeds. |
| Combined masked writeback | Mask mapping receives injected `MS_SYNC` and `munmap` failures; a 32-byte mask file is read where the original load requests 4096 bytes; unmask ignores that short-load result and the injected mask-file close failure; GBA teardown still clears savedata references. Trace is `SUCSUC`. The harness manually cleans the surviving map and retries the captured close. |
| Memory VFiles | Original memory backend reports successful sync, does no work in unmap, preserves externally owned memory on close, and frees the `VFileMemChunk` buffer on close. |

The observed child reads are fresh-process reads through the same host kernel
and page cache. They are **not** process-crash/reboot, power-loss, storage
durability, `.sav` interoperability, stock-gameplay, or physical Flash
evidence. The test does not establish how a real OS reports close failures or
that a failed `close` leaves the descriptor open; that behavior is a controlled
fault-injection assumption. No callback error report is inferred.

## Distinct savedata-restore POSIX write path

The pinned `src/gba/core.c` `_GBACoreSavedataRestore` caller uses
`VFileMemChunk` and invokes `GBASavedataLoad` when `writeback` is true. When
`savedata->data` is null but its real POSIX `VFile` is present,
`GBASavedataLoad` copies through `savedata->vf->write`. This is a separate
save-data restore path from the already-tested mapped-save sync/unmap and
masked short-read cases. The original caller and original `GBASavedataLoad`
body execute with the complete pinned POSIX fd and memory VFile translation
units; a local syscall wrapper controls only the write result. The caller
translation unit is not compiled: a narrow fixture `mCore` object supplies the
original function's `board` field.

The exact `_GBACoreSavedataRestore` function-body SHA-256 is
`8f3654b0b9164674275a28137a89decf55047436aa8df09225ccfcb326a6ea0b`.
Its source file identity and canonical dossier row are listed above; the
source files and headers carry MPL-2.0 notices. Only source-derived bodies are
extracted to a temporary build file; no mGBA source file is copied into this
repository. The runner verifies the caller body as well as the existing
savedata and VFile source identities.
The current verifier rejects seven source mutations and fifteen malformed or
contradictory output mutations, including a false complete-write control.

| Case | Observed pinned caller result | Host-file observation |
|---|---|---|
| Full write | Caller returns true; original VFile path issues the full write and the following zero-length write. | All 2048 input bytes match. |
| Positive short write | The injected real POSIX `write` writes and returns 1 for a 2048-byte request. Caller returns true and issues no retry. | Only the first byte is present; this is a controlled host fault observation, not a claim about ordinary filesystem behavior. |
| Negative write | The wrapper returns `-1`/`EIO`; caller returns false. | The empty file remains empty. |

This is a compiled, source-extracted host witness, not a full mGBA frontend or
headless emulator run. The machine record marks the complete core translation
unit, headless process, and frontend runtime as unobserved. It verifies the
caller function's boolean result and same-host file contents only. It does not
show frontend handling of that result, save-state UI behavior, durable
persistence, `.sav` interoperability, stock
gameplay, or physical Flash behavior. No approval or gate status is promoted.

## Validation and CI

Targeted local parser and native checks are included in the existing
`phase1-mgba-savedata-boundary-witness.yml` workflow. Its checkout mode checks
the exact pinned commit and source tree before running this harness. The exact
code-bearing head `f239c0e42eb089ce5be7fb6d784853c645841d06` has PR Actions run
[#41852469153](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41852469153):
conclusion `action_required`, with zero jobs. No job or step executed; this is a
permission blocker, not CI success or a code failure. The workflow is
pull-request-only, so no push-event run exists. Earlier green Actions runs
validate only their own earlier heads. CodeQL on the code-bearing commit
reported zero alerts; secret scanning was clean.

Historical base-branch run #40475162042 failed an earlier savedata source
anchor at line 154; the subsequent base-branch run #40475197646 passed after
that anchor was corrected. Neither run validates this new teardown matrix.
