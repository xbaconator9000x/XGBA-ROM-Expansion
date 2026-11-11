# XGBA — Expanding What a Game Boy Advance Game Can Access

**Executed expansion proof: R6–R13 verified · 11 November 2026**

> **A real, source-built Pokémon FireRed executable running in the native mGBA core successfully used graphics bytes stored _beyond the conventional 32 MiB GBA ROM window_.** The game received a validated external resource through an opt-in host bridge, used FireRed's own sprite-sheet loading routine, and copied the expected bytes into emulated GBA object VRAM.
>
> **R6 integration milestone: 32/32 tests passed**, including the positive executable-game test and five executed fallback/failure cases. [Passing push CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940797581) · [Passing pull-request CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940805793) · [Experimental implementation, PR #40](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/40).

**The milestones are real; the expansion platform is not yet a finished product.** R6 used a temporary test host; R7–R13 progressed to game-initiated requests in a patched native mGBA core, actual LCD screenshots, live FireRed Pallet Town graphics swaps, native CPU-frame benchmarking, save-state rollback and a real map layout loaded from outside the ROM. These results do **not** establish a stock-emulator release, Android or GUI frame-rate performance, unrestricted CPU-addressable ROM, or original GBA hardware compatibility.

## Latest verified milestone — R13: real FireRed map geometry outside the ROM

**11 November 2026 · Draft [PR #54](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/54) · exact head `f3ae6846e5971c0617674d5cef98be5331b91b2d` · 4/4 focused native tests passed on both push and PR CI.**

The actual **Player's House 1F** layout was removed from the compiled FireRed ROM: its original 13×10 metatile grid (260 bytes) and 2×2 border (8 bytes) were replaced by zero placeholders before compilation. The test verified that the original full 260-byte map sequence was absent from the ROM, which remained within 32 MiB. The original **268-byte layout payload** was stored at sidecar offset **33,562,624 (32 MiB + 8 KiB)**.

The source-built FireRed game requests the external layout through XGBA, stages it in EWRAM and enters the house using the genuine FireRed `DoWarp` / `WarpIntoMap` / `CB2_LoadMap` path. Native map-grid and border contents are checked against the original bytes and SHA-256. The game then returns to ROM-resident Pallet Town, evicts the external layout and re-enters the house, requiring a fresh provider read.

| Native acceptance case | Executed result |
| --- | --- |
| External layout entry → Pallet Town → re-entry | 3 transitions, 2 host reads, native grid SHA verified |
| Extension disabled | 0 transitions, 0 host reads; external entry safely refused |
| Original map data | Full original metatile sequence absent from ROM; payload beyond 32 MiB |
| Native renderer | 4 enabled + 2 disabled original 240×160 LCD PNGs; enabled scene changes verified |

**Evidence:** [passing R13 push CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966044589) · [push screenshots and proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966044589/artifacts/13831536868) · [passing exact-head PR CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966059991) · [PR screenshots and proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966059991/artifacts/13830909294). All six R7–R12 regression workflows passed at the R13 head. The four R13 tests check disabled refusal, original map absence and external offset, real entry/return/re-entry, and native LCD frames. No ROM or raw map binaries are distributed.

**Scope:** R13 proves external **map geometry and border**, not a completely external map bundle. Native layout metadata, tilesets, events and scripts remain ROM-resident. SELECT triggers the native warp in the test fixture; walking through a physical door and arbitrary-size map support are not yet proven. This is an important functional advance: XGBA now supplies actual data used by the real map engine, not just an overlay sprite.

## R12: verified native FireRed save-state recovery

**R12 — verified native FireRed save-state recovery.** [Draft PR #53](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/53), exact head `864804eebcc90a90fb07a81ddc449440b2725827`. [Native CI, 4/4 passed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964008063) · [eight native LCD PNGs and JSON evidence](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964008063/artifacts/13830302814). Crystal → Magma → native mGBA save-state restore to Crystal → Magma again; exact OBJ VRAM SHA-256 checks and real provider read counts 1 → 2 → 2 → 3. Disabled control performed zero host reads. [Matching PR CI, 4/4 passed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964060978) · [PR evidence artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964060978/artifacts/13829574576). All R7–R11 regressions passed at the R12 head. This verifies same-ROM, same-core, same-mounted-pack emulator state rollback and fresh resource acquisition; it does not establish ordinary in-game SRAM saves, arbitrary pack-mismatch restoration or general save-state extension serialization.


**Current priority:** functional map loading and navigation, ordinary game-save persistence, cache/integrity lifecycle, and graphical emulator/audio/VSync validation. Repeated endurance testing is deferred unless a specific regression warrants it.

## R11: real FireRed Pallet Town CPU-frame benchmark

**11 November 2026 · Draft [PR #52](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/52) · exact head `168d9137cb6b1576b53b6b0455d8c56a39bd943b` · 5/5 focused tests on each exact-head CI run.**

R10 ([draft PR #51](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/51), commit `2ede1b8470cbf71318e44873497a8b8d2ab51526`) moved the experiment into the **actual FireRed Pallet Town map/overworld engine**, with a SELECT-triggered live external graphics swap. [R10 push CI, 5/5 passed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955838562) · [native GIF/PNG evidence](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955838562/artifacts/13827221467) · [matching PR CI, 5/5 passed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955844195). R11 measured the runtime cost using a **real pinned FireRed ROM and patched native mGBA CPU**, not GIF playback timing. The earlier R10 GIF held source frames for **165 ms each**, approximately **10×** a real **16.74 ms** GBA frame; its apparent sluggishness was an encoding/playback artifact, not evidence of a tenfold game slowdown.

R11 executed **six paired same-ROM trials** (three XGBA-enabled, three disabled), each with **120 warmup frames + 360 pre-swap frames + 3 SELECT frames + 360 post-swap frames**. Timing used `CLOCK_MONOTONIC` around `mCore.runFrame` and excluded PNG/GIF encoding. Results are **unthrottled native emulation throughput**, not real GUI, vsync, audio, Android or hardware frame rates.

| Measurement | PR CI runner | Separate push runner |
| --- | ---: | ---: |
| Disabled, before SELECT (median) | 1865.083 FPS | 1119.142 FPS |
| Enabled, before SELECT (median) | 1865.589 FPS | 1130.095 FPS |
| Disabled, after SELECT (median) | 1870.672 FPS | 1146.004 FPS |
| Enabled, after SELECT (median) | 1875.427 FPS | 1133.968 FPS |
| SELECT → second asset ready (median) | 0.635484 ms | 1.034608 ms |
| SELECT → second asset ready (emulated frames) | 1 | 1 |

**Interpretation:** Compare enabled/disabled **within** a runner; absolute throughput differs between shared CI hosts. The faster PR runner observed no measured frame exceeding **16.74 ms** during its trials. This does **not** prove frame-limited 59.7 FPS graphical playback or eliminate future streaming, cache, save-state or device-specific bottlenecks.

**Evidence:** [R11 exact-head PR CI, successful](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959825105) · [PR benchmark report artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959825105/artifacts/13828577188) · [R11 exact-head push CI, successful](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959790780) · [push runner report artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959790780/artifacts/13828024036). R7–R10 regression checks remained green at R11. GitHub Actions artifacts are retention-limited.

**Functional integration continuation:** see R12–R13 above. Repeated stress testing is deferred; all native implementation milestones remain experimental on draft branches, not released products.

## Earlier verified milestone — R9: same ROM, different external graphics packs

**11 November 2026 · Real compiled FireRed + native patched mGBA · 5/5 R9 tests passed**

**We have now visibly demonstrated resource-pack swapping while a controllable GBA scene runs.** The *same, byte-identical FireRed ROM* booted in the native modified mGBA core with two separate graphics resource packs held **past the 32 MiB cartridge ROM window**:

| Run | External resource | Observed screen behavior |
| --- | --- | --- |
| **Pack A: Crystal** | Cyan/blue native 64×64 4bpp GBA sprite, 2,048 bytes | Real game-loaded crystal emblem over tiled scene |
| **Pack B: Magma** | Red/orange/gold native GBA sprite, same ID/size/offset, different SHA-256 | Visibly different emblem without rebuilding the ROM |
| **Extension disabled** | No external reads | Controlled scene and original graphics fallback remain operational |

The source-built FireRed ARM/Thumb program sets up GBA BG0 tilemap and OAM, receives an external resource through the **game-initiated R7 mGBA MMIO interface**, and polls actual **GBA KEYINPUT** to move a player sprite. During each run the native mGBA software renderer captured **16 original 240×160 screenshots**; those captured images—not synthetic or AI-generated gameplay—were encoded into three GIF animations.

The executed test observed the player moving **(24, 92) → (38, 102)** in each run; **891 pixels** differed between the crystal and magma emblems in the central comparison region, and the disabled run performed **zero host resource lookups**. The game ROM's SHA-256 was **identical in all three runs**.

**See the actual executable evidence:** [passing R9 run and artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42950960274) · [GIFs, original PNG frames, three-way comparison and proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42950960274/artifacts/13824972843) · [R9 implementation PR #49](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/49). The R9 PR CI also passed, and prior R7/R8 native regression CI remained green at the exact R9 commit.

**Important scope boundary:** R9 uses a **custom controllable tile-based proof scene inside a compiled FireRed executable**, *not* the canonical FireRed overworld map/event engine. It is not yet a standalone GUI emulator release, a drop-in arbitrary ROM patcher, or original-cartridge support. The R7–R9 implementations remain in **open draft PRs #47–#49**, preserving the previously validated baseline. The GitHub Actions GIF artifact is retention-limited; its underlying code and test procedure remain in the repository.

### The engineering progression

- **R6:** a source-built FireRed game consumed bytes beyond 32 MiB with a test host bridge.
- **R7:** FireRed issued its **own resource request** to the opt-in patched native mGBA core; exact OBJ VRAM bytes and disabled fallback verified.
- **R8:** a real compiled FireRed executable **displayed an externally loaded graphic on mGBA's actual 240×160 LCD output**. [R8 PNG proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42947434354).
- **R9:** two independently selected external 4bpp graphics packs visibly changed a **controllable game-side scene**, with unchanged ROM identity and recorded mGBA GIFs.
- **R10:** actual FireRed Pallet Town overworld engine performed a live SELECT-triggered external graphics swap.
- **R11:** six paired native mGBA trials measured unthrottled CPU-frame throughput and resource-ready latency, correcting misleading GIF playback pacing.
- **R12:** real native mGBA save-state rollback restored the earlier graphics and game state, then a fresh guest request re-acquired the second asset.
- **R13:** actual FireRed house map grid and border lived outside the ROM; native map transitions, eviction and re-entry loaded them from the sidecar.

**Next work:** expand real map integration to normal door navigation and further asset types; validate ordinary in-game save persistence and broader cache/pack identity; measure real graphical-emulator playback with audio/vsync; and package accessible ROM-hacking tooling. Larger resource-library tests remain valuable, but redundant endurance tests are deferred. Total external content can grow separately from the addressable cartridge window, but CPU/GBA memory limits still apply.

## Why this matters for GBA ROM hacking

Traditional GBA ROM hacking is constrained by the cartridge's CPU-visible ROM address space. Adding regions, sprites, music, dialogue, and other game data typically means fitting assets into that space, repointing them, or working around the cartridge's storage and banking conventions.

**XGBA explores a different architecture: keep the executable game inside the normal ROM window, but allow explicitly modified games and emulators to retrieve additional assets from separately stored, validated resource packages.**

If developed into reusable tooling, this could change the practical scope of emulator-targeted GBA projects:

- **More worlds and content:** additional regions, tilesets, artwork, dialogue, and potentially new scenarios without requiring every asset to reside in the cartridge ROM.
- **Larger Pokémon and character projects:** additional sprites, animations, forms, and associated content, subject to each game's engine and data-structure limits.
- **Modular distribution:** resource packs with stable identifiers, integrity checks, and source-ROM identity rather than a single ever-larger binary.
- **New editing workflows:** future integration with ROM-hacking editors and build pipelines could manage external resources directly.

These are **implications and development goals**, **not features already supported for arbitrary ROMs**. There is no claim that XGBA was the first project ever to explore emulator-assisted resources, that ordinary emulators can already run it, or that hardware limits have been eliminated.

### The key distinction: storage is not directly addressable memory

An ordinary GBA CPU cannot simply dereference an unlimited ROM pointer. The experimental mechanism separates **how much data the host can store** from **how much data the GBA can address or hold at once**.

~~~text
               Real FireRed ARM/Thumb execution
                    (ordinary GBA ROM)
                             |
                  Test-only opt-in handshake
                             |
           mGBA-linked native host resource provider
                             |
           Versioned manifest + identity + SHA-256
                             |
        External sidecar asset beyond ROM's 32 MiB
                             |
                 Bounded GBA EWRAM staging
                             |
            FireRed's native LoadSpriteSheet()
                             |
                    GBA object VRAM
                  (verified by test)
~~~

The host's resource collection could *eventually* be far larger than the ROM window because content can be loaded on demand. It is **not literally infinite**: host storage, indexing formats, data-transfer speed, game-engine changes, EWRAM/IWRAM/VRAM capacity, and runtime lifecycle constraints still matter. The demonstration **does not** directly map external bytes into the GBA CPU's ROM address space.

## What we actually proved — R6

On **11 November 2026**, the R6 executable integration test:

1. Built a **real ARM/Thumb FireRed ROM and ELF** from the pinned [pret/pokefirered](https://github.com/pret/pokefirered) source with a small, temporary opt-in test probe.
2. Ran that compiled ROM in the **actual native mGBA CPU core** built from pinned [mgba-emu/mgba](https://github.com/mgba-emu/mgba) sources. This was **not** a Python-only simulation of game execution.
3. Created an external sidecar containing a **64-byte test graphics resource at file offset 32 MiB + 8 KiB**, past the ordinary ROM window.
4. Verified the game's identity and resource integrity through the experimental host provider, then copied the validated bytes over the emulated GBA bus into bounded **EWRAM**.
5. Allowed FireRed's compiled code to call its real **sprite-sheet loading path**, then verified the exact expected data in **OBJ VRAM**.
6. Executed five additional test modes: **extension disabled**, **incorrect ROM identity**, **truncated resource**, **corrupted digest**, and **missing resource**. Each correctly used or preserved the original sprite rather than accepting invalid external data.

The full exact-commit test run reported **32 tests passed**, with the same commit passing both GitHub push and PR checks.

**Scope of the result:** the proof verifies an actual game's resource-load path and destination graphics memory. It does **not** establish a user-facing on-screen sprite presentation, live map streaming, audio streaming, general-purpose patching of existing ROM hacks, or that stock mGBA can use sidecars without modifications.

### The six delivered experimental packages

| Package | Delivered capability | What it establishes |
| --- | --- | --- |
| **R1** | Validated, bounded sidecar streaming | External resources can be addressed and read, including from sparse storage beyond 32 MiB. |
| **R2** | Deterministic resource packaging | Stable resource identity, integrity data, repeatable builds, and rollback on failure. |
| **R3** | Opt-in host staging bridge | Bounded staging and source-ROM identity checks without rewriting ordinary ROM pointers. |
| **R4** | Native FireRed static-graphics adapter | FireRed's real sprite-loader contract can consume a valid bounded EWRAM source, with original-asset fallback. |
| **R5** | Native C mGBA-linked resource provider | Versioned provider handshake, validated resource retrieval, and failure/opt-out paths using the pinned emulator library. |
| **R6** | Executed FireRed + mGBA integration | A running, compiled FireRed game actually receives and loads the post-32-MiB graphics resource; five negative cases run too. |

All six are recorded as **delivered experimental packages**. The delivery ledger and code are tracked in [PR #40](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/40) and the [autonomous product ledger](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/blob/xgba-autonomous-product-state/.xgba-autonomy/ledger.json). **PR #40 remains an unmerged draft**; this README documents the verified milestone without silently shipping its experimental implementation on the main branch.

## Reproduce the evidence

**Most direct:** inspect the [32/32 passing source-build and integration CI run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940797581), which checks out pinned FireRed and mGBA sources, installs a real ARM build toolchain, compiles FireRed and the mGBA-linked harness, and runs the positive and negative cases. The matching [pull-request run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940805793) is also green.

For local reproduction on a suitable Linux build host, use the **experimental branch**, not the current main branch:

~~~bash
git clone https://github.com/xbaconator9000x/XGBA-ROM-Expansion.git
cd XGBA-ROM-Expansion
git checkout phase1/xgba-optin-resource-prototype-20261110
mkdir -p upstream
git clone https://github.com/pret/pokefirered.git upstream/pokefirered
git -C upstream/pokefirered checkout --detach ce6406d8c2eaf46d543c8a2606de0c3cb1951982
git clone https://github.com/mgba-emu/mgba.git upstream/mgba
git -C upstream/mgba checkout --detach fd9dc5c2cbf234365068855851107e762fc6211b
# Install GCC, CMake, Make, binutils, arm-none-eabi-gcc,
# arm-none-eabi-nm, the ARM C runtime and graphics build dependencies.
python3 -m unittest discover -s tests -p 'test_xgba_resource_*.py' -v
~~~

For the focused experiment, run `python3 tools/xgba_resource_integration_smoke.py --json r6-proof.json` after preparing the same toolchain and pinned sources. The demonstration compiles its own ROM from source, instruments a temporary checkout, and records ROM/ELF/resource hashes and execution results. **Do not publish copyrighted game ROM bytes.**

**Upstream pins:** FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`. The passing product commit is [`b9632c5`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/b9632c5ae9c562bb764047657deb12d7b0ffe891).

## What comes next

The R6–R13 milestones answer increasingly practical feasibility questions for **emulator-assisted external assets**. The next task is to turn these executed, source-instrumented proofs into a reproducible, supportable workflow:

1. **Production integration:** harden the existing game-initiated native mGBA resource device and FireRed-side integration into an explicitly enabled, maintainable extension and reusable resource API.
2. **Engine support:** extend the verified sprite and map-grid integration to ordinary navigation, tilesets, palettes, other assets, and safe decompression, allocation, ownership, resource lifetimes, DMA, audio and save-state identity.
3. **Hacking tools and compatibility:** integrate resource IDs and packaging with editors/build systems; test fingerprinted game versions and modified ROMs instead of assuming universal compatibility.
4. **Release and regression:** provide runnable builds, clear setup instructions, measurable load times, fail-closed recovery and honest emulator/hardware support claims.

**Not yet proven:** a direct drop-in upgrade for existing `.gba` files, original-cartridge compatibility, ordinary stock-emulator support, arbitrarily large *simultaneously addressable* GBA memory, or a complete game expansion beyond 32 MiB.

## Earlier research and compatibility work

This breakthrough **builds on**, rather than erases, the repository's prior source-pinned hardware and ABI research:

- [Historical Phase 1 source-mapping status](docs/PHASE1_STATUS.md): `FAIL_INCOMPLETE`, including the 14,834-file inventory. Mapping and independent whole-file semantic approvals remain incomplete, but a full mapping pass is **not a prerequisite** for the demonstrated opt-in prototype.
- [34 native mGBA Matrix and cartridge regression checks](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40204719637): banking, ROM access, DMA, save and savestate behavior, including known unsafe behaviors. This is separate from the external-sidecar proof.
- [External resource/banking constraints](docs/PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md): GBA address-space realities and why existing 64 MiB Matrix banking is not the same as an open-ended sidecar resource protocol.

**XGBA is an experimental engineering project, not a finished ROM-hacking product.** But the distinction now matters: we have moved beyond a proposed design and demonstrated that a running GBA game can use validated external resources stored past its ordinary cartridge ROM window. The next challenge is to make that capability practical, reproducible, and available to the wider ROM-hacking community.
