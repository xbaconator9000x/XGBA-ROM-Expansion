# Phase 1 v2.3 — ROM backing, audio and animated tiles resource lifetimes

**Scope:** pinned source semantics for existing mGBA and FireRed. Thirteen exact-source, ordered-in-function assertions passed in [the dedicated reproducible check](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40185950861). This validates source structure and identifies obligations; it does **not** implement or execute an XGBA sidecar.

## 1. mGBA ROM-size handling and pointer replacement

**Pinned** `mgba-emu/mgba` commit `fd9dc5c2cbf234365068855851107e762fc6211b`.

- [`src/gba/gba.c:425–493`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/gba.c#L425-L493), blob `c30bd943909dc00df0b5b9932e6d9ddb6e1c404e`: `GBALoadROM` unloads the prior game; when a file exceeds `GBA_SIZE_ROM0` (32 MiB), it probes offset `0xAC`. A value `'M'` enters the Matrix-compatible path; other oversize files map at most the original 32 MiB into the ROM window. ROM masks, CRC and active-region CPU fetch callbacks depend on this constrained mapping.
- [`gba.c:140–177`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/gba.c#L140-L177): `GBAUnloadROM` unloads cartridge peripherals, frees or unmaps ROM backing, closes the VFile, clears the ROM pointer and size, and tears down savedata state.
- [`src/gba/memory.c:1900–1918`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L1900-L1918), blob `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc`: copy-on-write replaces backing ROM memory, repairs the CPU `activeRegion` pointer where necessary and rebinds `gpioBase`.
- [`gba.c:554–579`](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/gba.c#L554-L579): the original binary-ROM patch function rejects patched sizes greater than 32 MiB and replaces the mapped ROM pointer. **It cannot be reused unchanged for unlimited external content.**

**Design contract XC23-ROM-LIFECYCLE:** An opt-in external-resource provider needs explicit open/close, ROM identity, cache generation, memory-window version and peripheral arbitration. Invalidating a bank must invalidate any host pointers derived from it, including CPU instruction fetch and device mappings. An oversize .gba file is not a substitute for a versioned sidecar. Normal loading/patching must continue to use mGBA's native size rules, including Matrix behavior.

**Unexecuted regression obligations:** ROM unload/reload while bank mapped; CPU ARM and Thumb prefetch after COW and patching; pointer ownership on failed map; save-state restoration after external resource removal; Matrix and GPIO compatibility; extended package checksum mismatch.

## 2. Persistent audio pointers and music scheduling

**Pinned** `pret/pokefirered` commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.

- [`src/m4a.c:107–114`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/m4a.c#L107-L114), blob `ebd3afe291b6c4e9f2ac62250a87c6a0482086d4`: song ID indexes `gSongTable[n]`, selects player through `song->ms` and passes the raw song-header pointer to `MPlayStart`.
- [`m4a.c:611–665`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/m4a.c#L611-L665): when playback starts, `mplayInfo->songHeader`, `mplayInfo->tone` and each `track->cmdPtr = songHeader->part[i]` persist beyond the call.
- [`m4a.c:668–689`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/m4a.c#L668-L689): stopping playback pauses and stops tracks but does not explicitly zero the song-header pointer.

**Design contract XC23-AUDIO-RETENTION:** Keep song headers, voicegroups and active track command streams pinned in the emulated address space for the duration of their use, including after pause/resume and through savestate restoration. External bytes cannot be evicted based solely on the completion of `MPlayStart`, and a raw host pointer must never be inserted into song tables. Extension IDs and song/player ranges must be versioned and checked.

**Unexecuted regression obligations:** concurrent background tracks and sound effects; pause, resume and channel preemption; cache eviction while `cmdPtr` points to a song; corrupted voicegroup; transient resource failure.

## 3. Animated tilesets queue deferred DMA references

- [`src/tileset_anims.c:3–15`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/tileset_anims.c#L3-L15), blob `04854a2e46a1d2ca89626e7be92955d6a20490e5`: queued tile DMA buffers store `src`, `dest`, `size` and the queue length; the array has **20 slots**.
- [`tileset_anims.c:143–162`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/tileset_anims.c#L143-L162): `AppendTilesetAnimToBuffer` enqueues an original source pointer; `TransferTilesetAnimsBuffer` later calls `DmaCopy16(3, src, dest, size)` before clearing the queue. Enqueue does **not** copy bytes.
- [`tileset_anims.c:164–205`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/tileset_anims.c#L164-L205): map layout primary and secondary tileset pointers independently install their animation callbacks. Timer ticks queue VRAM updates.
- [`tileset_anims.c:208–215`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/tileset_anims.c#L208-L215): hard-coded tile offsets are used for specific animation frames, so a dynamic tileset plugin must also preserve allocator/VRAM destination contracts.

**Design contract XC23-TILE-DMA-PINNING:** Source tile frames must remain resident until the deferred DMA completes. Do not mutate or evict mapped graphics between queue creation and transfer, even after source objects have been imported or edited. The queue capacity, primary/secondary callback lifetime and physical VRAM destinations remain native GBA constraints.

**Unexecuted regression obligations:** map change during queued transfer; adding frames; overlapping VRAM destinations; timer wrap; animated collision/layer metadata; hot-reload while DMA pending.

## 4. Independently reviewed function-level coverage still pending

The new [`tools/function_semantic_dossiers.py`](../tools/function_semantic_dossiers.py) produces 39,530 additional *function-level review entries*, exposing parser provenance, direct/indirect call syntax, memory references, assignments and branch obligations. These are valuable for review but are **not** approved semantics. Of those, **31,043 are from files with parser errors** and require extra caution.

**Phase 1 remains `FAIL_INCOMPLETE`**. The exact-source assertions pass; no XGBA external bank, stream or ABI has yet been executed or validated.
