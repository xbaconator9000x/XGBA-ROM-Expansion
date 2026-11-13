# XGBA

**More game. Same GBA.**

What if a Game Boy Advance game could access substantially more content than you can squeeze into its cartridge ROM?

That's the question behind XGBA. I'm building an experimental way for compatible GBA games to **request maps, graphics, scripts and other resources from external storage while they're running**, instead of having to fit everything into one `.gba` file.

The dream? Massive games, enormous ROM hacks, and maybe even that mythical **nine-region Pokémon adventure**. Imagine making the game you actually want to make without spending half your life trying to find somewhere to put the assets.

**And no, we haven't built a playable nine-region game.** We're proving the underlying technology first, with real game engines, real emulator tests, and increasingly ridiculous stress tests.

> **Status — 14 November 2026:** Working experimental FireRed/Emerald external-resource integration; full three-ROM gameplay integration **not yet complete**. See [what works](#what-actually-works) and [the active integration PR](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123).

## The idea

Traditional GBA ROM hacking involves fighting cartridge space, repointing data and working around fairly unforgiving hardware limits. Bigger cartridge images, ROM banking, and multi-game cartridges are useful approaches, but they don't automatically give an existing game a clean way to fetch a world of new content on demand.

**XGBA takes a different approach:**

1. A deliberately XGBA-enabled game requests a named resource.
2. A modified emulator checks its source identity and the resource's integrity.
3. The emulator supplies that resource from an external **sidecar** package.
4. The game uses a bounded buffer in **real GBA working memory** to load it through its existing engine systems.

```text
    XGBA-enabled FireRed / Emerald
                  │
         Request resource ID
                  │
       Modified mGBA provider
                  │
       External resource packs
        (identity + SHA-256)
                  │
        Bounded 16 KiB pages
                  │
     Existing GBA RAM / VRAM
                  │
     Actual game-engine assets
```

The executable game still runs as a GBA game. We are **not** claiming that the GBA suddenly has unlimited RAM, VRAM, or directly addressable ROM. The additional capacity is **external storage**, fetched in manageable pieces. Host storage and emulator support still impose limits, and a new resource format doesn't magically remove limitations in the game engine itself.

That distinction matters. A **64 MiB cartridge image** is still a larger *cartridge image*. A multicart menu that boots several games isn't one continuous game world. XGBA is experimenting with something else: a way for a running game to use a separately managed pool of content.

## What actually works

There's a lot of code here now, but I'd rather be precise about what it proves.

| Capability | Current state |
| --- | --- |
| Real compiled FireRed fetching assets beyond the ordinary 32 MiB ROM window through modified mGBA | **Verified** — original game code, native emulator execution and OBJ VRAM checks |
| Emerald maps, tilesets, sprite/resource lifetimes, battles and Flash-save recovery | **Verified in controlled native integration tests** |
| Game-engine scripts using externally supplied, **test-authored** data with real flags, inventory and save recovery | **Verified** — not the same as executing a foreign ROM hack's entire original script system |
| Original Emerald, Team Rocket Edition 3.06 and Heart & Soul 2.0.6 resource inventory | **Preserved and source-qualified** in private original-ROM-derived data |
| Real Rocket source NPC frames, palettes and terrain for the first target map | **Extracted and integrity-checked**; first-viewport adapter and Fly UI are in the [draft integration PR](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123) |
| One uninterrupted, playable Emerald → Rocket → Johto → Emerald journey | **Not yet demonstrated** |
| One-click expansion of any clean or already modified ROM | **Long-term goal**, not a released tool |
| Stock mGBA or original GBA hardware running expanded sidecars | **Not supported by these experiments** |

For a sense of scale, our private original-ROM intake currently accounts for **2,856 populated maps, 17,089 NPC placements, 7,146 warps, 2,340 coordinate events and 4,697 background interactions** across the three games. The source identities are preserved; we aren't simply renumbering everything and hoping for the best.

Preserving that data is an important milestone. **Making every part of it work together is a different, much harder job.**

### Evidence, without the 50-page changelog

- [R6 — real FireRed/mGBA external graphics proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940797581): external asset beyond the standard ROM window, checked in the game's actual graphics path.
- [R40 — original Emerald executing an external script and cold-reloading Flash state](docs/R40_REAL_EMERALD_EXTERNAL_EVENT_FLASH.md).
- [R42 — two source-labelled, authored events running through Emerald's actual engine](docs/R42_NATIVE_TWO_SOURCE_IN_GAME_MECHANICS.md).
- [R45 — original assets from all three games shown inside a native mGBA map viewer](docs/R45_ACTUAL_THREE_ORIGINAL_ROM_NATIVE_MAP_EXECUTION.md). **A viewer is not a playable three-game integration.**
- [R51–R62 — active original-Emerald three-world integration](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123): source-aware maps, original graphics, Fly selection, Rocket assets and private host-provider checks. **The end-to-end gameplay acceptance is still pending.**

The [historical README and milestone log](docs/archive/README_PRE_REWRITE_2026-11-14.md) retains the older detailed evidence instead of dumping it all onto the front page.

## The big test: three actual games, one running Emerald

To stress this properly, we're not merely injecting three sample maps and calling it a day. We're working from the **original, user-owned ROM data** for Pokémon Emerald, Team Rocket Edition and Heart & Soul, aiming to retain all relevant content: maps, events, scripts, NPCs, graphics, Pokémon data, battles, music, progression and game state.

The next real acceptance test is deliberately straightforward to describe, even if implementing it is anything but:

1. **Start in actual Emerald.** Fly to a location supplied from the original Team Rocket Edition.
2. **Play a genuine Rocket map.** See its real geometry and original sprites; interact with an original NPC, run the original dialogue and compatible script effects.
3. **Continue to Johto.** Enter the original Heart & Soul Goldenrod map with its own assets and interactions, without trampling Emerald or Rocket IDs.
4. **Return to Emerald.** Retain party, bag, relevant flags and progress; save through actual Flash and prove the result after a cold emulator restart.

A homebrew showcase, static reconstruction, fabricated NPC conversation or a screenshot that merely *looks* like Pokémon won't count as passing this test. The real engine has to do the work.

The acceptance criteria are documented in [the full-content integration contract](docs/R47_COMPLETE_THREE_GAME_CONTENT_ACCEPTANCE.md). **We are not there yet.** The largest remaining work is getting complete original foreign assets into the live engine, safely translating foreign scripts/warps and maintaining separate source namespaces within one reliable game state.

## Where I want to take it

**First: make the three-ROM integration genuinely playable.** Finish original art, animation handling, live map/NPC paging, foreign-script compatibility, cross-world state and rigorous emulator evidence.

**Then: make it useful to ROM hackers.** A game expansion method isn't much use if you need to rewrite half an engine by hand. I want editor and emulator integration that lets people manage external resources inside their usual tools, with compatibility checks and clear failures instead of silent corruption.

**Eventually: make expansion boring.** Select a supported ROM, validate it, patch it, and carry on building. Ideally that applies not only to vanilla FireRed/Emerald but to compatible existing ROM hacks as well. That is the ambition—not a claim of universal compatibility today.

If a nine-region game ever becomes practical because of this, fantastic. But even much smaller projects could benefit from no longer treating cartridge space as the final word on their scope.

## Building, testing and contributing

This is a **developer-stage experiment**, not a consumer download or a general ROM patcher. The source, native mGBA integrations, versioned resource formats, test harnesses and CI workflows are in this repository. Some end-to-end tests require pinned upstream FireRed/Emerald and mGBA source checkouts, ARM toolchains and opt-in experimental patches.

Start with [the architecture notes](docs/xgba-integration-architecture.md), the [memory and resource-lifetime policy](docs/xgba-memory-virtualization-policy.md), or the [current three-game acceptance contract](docs/R47_COMPLETE_THREE_GAME_CONTENT_ACCEPTANCE.md). For a public, source-safe smoke test of the private resource-fusion logic on the active development branch:

```bash
git clone https://github.com/xbaconator9000x/XGBA-ROM-Expansion.git
cd XGBA-ROM-Expansion
git switch integration/r51-original-three-world-grid-native-20261113
PYTHONPATH=tools:tests python3 -m unittest test_xgba_r62_private_original_provider_bundle -v
```

That public test uses **authored fixtures**, not copyrighted ROM bytes. The actual original-ROM asset packs are kept private. See [GitHub Actions](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions) for execution evidence and [PR #123](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123) for the current integration changes and unresolved blockers.

**AI disclosure:** I use AI extensively to help develop, test and document XGBA. I'm not hiding that. But AI-written code and a green unit test are not a substitute for the game actually working. Claims here are deliberately tied to executed tests and their limitations.

**A note on original games:** This repository does not distribute commercial Pokémon ROMs or extracted copyrighted game assets. Original-ROM-derived validation is performed privately with source-identity and integrity checks.

---

**The short version:** We've demonstrated that an actual running GBA game can fetch and use verified data from outside its ordinary cartridge ROM space. That's a genuinely interesting foundation. Now I want to turn it into something ROM hackers can actually use—and ultimately make some gloriously oversized games with it.
