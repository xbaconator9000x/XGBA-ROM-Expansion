# R47 authoritative objective — full three-original-ROM game integration

**Status: requirements and acceptance contract. Not implemented/verified gameplay.**

> The objective is **not** to place a few genuine maps inside an expanded emulator.
> It is to make the complete relevant content from **Pokémon Emerald (U)**,
> **Unofficial Team Rocket Edition 3.06**, and **Pokémon Heart & Soul 2.0.6**
> coexist and *function during real Pokémon gameplay* in one expanded runtime.
> The immediate next milestone is **talking to an original imported NPC, seeing
> their actual dialogue, executing their original event, and saving its state**.
> No source-labelled text, invented sample NPC, synthetic substitute script,
> offline image, sprite viewer or metadata counter satisfies this milestone.

This is the project's **authoritative full-scope acceptance contract** for
all future work. Roadmaps, watchdog runs and progress summaries must not
narrow the objective to a few cherry-picked maps.

## Three original sources and existing baseline

Real private, read-only R41/R46 inventory (original user ROMs, 13 Nov 2026):

| Full original content class | Emerald | Rocket 3.06 | Heart & Soul 2.0.6 | Aggregate |
| --- | ---: | ---: | ---: | ---: |
| Original populated maps | 518 | 1,778 | 560 | **2,856** |
| NPC/object event placements | 2,941 | 9,410 | 4,738 | **17,089** |
| Warps | 1,313 | 4,399 | 1,434 | **7,146** |
| Coordinate-trigger events | 375 | 1,378 | 587 | **2,340** |
| Background interaction events | 720 | 2,923 | 1,054 | **4,697** |
| Map group slots incl. holes | 518 | 1,778 | 1,495 | **3,791** |
| Valid original map script roots | 518 | 1,778 | 560 | **2,856** |

Heart & Soul's 935 inactive/zero map slots must remain holes, **not
renumbered**. A total of 2,088 unique numeric map IDs exist across the
three games, including overlapping identities; use the key
`(source_id, original_group, original_map)`. R46 already implements a
bounded, source-aware C11 warp lookup and a 16 KiB external-index page
reader, but it is **not yet hooked into original Emerald's active overworld**.

### Direct original NPC-to-script pointer census (private read-only ROM scan)

In addition to the R41 aggregate, an independent R47 source-ROM walk followed
each populated map's original event-object array and examined every object's
native 24-byte record and original script reference at offset 0x10:

| Source | Total original object records | Script pointers inside same original ROM | Null/no script pointers | Unusual non-ROM values |
| --- | ---: | ---: | ---: | ---: |
| Emerald | 2,941 | 2,163 | 778 | 0 |
| Rocket Edition 3.06 | 9,410 | 7,167 | 2,242 | **1** |
| Heart & Soul 2.0.6 | 4,738 | 2,458 | 2,280 | 0 |
| **All three** | **17,089** | **11,788** | **5,300** | **1** |

All 2,856 original object-array headers and physical object counts parsed
consistently. The one unusual Rocket object is **source Rocket, original
map group 19/map 10, object local ID 14**, with raw script field `0x000003E0`;
it may encode a source-engine special case and must **not** be dropped,
rewritten, or treated as an ordinary script address without further evidence.
Null script values can be legitimate and must not be discarded either.

Known **original NPC test candidates** for the first in-engine talk test
(with original pointer provenance, not invented dialogue):

- Emerald Littleroot 0:9, original object ID 1, (16,10), script ROM offset
  `0x1E8034`, graphics ID 6
- Rocket Littleroot 0:9, original object ID 1, (18,10), script ROM offset
  `0x215555`, graphics ID 6
- Heart & Soul New Bark 0:0, original object ID 1, (20,18), script ROM
  offset `0x38E3DF`, graphics ID 416

These are real script **pointers**, not evidence that their dialogue
or custom engine commands can execute under vanilla Emerald. The first
gameplay acceptance test must resolve and execute the selected original
script in the actual guest interpreter and verify real resulting dialogue
and state.

These counts cover **map-linked objects/events** only. A full integration
also requires independent inventories for every other game-specific
resource class, rather than treating the above totals as complete.

## What "the whole kit and tackle" means

- **Original game worlds:** full source map tables and metadata, connections,
  entrances, interiors, border tiles, primary/secondary tilesets, palettes,
  collision and elevation, object graphics, animations, music and ambience,
  map-specific weather, movement, following and camera behavior.
- **Real NPCs and interactable world:** original map object-event records,
  sprite/graphics IDs and movement behavior, facing/direction, trigger
  coordinates and sight ranges, the **actual original script bytes**,
  dialogue strings, text encoding, choices, gifts, hidden items, signs,
  trainer challenges, shops, healing, special handlers and story events.
