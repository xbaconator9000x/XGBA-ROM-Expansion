# Phase 1 — pinned mGBA stdio VFile save teardown

**Disposition:** bounded source-extracted/native Linux evidence; not semantic
approval. No upstream source, save behavior, shared gate, approval count, or
runtime code was changed. The evidence is specific to the pinned stdio backend
selected with `ENABLE_VFS_FILE`; it does not identify the backend used by every
mGBA frontend or platform.

## Pinned provenance, dependency closure, and licensing

The source pin is `mgba-emu/mgba@fd9dc5c2cbf234365068855851107e762fc6211b`.
The verifier checks Git blob IDs and full-file SHA-256 values for the nine files
below, canonical matching rows in the compressed machine dossier, and—when
passed `--checkout`—the checkout commit and each source-tree blob. The dossier
is Git blob `3b982876c7d810a827af8c80c7e5d9231fdaa327`, SHA-256
`1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.

| Pinned file | Git blob | Source SHA-256 | Dossier row SHA-256 | Disposition |
|---|---|---|---|---|
| `src/util/vfs/vfs-file.c` | `4a63e53f842b31b24d6188e6525ddcf121a0c7da` | `77737a3fa897db96e31f1f5e56faa0c06afa0cc86c7697642b28026308ba0921` | `263f5e29518c63b6c0cfb36819debd8c57dfc630a6490376255e2f1fd1fe3849` | Complete original translation unit compiled and executed. |
| `src/util/vfs.c` | `3158c52659a83333cb23aeb0dd7ea4bba35908fc` | `7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06` | `47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2` | Exact `VFileOpen` body extracted, compiled, and executed with `ENABLE_VFS_FILE`. |
| `src/gba/savedata.c` | `fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb` | `9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161` | `99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0` | Exact sizing, init, SRAM type, load, mask/unmask, deinit, and clean bodies executed. |
| `src/gba/gba.c` | `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e` | `e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b` | `d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056` | Exact `GBALoadSave` and `GBAUnloadROM` bodies executed; `GBAFrameEnded` source-pinned and audited, not executed here. |
| `include/mgba-util/vfs.h` | `6c9bd299153af4c3c9cd5487f2425a2481331ee5` | `4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656` | `5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd` | VFile method contracts and compile dependency pinned. |
| `include/mgba-util/memory.h` | `325f748f6fddc33a5539739ebc6eff6f3bb42bad` | `509b56f31b2a279d954a16799501a1585cf7aa55f917a180432283b0205c198c` | `cf858e1e109d1346cab0d7b30bcd119c207cfb84e9b45a3e73321c1e3576315e` | Compile dependency; allocation routines are narrow host stubs. |
| `include/mgba-util/common.h` | `923e93086adfa09c9a55fcc2f0f6fa4d560e5888` | `ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f` | `b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec` | Transitive header compile dependency pinned. |
| `include/mgba-util/dllexports.h` | `a44480df6ec26821b8616650b2575ba794848eca` | `96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4` | `5a0c3158c1515885d4f326ea52cc891074b5e0cd54e40460eab89d55a1746070` | Transitive header compile dependency pinned. |
| `include/mgba/internal/defines.h` | `67b8ec8fd2f51ee2c0c6231443af752158397b03` | `167896b30ed7f1cd3f9e5cbc99ee994a48a094b3e95989ab2f9e1ebf8cf4b46b` | `05a6cd7248412bb03041f85841bf51db1f6a52e4b27bea5ac19c15ffa36a7bc2` | Exact `mSavedataClean` body executed. |

The pinned upstream files carry MPL-2.0 notices. Original files are fetched
only into the temporary build directory in CI; no upstream implementation was
copied into this repository or modified. This does not resolve rights for any
combined distribution.

## Source behavior and error propagation

Relevant pinned anchors are `vfs.c:30–58`, `vfs-file.c:29–159`,
`savedata.c:46–64, 71–135, 194–226, 327–350, 586–604`, and
`gba.c:140–178, 496–504, 967–1008`. The runner hashes every extracted body,
including all stdio backend methods, `VFileOpen`, savedata lifecycle methods,
`GBASavedataClean`, `mSavedataClean`, `GBALoadSave`, `GBAUnloadROM`, and
`GBAFrameEnded`.

With `ENABLE_VFS_FILE`, the pinned `VFileOpen` preprocessor path calls
`VFileFOpen`; if the path does not exist and the mode is `r+b`, `VFileFOpen`
retries with `w+b`. The harness compiles with `ENABLE_VFS` and
`ENABLE_VFS_FILE` and does not enable the fd backend. `GBALoadSave` installs
the supplied VFile.
The test calls that original body with the VFile returned by the original
dispatcher, then runs the pinned savedata type, mapping, mask/unmask, load,
cleanup, and unload bodies.

The stdio backend returns `fread`/`fwrite` counts from `VFile.read`/`write`.
`_vffMap` ignores `fseek` and `fread` results; `_vffUnmap` ignores seek/write
results and returns `void`; `_vffTruncate` is grow-only and ignores each
zero-fill `fwrite` result while incrementing its tracked size; `_vffSeek`
ignores `fseek` and returns `ftell`. `_vffSync` returns false when its
buffered `fwrite` does not complete the single requested element, otherwise
returns the result of `fflush`. It does not call `fsync`. `_vffClose` returns
false when `fclose` fails and does not free its wrapper on that path.

The save callers have distinct result handling:

* In the raw-data branch of `GBASavedataLoad`, the write count overwrites the
  read count and the function returns `read >= 0`. The native short-write case
  therefore returned true after the controlled cookie accepted 3 of 8 bytes.
* In the mapped-data branch, `GBASavedataLoad` returns whether the requested
  byte count was read. `GBASavedataUnmask` ignores that result, clears
  `maskWriteback`, and closes the temporary VFile.
* `GBASavedataDeinit` calls the void `unmap` method and clears the savedata
  pointer, so unmap write errors have no return channel. `GBAUnloadROM` ignores
  the `realVf->close` result and clears `realVf`.
* `mSavedataClean` clears the dirty state before `GBASavedataClean` calls
  `VFile.sync`. A failed sync skips `GBASavedataRTCWrite`. `GBAFrameEnded`
  source-pins a separate callback condition based on `wasDirty && !dirty`, not
  on sync success. Thus the source permits a dirty-to-clean notification after
  a failed sync; this package audits but does not execute `GBAFrameEnded` or
  claim that a frontend displays an error.

The POSIX fd backend is compared only at the API boundary: its distinct
`VFile.unmap`/`close` failure behaviors were covered by the preceding fd
package and are not repeated here.

## Native Linux execution

The fixture compiles the complete unchanged pinned `vfs-file.c` translation
unit and exact extracted `VFileOpen`, `GBALoadSave`, savedata, and unload
bodies. `mSavedataClean` is also extracted from its pinned inline definition.
Narrow stubs provide GBA peripheral callbacks, logging, allocation, and
unexercised savedata-type initializers. Linker wrappers inject `fflush` and
observe the real `/dev/full` `fwrite` failure. Linux `fopencookie` supplies
controlled short-write, short-read, and close-error streams.

The local run used GCC 13.3.0 on Linux with C11, POSIX 200809L,
`ENABLE_VFS`/`ENABLE_VFS_FILE`, `-Wall -Wextra -Werror`, and linker wrapping
for `fflush` and `fwrite`. The fixture SHA-256 is
`2458e0ed4e5cafc1e60dbac18e2bc5945b718377bd25b55213e63f55bf5c7a39`; compiled
executable SHA-256 is
`11f10fff88bd1a4e1cfccb3e819256d07fc9c0bd1cb1855b29a8d749bd29642e`.

```sh
python3 tools/phase1_mgba_vfs_stdio_native.py \
  --source-dir /tmp/mgba-stdio-source \
  --harness tests/phase1_mgba_vfs_stdio_native.c
