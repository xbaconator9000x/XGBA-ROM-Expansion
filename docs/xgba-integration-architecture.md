# XGBA integration architecture — ADR 001

**Status:** Proposed implementation direction; approved native milestones R6–R14 are evidence, NOT proof that all interfaces below exist. R15 ordinary in-game Flash persistence and clean reboot are still outstanding.

## Decision

**XGBA is a versioned runtime + pack format + builder, not a redistributable universal Pokémon ROM and not a feature tied to any one editor.** Use three composable authoring paths:

1. **Source/decomp adapter (preferred for initial robust integration):** link XGBA guest hooks, relocation tables and resource IDs into a user-built FireRed decomp project. Retain native ROM code and direct game pointers inside the original 32 MiB window.
2. **Binary installer/patcher (supported, specific known ROM revisions):** verify the user's own original ROM by exact hash; produce a patched ROM on their machine plus validated external packs; refuse unrecognised, previously modified or conflicting ROMs unless an explicit compatibility profile exists. Distribute code and deltas, not Nintendo ROM data. Use an input-verifying patch format (e.g. BPS) where feasible.
3. **Editor adapters:** PokéBacon Studio first, Hex Maniac Advance automation/export second, other editors later. Editors author resource definitions, generate/rebuild packs, and call the same XGBA builder; no editor gets an incompatible proprietary fork of the pack format.

These authoring paths all generate **the same runtime contract**, not three different engine implementations.

## Runtime layers and ownership

| Component | Responsibility | Earliest usable version |
| --- | --- | --- |
| XGBA guest runtime (ROM-side) | Stable resource IDs; scene dependency requests; correct map/battle hooks; budgeted RAM/VRAM residency; save/cold-reset invalidation; fallback handling | R14 proved two map layouts/secondary tilesets; R15 and later generalize |
| Resource manifest and pack format | Versioned resource IDs; target game identity; source hashes; logical 64-bit offsets; per-pack actual file segment; compression; dependencies; content SHA-256 | Current sidecar v1 supports exact source identity + bounded resources; multi-pack virtual addressing needs a versioned extension |
| Compiler/pack builder | Convert editor/source assets to GBA-native formats; resolve native pointer/relocation IDs; validate scene budgets; emit patches and packs; reproducible asset manifests | New work, can reuse R14 pack extraction and R15 budget planner |
| Emulator bridge | Resolve/resource-read sidecars; opt-in feature negotiation; host-side immutable caches; bound and verify transfers; manage failure and save lifecycle | Native patched mGBA provider already demonstrated on R7–R14 |
| Distribution/launcher | Locate ROM, versioned packs and save files; verify compatible pairs; launch opted-in emulator; gracefully explain missing capabilities | New work |
| Editor integration adapters | Author/import/export game maps, sprites, battles, scripts and pack references; permit live tests against runtime | PokéBacon integration planned; HMA scripting feasible for limited patch automation, not assumed to support editing 64-bit external assets natively |

**Ordinary mGBA and other existing emulators do not automatically understand XGBA sidecars.** The first compatible runtime is a patched mGBA core/build. A standalone dynamically installable emulator plugin is an attractive future packaging target, but depends on each emulator exposing usable extension hooks. Do not promise universal plug-in compatibility before verifying it. A future Libretro core, enhanced stand-alone mGBA build, or other emulator port may reuse the same versioned resource provider.

## Canonical output

A *user-generated* build can be presented as:

    MyHack/
      MyHack.gba               # patched from author's own source ROM; not in XGBA repo
      MyHack.xgba.json         # sidecar manifest with version and ROM/content identity
      packs/
        maps.xgbapack
        pokemon.xgbapack
        battles.xgbapack
        audio.xgbapack
      saves/                   # private; not included in public evidence or distributions

The names/extensions above are illustrative, not committed as a final binary spec. The manifest should link package identity and exact base/runtime versions, not assume that a filename identifies the correct ROM.

A public creator download generally contains an XGBA project/patch and appropriately licensed original expansion content. A user supplies their own legitimate source ROM where required, and the installer verifies it before patching. The tool must not distribute original complete Nintendo ROMs or raw assets embedded in a reconstructed base ROM.

## Handling resources from offset 74 and 67,987,873,254,192

A resource has two separate address domains:

- **Logical virtual storage address**: 64-bit resource identifier/offset, can be tens of terabytes from zero.
- **Actual host backing**: a file shard or object identified by pack ID and a separately validated file seek offset; never allocate a gigantic sparse file merely because a logical offset is large.
- **Guest resident address**: only where the *current* scene stores bytes in native GBA EWRAM/IWRAM/VRAM or references original ROM. A 64-bit storage offset is never itself a GBA CPU pointer.