- **All battle/game data:** original trainer rosters, Pokémon/species,
  forms, moves, abilities, items, parties, encounters, encounter tables,
  trainer AI, scripts, evolution data, sprites and battle graphics,
  custom game-specific data, and associated script/engine dependencies.
- **Game logic:** original triggers, source-specific flags, variables,
  specials/native script callbacks, quest progression, shared storage/party
  and inventory semantics, event dependencies and cutscenes.
- **Persistence:** source-aware current location and warps, trainer defeat
  and NPC interactions, item ownership, flags/variables, quest progress,
  parties, storage, Pokédex where compatible, original Flash saves,
  emulator cold restart, and no corruption of other source worlds.
- **Compatibility:** preserve original IDs within each world, translate
  references explicitly, identify unsupported opcodes/engine behaviors,
  and fail closed on unknown commands. Do not silently reroute a failed
  foreign script to a synthetic Emerald action or discard unsupported content.

**Preserve all relevant original source data and its provenance, even when
some class is not yet executable.** Rejected/unimplemented data must remain
addressable in an intact external source store and be counted in coverage
reports. A successful map conversion may not count as completion of its
associated NPCs, text, scripts, collision, encounters or save semantics.

## Required acceptance tests (in this order)

1. **Whole-source intake:** all three ROMs' bytes verified privately against
   known SHA-256 identities. Produce manifest and source-aware indexes of
   all relevant map, graphics, object/NPC, script, string, trainer, item,
   Pokémon, battle, encounter, audio, flag/var, warp and save resources.
   Report retained, rejected, unsupported and executable counts *per source
   and per resource class*. No silent omissions. This is an **intake gate**,
   not a gameplay pass.
2. **Original-engine foreign map:** a source-built **original Pokémon
   Emerald game engine** inside patched mGBA uses XGBA to fetch a real
   Rocket Edition / Heart & Soul map with its graphics, collisions,
   actual walkable player, object/NPC spawns, camera and original warp
   destinations. Show authentic native-emulator LCD evidence and guest-side
   map/source identity, not an offline rendering or a homebrew map viewer.
3. **REAL NPC conversation:** select a known named or otherwise identifiable
   NPC from each foreign ROM, preserve its exact original map placement and
   reference to its original script. Walk up using **actual D-pad inputs**,
   face/interact via A, render the **original dialogue text**, trace
   original script bytecode/pointer provenance and verify changes in actual
   guest flags, variables, inventory, party or trainer state as appropriate.
   Include normal/alternate/second-interaction branches. The test must
   **fail** if dialogue is substituted or the source script never runs.
4. **Full event-graph coverage:** repeat across representative but diverse
   real NPCs, story cutscenes, choices, trainers, shops, gifts, hidden
   items, conditional dialogue and custom engine specials. Enumerate all
   script roots and unresolved dependencies, ultimately execute the
   complete relevant event catalog. A few NPCs are **acceptance probes
   of the implementation**, not the scope limit.
5. **Connected multi-world gameplay:** actual walking through original
   warps, arrival and connected map transitions, source-local numeric
   overlaps, deliberate cross-world portals, collision and object
   restoration after battles/warps. No host-written in-game fake position.
6. **Real battles and persistent state:** original trainer and wild battles
   with source trainer/party/battle behavior, item rewards and flags.
   Flash save via the game's actual routines, cold-restart emulator, verify
   the exact chosen NPC's new dialogue branch, trainers, inventory,
   all three worlds' quest namespaces and source-aware location retained.
7. **Playable expanded emulator release:** hand the user an installable
   compatible Android patched emulator and private game/source pack, with
   exact import instructions and tests on physical Android. Don't mark
   emulator/hardware tests passed unless they were actually executed.

## Evidence and reporting discipline

A milestone claim must identify **which exact original ROM resource** was
used and how it reached the executing guest, ideally using:

- original source ROM SHA-256 + source-local group/map/object ID;
- original object/script ROM offsets and pre/post game state;
- native patched mGBA emulator build and real GBA frame screenshots/GIF;
- XGBA external reads, integrity checks, EWRAM lease/VRAM evidence;
- real input sequences, actual original engine callback and script context;
- save + cold-restart round-trip results and outstanding compatibility gaps.

**Do not count as native original-engine integration:** R41 structural
checks, R42 source-themed authored scripts, R43 labelled-data homebrew,
R44 offline reconstructions, R45 source-derived homebrew map viewer, or
R46 native routing ABI by itself. All remain useful prerequisite
engineering results, but **not the requested three-ROM playable test**.

Original commercial ROMs and private derived resource packs remain local
and must never be committed to public GitHub or public CI artifacts.
