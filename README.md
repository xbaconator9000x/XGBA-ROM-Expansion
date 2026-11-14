# XGBA — Expanding GBA game resources

XGBA is an experimental project exploring how Game Boy Advance games can access substantially more content than fits inside a conventional cartridge ROM.

The approach is to let an **XGBA-enabled game** request additional maps, graphics, scripts and other resources from external files through a **modified emulator**. The game still runs its original GBA engine and uses its actual working memory. The extra storage is not a larger block of directly addressable GBA ROM or RAM.

My longer-term aim is to make this usable for ROM hacking: not just custom-built demonstrations, but eventually a repeatable expansion process for supported vanilla games and already modified ROMs, with editor and emulator integration.

> **Status — 14 November 2026:** External resource loading has been demonstrated in real FireRed and Emerald engine tests. Three-ROM integration is under active development, but an uninterrupted Emerald → Team Rocket Edition → Heart & Soul → Emerald playthrough is **not yet demonstrated**. See [current progress](#what-we-have-demonstrated) and [draft PR #123](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123).

### Latest verified engineering evidence — 15 November 2026 (R95)

- Draft [PR #123](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123), exact implementation head [`6f3f175dd086fe33642537630ea03c300fbdb606`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/6f3f175dd086fe33642537630ea03c300fbdb606): **13/13 PR-triggered workflows returned by the GitHub commit-run query completed successfully**. [R51 native original Emerald ARM/mGBA/Flash](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43614274854) completed 6/6 tests in 107.496 seconds; its source-geometry integrity job passed. [R56 original OBJ admission](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43614274807) passed native 16-bit source-ID, metadata/frame/palette/OAM-animation CRC, negative rejection and no-public-ROM-byte checks. These are **exact-head public source and authored-fixture tests**, not a completed private original-ROM gameplay acceptance.
- **R93–R95 Heart & Soul progress:** source-built official HnS v2.0.6 Goldenrod map/tileset and Boy2 graphics ID 406 are integrated into the source-authenticity pipeline with original palette/OAM/animation contracts. A source build and verified asset identity do **not** establish correct live Goldenrod LCD rendering or fully functional original NPC scripts in Emerald.
- **R84 Flash safety remains in force:** foreign-world saving is refused before Flash writes rather than claiming a successful shared save. Normal Emerald-only saving remains available. This is not multiworld persistence.
- **Still unverified:** original-ROM Emerald → Rocket → Heart & Soul → Emerald playable Fly, original foreign NPC script execution, original Heart & Soul rendering in Emerald gameplay, and shared Flash save with cold restart. No public original ROM bytes, saves or proprietary provider packs are included.

## What XGBA is

A GBA cartridge ROM has a limited CPU-visible address range. XGBA separates **where resources are stored** from **where a running game needs them in memory**.

The current prototype uses these components:

1. **A patched GBA game**, built or instrumented to request a resource by ID at specific points in its existing engine.
2. **A modified mGBA emulator** that handles those requests and retrieves data from external resource packages (sidecars).
3. **Source and integrity checks**, including original-ROM identity, resource identifiers and SHA-256 hashes, before the host supplies data.
4. **Bounded transfers**, typically using 16 KiB resource pages and carefully managed EWRAM lifetimes. Graphics ultimately reach normal GBA VRAM through real game-engine code.

```text
GBA game (real FireRed / Emerald engine)
                |
        Resource request
                |
      Modified mGBA provider
                |
   External integrity-checked files
                |
     Bounded transfer into RAM
                |
  Native game loaders / RAM / VRAM
```

The emulator provides additional *storage access*. It does not remove the GBA's CPU, graphics, memory-bandwidth or game-engine constraints. It also requires deliberate support from the game and emulator; a normal `.gba` file in an unmodified emulator does not acquire this functionality by itself.

## Why I started it

The normal approach to making a larger GBA game is to fit everything into the available cartridge space, repoint data, optimise assets, replace content or build around the engine's limits. Those techniques work, but space management becomes a substantial part of development as a project grows.

Other approaches address parts of this problem. Larger 64 MiB ROM configurations and banking can increase or rearrange cartridge storage, while multicarts can hold several games. Neither is automatically a way for **one running game** to request an arbitrary, source-verified resource collection outside its cartridge image, or to share a coherent world and save state across multiple games.

XGBA is an experiment in that latter model. I want storage capacity to become less of a constraint on the *scope* of a project, without ignoring the real hardware and engine limits that remain.

Pokémon is a useful proving ground: multiple regions mean extensive map data, tilesets, NPCs, events, species, music and progression state. A nine-region game is an ambitious possible application, **not a feature XGBA can currently deliver**.

## What we have demonstrated

The project has progressed beyond storage-format tests. Several stages have been executed in real, source-built FireRed or Emerald running under a pinned, modified native mGBA build.

| Area | Demonstrated result | Important boundary |
| --- | --- | --- |
| **External graphics** | Actual FireRed game code retrieved a validated resource stored beyond the usual 32 MiB cartridge window and loaded it into OBJ VRAM. | The result requires patched game and emulator code. |
| **Engine integration** | Emerald source-built map, tileset, object-graphics and battle tests exercise bounded resource loading, allocator pressure, DMA/VRAM lifetimes and map transitions. | These are controlled integrations, not a complete foreign game. |
| **Persistence** | The real Emerald Flash-save path has saved externally supplied **test-authored** event effects; a separate cold emulator process recovered those flags, variables and items. | This does not yet establish one shared save across three original games. |
| **Original game data** | The private intake for Emerald, Team Rocket Edition 3.06 and Heart & Soul 2.0.6 preserves source-qualified map identities, NPCs, warps and other event records. | Source data preservation is not the same as executable compatibility. |
| **Foreign graphics integration** | Original Team Rocket Edition tilesets, NPC frames and palettes have been extracted, checked and assembled into private provider resources; native Emerald adapters and Fly-screen selection exist in the development branch. | A live, playable Fly into the original Rocket world has not passed. |

The original three-game inventory currently contains **2,856 populated maps, 17,089 NPC/object placements, 7,146 warps, 2,340 coordinate events and 4,697 background interactions**. Those counts describe source records collected and preserved, not content that has all been made playable.

### Selected evidence

- [R6: original FireRed external graphics and OBJ VRAM verification](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940797581).
- [R40: original Emerald interpreter and Flash cold-restart test](docs/R40_REAL_EMERALD_EXTERNAL_EVENT_FLASH.md).
- [R42: authored external events running through actual Emerald gameplay systems](docs/R42_NATIVE_TWO_SOURCE_IN_GAME_MECHANICS.md).
- [R45: private original assets from three games rendered in a native mGBA map viewer](docs/R45_ACTUAL_THREE_ORIGINAL_ROM_NATIVE_MAP_EXECUTION.md). This was **not** a three-game overworld.
- [R51–R62: current original-Emerald multi-world integration and original Rocket resources](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123) (draft; full gameplay acceptance pending).

The more detailed development record is retained in the [historical README archive](docs/archive/README_PRE_REWRITE_2026-11-14.md), with individual engineering reports under [docs](docs/).

### Current integration test: three original Pokémon games

Our present stress and compatibility target is to bring the relevant original content of **Pokémon Emerald, Team Rocket Edition and Heart & Soul** into one Emerald-based running game, rather than selecting a few representative maps and treating them as the finished result.

The immediate acceptance path is:

1. Play in the **actual Emerald engine**, then use its Fly interface to enter an original Rocket Edition map.
2. Render the **original Rocket geometry and sprites**, interact with an original NPC, execute its compatible original dialogue and script, and retain the correct source identity.
3. Continue to **Heart & Soul's Goldenrod**, with its original assets and events, without mixing map IDs or game-state namespaces.
4. Return to Emerald, verify the relevant party, inventory, flags and progression, **save to Flash**, and recover that state after a cold restart.

This is a test specification, **not a completed playthrough**. The original-art pipeline, live map/NPC paging, script relocation and compatibility, source-specific state and complete save recovery all require further work. The acceptance requirements are defined in [R47's full-content contract](docs/R47_COMPLETE_THREE_GAME_CONTENT_ACCEPTANCE.md).

## What this could mean for ROM hacking

If we can turn the architecture into reliable tools, there are several practical implications for the community.

- **Larger playable projects.** Maps, graphics, dialogue and other resources could be stored outside the cartridge and loaded when needed. Projects would still need to respect game-engine and working-memory limits.
- **Multi-region and multi-source development.** A game could eventually draw from substantially larger collections of world data, with explicit identifiers to prevent maps, scripts or other records from different sources colliding.
- **Less destructive content management.** Instead of routinely removing or replacing assets to make space, compatible projects could manage additional resources as separate packages.
- **Better workflows for creators.** ROM editors, build pipelines and emulators could eventually support these packages directly, making the process more accessible than hand-editing engine code and pointers.

I don't think the interesting result here is merely a bigger ROM file. It's the prospect of a **game accessing a larger body of content during gameplay**, with the emulator handling storage and the engine loading what it needs.

XGBA isn't necessarily the first exploration of expanded GBA storage or emulator-side extensions, and it doesn't supersede cartridge banking, multi-ROM collections or other approaches. The intended contribution is a validated, reusable path for **game-initiated external resources**, particularly for existing GBA engines and ROM-hacking workflows.

## Future plans

Development is currently organised around four connected goals.

**1. Finish executable three-ROM integration.** Complete original Rocket and Johto graphics and animations, on-screen NPC loading as the player moves, native Fly/warp transitions, original script and event compatibility, battles, source-scoped state, and Flash save/recovery. Verify it in the real Emerald engine with emulator traces and actual gameplay captures.

**2. Generalise the expansion system.** Move beyond the current test maps and resource types. Improve paging, prefetching, decompression, DMA ownership, cache eviction, resource lifetimes, integrity recovery and performance under sustained gameplay. Investigate what engine structures must change to support very large maps and resource catalogues.

**3. Support already modified ROMs.** Explore compatibility-aware patching of supported FireRed/Emerald derivatives and existing hacks. This needs executable/version detection, pointer and patch-conflict analysis, rollback and tests; it cannot safely be assumed to work for every ROM.

**4. Integrate with the tools people already use.** Provide editor, build-tool and emulator support for importing, organising, expanding and exporting external resources. The longer-term goal is a straightforward patch-and-edit workflow, rather than a custom engineering exercise for each game.

Additional work on **extended EWRAM/IWRAM/VRAM capabilities** is being investigated separately. That is a different problem from storage expansion, and any emulator-assisted memory changes will require their own hardware-compatibility and performance evidence. See the [memory policy and architecture notes](docs/xgba-memory-virtualization-policy.md).

## Current limits and project access

XGBA is **experimental**, not a released universal ROM expansion patcher.

- The working system presently depends on **modified mGBA and explicit game-side integration**. Stock emulators and physical GBA hardware are not established targets for these external resource packs.
- The amount of content stored externally may grow far beyond a normal ROM image, but **simultaneously usable RAM, VRAM, bandwidth, map structures and engine behaviour are still bounded**. “Indefinite expansion” is a design ambition, not a measured infinite capacity.
- Full original Team Rocket Edition / Heart & Soul script execution, shared progression and an uninterrupted three-world journey **remain unproven**.
- Private source-ROM processing is used to check original game assets and resource identity. **This public repository does not distribute commercial ROMs or extracted copyrighted graphics and scripts.**

For technical details, start with the [integration architecture](docs/xgba-integration-architecture.md), the [three-ROM acceptance criteria](docs/R47_COMPLETE_THREE_GAME_CONTENT_ACCEPTANCE.md) and the [current development PR](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123). See [GitHub Actions](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions) for reproducible public tests; private original-ROM validations are identified separately.

For a source-safe example on the current integration branch:

```bash
git clone https://github.com/xbaconator9000x/XGBA-ROM-Expansion.git
cd XGBA-ROM-Expansion
git switch integration/r51-original-three-world-grid-native-20261113
PYTHONPATH=tools:tests python3 -m unittest test_xgba_r62_private_original_provider_bundle -v
```

This test uses authored fixtures; it does not require or include copyrighted game ROMs.

**AI disclosure:** I use AI assistance for implementation, testing, research and documentation. The work is evaluated through source inspection and reproducible tests. I distinguish between verified native game execution, authored test data, source-data imports and functionality that has not yet been implemented.
