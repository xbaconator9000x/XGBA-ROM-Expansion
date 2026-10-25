# XGBA semantic review v1.7 — game-resource consumers (source verified)

**Status:** focused source-backed function-level semantics, not whole-file or full Phase 1 clearance. All links use immutable commit SHA and verified Git blob SHA.

## Sprite and compressed graphics pipeline

[FireRed src/decompress.c:11–60](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/decompress.c#L11-L60) (`f4740f917ed9ae7e0fd967107e1e63733bb8c66a`) calls `LZ77UnCompWram(src->data, gDecompressionBuffer)` and hands an ordinary in-memory `SpriteSheet` or `SpritePalette` to the sprite loader.

[FireRed src/sprite.c:1476–1489](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/sprite.c#L1476-L1489) (`d0198d53004775c8664dcccf57833e178833776e`) allocates tile slots from `sheet->size / TILE_SIZE_4BPP` and copies the sprite bytes into `OBJ_VRAM0`. [Palette loading, 1575–1606](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/sprite.c#L1575-L1606) allocates/reuses one palette tag and writes to object palette memory.

[FireRed front pic registry](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/data/pokemon_graphics/front_pic_table.h) (`82af860d3006c8ca1c1d4c58ac35fb33e1ad025b`) is a `CompressedSpriteSheet` table populated by species-specific macros. Asset discovery must preserve this registry-to-sprite link and the runtime expectations of the decompressor and tile allocator.

**XS17-RESOURCE-STAGING:** An XGBA resource identifier is never interchangeable with `src->data` or a VRAM pointer. External sprite assets must be located, validated, staged/decompressed into bounded existing RAM space, and then handed to the **unchanged** tile/palette allocator with validated lengths. Original tile limits and tag semantics still apply.

**Missing tests:** source asset byte counts, worst-case decompression buffer size and overwrites, palette exhaustion, compressed format accuracy, lookup table range and species fallback, resource unloading and cache invalidation.

## Audio table and in-memory playback

[FireRed src/m4a.c:107–150](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/m4a.c#L107-L150) (`ebd3afe291b6c4e9f2ac62250a87c6a0482086d4`) indexes `gSongTable[n]`, selects `gMPlayTable[song->ms]`, and gives a raw `song->header` to `MPlayStart`. Playback checks cached header equality and music-player status.

**XS17-AUDIO-POINTER-IDENTITY:** A streamed song needs a stable in-emulator header address for its entire playback lifetime; swapping/releasing a cache window while `MPlay` still points at it is unsafe. Song-table ID bounds, player indices, sound channel scheduling and bank cache lifetime must be validated. Adding a MIDI to the bundle alone does not add a safe playable song.

**Missing tests:** concurrent songs and SE channels, cache eviction during playback, voicegroup and song header reference resolution, corrupt track streams and save-state restore of music state.

## Separate battle-script bytecode interpreter

[FireRed src/battle_script_commands.c:913–929](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/battle_script_commands.c#L913-L929) (`67f90a37044db87091b2174f78fe1e31ad2ef10d`) reads a pointer operand with `T1_READ_PTR(gBattlescriptCurrInstr + 1)` and jumps by assigning `gBattlescriptCurrInstr`. [1005–1028](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/battle_script_commands.c#L1005-L1028) uses conditional raw bytecode PC increments and pointer jumps.

**XS17-BATTLE-SCRIPT-ABI:** FireRed's field-script interpreter and battle-script interpreter are distinct raw-pointer consumers. A field-script-only extension cannot claim to support expanded battle scripts. A battle-specific relocation contract must preserve opcode operand widths, PC jump semantics, stack lifetime and existing special-case branches.

**Missing tests:** full opcode dispatch table, battle PC push/pop and nested script calls, bank switching during battle animation, invalid extended pointers, vanilla battle-script regressions.

## Scope and source integrity

- No implementation patches have been written.
- This document is a source-backed function-level review, **not** approval of entire files.
- These are at least three additional subsystem boundaries not fully covered by the v1.5 candidate mapping: sprite staging, audio header identity and battle bytecode.
- See [CPU/map/save semantic dependencies](SEMANTIC_DEPENDENCIES_v16.md) and [v1.5 core contracts](CRITICAL_SOURCE_CONTRACTS_v15.md).