```

The local `--source-dir` run verified each pinned file blob and source hash,
all nine canonical dossier rows, and function hashes; it did **not** attest
the upstream checkout's whole-tree identity. The existing PR workflow uses
`--checkout` after checking out the exact pinned commit and verifies the
upstream commit and each source-tree blob. Nine source mutations and ten
evidence mutations were rejected. All 18 new focused parser/extraction tests
passed.

| Native case | Observation |
|---|---|
| Regular save lifecycle | Original dispatcher and `GBALoadSave` selected the stdio VFile; original unload wrote and closed the mapping, cleared savedata references, and a fresh child process read `0x5C`. |
| Mapped short unmap | Controlled cookie accepted 3 of 4096 bytes; original unmap/deinit returned no error and cleared `savedata.data`. |
| Raw short load | Controlled output accepted 3 of 8 source bytes; original raw `GBASavedataLoad` returned true. |
| Mask/unmask short read | Controlled temp stream supplied 32 of 4096 bytes then `EIO`; original unmask completed, cleared its writeback flag, and later unload wrote the partial buffer. A fresh child read `0xD4`. |
| Injected `fflush` failure | The wrapper made the original `_vffSync(NULL, 0)` call return false; after injection was disabled, close flushed the payload and a child read `F`. This is a controlled injection, not a filesystem failure. |
| `/dev/full` savedata cleanup | Native Linux `fwrite` failed in the original buffer-sync path; dirty state was already cleared, RTC write count remained zero, and cleanup did not expose a caller return value. |
| Unload close error | The `fopencookie` close callback returned `EIO`; host `fclose` invoked the callback, the original VFile wrapper remained allocated, and original GBA unload cleared its savedata references while ignoring the bool. The fixture freed the retained wrapper after observation; it did not retry `fclose`. |

The child reads establish visibility through the same host kernel/page cache,
not power-loss durability. The native harness does not run a real mGBA
frontend, stock ROM gameplay, or `.sav` interoperability; it does not test
`fsync`, process-crash/reboot behavior, physical Flash, non-Linux platforms, or
every VFile backend. The `fopencookie` cases are controlled host fault
injections; `/dev/full` is a Linux-specific host error path.

## Validation and CI

The exact pre-change PR13 head
`0bf5a496df18ef9e3c6cf39ef361ffbe93931c6a` had successful Actions rerun
[#41853164293](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41853164293),
job `126701990749`, 20/20 executed steps. It validates only that earlier head.
Exact-head PR Actions
[#41881695685](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41881695685)
for `b540768f5e8baad5b0724f36eadde8269ad6a485` is `action_required`; the API
reports zero jobs, so there is no job or step log and no CI pass for this
package. The base branch had no matching workflow run. The existing workflow
does not subscribe to `push`, and no push-triggered run was found. This is a
permission blocker, not a code failure or green result.

The local source-directory native run and 18 focused tests passed. Secret
scanning found no secrets, and CodeQL reported zero alerts for Actions, Python,
and C++. The workflow remains the existing PR13 workflow; no new workflow,
scheduler, branch, or PR is added.

This evidence remains non-approving. Gate stays `FAIL_INCOMPLETE`;
independent approvals remain zero.