A room can have original ROM tiles, near-offset external data and distant-offset external tiles **at once**. A gym battle can have local and multiple external Pokémon, plus separately streamed animation and music resources. For each live scene the XGBA compiler must build a dependency/residency plan that includes all simultaneously needed data in the relevant native pools. At runtime use source-ID-based resource requests, stage verified chunks, populate actual GPU tiles/palettes where needed, prefetch upcoming frames, and release memory after the previous consumer is finished. The phase-aware planner is a model and must be validated against actual game activity.

**Do not require that source assets in different external files live at different GBA CPU addresses.** Only simultaneously resident, conflicting data need disjoint physical locations; another phase may reuse the same protected staging arena after safe eviction. Hardware resets invalidate RAM/VRAM residency, regardless of whether a host-side immutable cache remains warm.

## Editor choices

**PokéBacon Studio**: Implement full XGBA awareness as part of the project's data model: external asset browser, resource IDs, pack assignment, relocation audit, memory budget warnings, build/export, test in XGBA-enabled emulator. Keep editing experience normal for users; backend chooses which objects go in local ROM or external packs. Device/Android support is a separate deployment gate.

**Hex Maniac Advance**: Its .hma scripts and Python automation can install some known hooks/metadata and export definitions; it currently primarily edits data in the opened ROM and must not be treated as a native 64-bit external pack editor without our own adaptation. A companion importer/exporter can bridge HMA-edited ROM contents to the XGBA build system. A dedicated plugin/fork is only appropriate if its public extension surface is insufficient for the user experience.

**Decomp / Porymap / existing tooling**: Build adapters/CLI that take map data, species tables, animations and native compilation output and emit versioned pack references. Avoid expecting universal binary patching after arbitrary third-party hacks; provide compatibility profiles and fail closed on unknown code/data layouts.

## Installer modes

- **Source build:** for advanced creators, patch/link XGBA guest loader into supported decomp, compile exact ROM and sidecars, run native tests.
- **Clean-ROM patch:** for ordinary users, exact input hash + targeted verified patch profile -> local patched ROM and compatible packs. BPS checks source identity; a binary patch by itself is not an emulator extension.
- **Editor export:** editors invoke the exact same builder and show equivalent output/diagnostics.

The game ROM needs runtime loader hooks *and* an XGBA-enabled emulator to fetch the packs. Installing only an HMA script, only a .gba patch or only an editor extension is insufficient for arbitrary external runtime data.

## Future EWRAM/VRAM expansion

Keep optional extra guest EWRAM mapping and PPU/VRAM extension as **separate, versioned emulator capabilities**. They are not R15 prerequisites. A normal XGBA pack should function in current native limits where its scene budgets fit, even if a future enhanced emulator supports a larger working set. Never silently change real GBA memory semantics in compatibility mode. See [memory virtualization policy](xgba-memory-virtualization-policy.md).

## Near-term execution order

1. **Finish R15 native Flash save/close/reopen/continue proof.** Ensure sidecar re-acquisition after a cold start, and defined behaviour on missing/wrong pack. Preserve screenshots and exact-head CI.
2. Define versioned **XGBA manifest v2** with source identity, multiple independently hashed pack shards, stable resource IDs, 64-bit logical offsets and safe actual file offsets; implement deterministic pack builder and backwards-compatible v1 reader.
3. Extract common guest resource-manager implementation from R14 one-off loader; integrate the phase-aware residency planner into actual map transitions and battle asset loads; enforce native EWRAM/VRAM/palette usage against actual Free/used allocators.
4. Provide a **FireRed source-build kit** plus a hash-checked patcher for a known clean ROM only. Do not declare compatibility with arbitrary existing modified ROMs.
5. Ship a compatible **XGBA mGBA runtime/launcher** with version handshake, save file ownership, integrity reporting and clear unsupported-emulator errors. Test graphical emulator/audio, not just headless CPU frames.
6. Add PokéBacon XGBA export and limited HMA automation/import adapter once the pack format and loader interfaces are stable.
7. Revisit opt-in expanded EWRAM/PPU only if measured scene or battle budgets still demand it after proper streaming and caching.

## Definition of success

A creator can import or build a legitimate supported ROM, author assets in their preferred tool, produce a small supported patched ROM and external packs, play an uninterrupted house-to-outdoor-to-battle sequence with simultaneously required original/external Pokémon/assets, save normally, close and restart the compatible emulator, continue from Flash, and reproduce the same scene with validated correct backing resources. Exact-head native CI plus archived LCD PNG/GIF and verification reports support each claim; simple planner/unit test passes are not sufficient to label the runtime end-to-end complete.

**This ADR is architectural direction, not an assertion that these deliverables already work.**
