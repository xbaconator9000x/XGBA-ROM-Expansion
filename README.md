# XGBA — Expanding What a Game Boy Advance Game Can Access

**Experimental proof of concept achieved · 11 November 2026**

> **A real, source-built Pokémon FireRed executable running in the native mGBA core successfully used graphics bytes stored _beyond the conventional 32 MiB GBA ROM window_.** The game received a validated external resource through an opt-in host bridge, used FireRed's own sprite-sheet loading routine, and copied the expected bytes into emulated GBA object VRAM.
>
> **R6 integration milestone: 32/32 tests passed**, including the positive executable-game test and five executed fallback/failure cases. [Passing push CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940797581) · [Passing pull-request CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940805793) · [Experimental implementation, PR #40](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/40).

**The milestone is real; the expansion platform is not yet a finished product.** The successful demonstration uses a temporarily instrumented FireRed build and an external test harness linked to mGBA. It is **not** an off-the-shelf emulator patch, a downloadable expanded FireRed game, unrestricted CPU-addressable ROM, or proof of compatibility with original GBA hardware.

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

The R6 milestone answers a crucial feasibility question for **emulator-assisted external assets**. The next task is to turn a tightly controlled proof into a reproducible, supportable workflow:

1. **Production integration:** move the host/resource handshake out of the test harness into an explicitly enabled, maintainable mGBA extension and a normal FireRed-side resource API.
2. **Engine support:** expand from one fixed-size static sprite source to additional asset types while handling decompression, allocation, ownership, resource lifetimes, DMA, audio and save-state identity correctly.
3. **Hacking tools and compatibility:** integrate resource IDs and packaging with editors/build systems; test fingerprinted game versions and modified ROMs instead of assuming universal compatibility.
4. **Release and regression:** provide runnable builds, clear setup instructions, measurable load times, fail-closed recovery and honest emulator/hardware support claims.

**Not yet proven:** a direct drop-in upgrade for existing `.gba` files, original-cartridge compatibility, ordinary stock-emulator support, arbitrarily large *simultaneously addressable* GBA memory, or a complete game expansion beyond 32 MiB.

## Earlier research and compatibility work

This breakthrough **builds on**, rather than erases, the repository's prior source-pinned hardware and ABI research:

- [Historical Phase 1 source-mapping status](docs/PHASE1_STATUS.md): `FAIL_INCOMPLETE`, including the 14,834-file inventory. Mapping and independent whole-file semantic approvals remain incomplete, but a full mapping pass is **not a prerequisite** for the demonstrated opt-in prototype.
- [34 native mGBA Matrix and cartridge regression checks](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40204719637): banking, ROM access, DMA, save and savestate behavior, including known unsafe behaviors. This is separate from the external-sidecar proof.
- [External resource/banking constraints](docs/PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md): GBA address-space realities and why existing 64 MiB Matrix banking is not the same as an open-ended sidecar resource protocol.

**XGBA is an experimental engineering project, not a finished ROM-hacking product.** But the distinction now matters: we have moved beyond a proposed design and demonstrated that a running GBA game can use validated external resources stored past its ordinary cartridge ROM window. The next challenge is to make that capability practical, reproducible, and available to the wider ROM-hacking community.
