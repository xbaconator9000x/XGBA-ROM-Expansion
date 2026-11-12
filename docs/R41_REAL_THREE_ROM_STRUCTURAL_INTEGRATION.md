# R41 — Actual user-supplied three-ROM intake, authentic sparse Heart & Soul maps, collisions

**MERGED/VERIFIED · 13 November 2026 Australia/Brisbane.** Source [PR #110](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/110), commit [508d715](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/508d715488923b8945535c68d0a14776496114f6). This milestone directly used private **actual user-owned** Emerald, Team Rocket Edition 3.06 and Heart & Soul 2.0.6 ROMs for local *read-only* structural integration; **no original ROM or extracted proprietary bytes were committed to GitHub**.

## Real sources analyzed locally

| Source | Original whole ROM | Map-group slots | Populated fully validated maps | Zero-pointer slots |
| --- | ---: | ---: | ---: | ---: |
| Vanilla Pokémon Emerald (U) | 16 MiB | 518 | 518 | 0 |
| Unofficial Team Rocket Edition English 3.06 | 32 MiB | 1,778 | 1,778 | 0 |
| Pokémon Heart & Soul 2.0.6 | 32 MiB | 1,495 | 560 | 935 |
| **Total** | **80 MiB** | **3,791** | **2,856** | **935** |

All 80 MiB of original source bytes remain fully preserved (5,120 original 16 KiB pages and zero SHA mismatches). Separate earlier private read-only full-byte stress checked **60,000** random host windows under a **32 KiB cache**. R41's new private map/event-structure experiment validated every **nonzero** original map header including layout, grid, tileset descriptors, object/warp/coordinate/background event arrays, and connections. **This does not validate arbitrary custom scripts, Pokémon tables, music, or execution of all preserved data.**

HnS's existing map-group table has many **legitimate zero pointer entries**, which an earlier strict parser wrongly rejected as corrupted original layouts. R41 introduced an explicitly enabled `--allow-null-maps` option to `xgba_r34_binary_maps.py` that **preserves all original numeric group/map IDs** while recording 935 inactive slots. Every **nonzero malformed** entry still causes a failed import. Strict historical R34 behavior remains the default. Original data and all 935 holes are preserved rather than compacted.

## Original ID collisions (actual 3 ROMs)

- **2,088** distinct original numeric group/map IDs active in at least one source
- **201** same numeric IDs active in all three games
- **366** same numeric IDs active in exactly two games
- **1,521** numeric IDs active in one source only
- **566** shared numeric IDs whose active maps **disagree in width and/or height** across sources

The only safe runtime lookup is **(source ID, original group, original map)**. Resolving a map by group/map alone can return a different source/world, break original connections, or corrupt save state. R41 doesn't silently reassign IDs or overwrite source worlds. Collision statistics are private aggregate-only evidence, not a claim that all 2,856 maps are ready to traverse in one game.

## Actual source scripts, provenance and known translation costs

The user's original Team Rocket Edition 3.06 binary contains a structurally terminated source-map script at **group 0, map 13, ROM offset 0x216AB0** with original `setflag`, `setvar`, `clearflag`, and `end` operations. That does not make its original variable and flag IDs safe for vanilla Emerald saveblocks without per-world translation. R41 inspected this **privately**; it has not yet run through native patched Emerald/mGBA.

Public original Heart & Soul source at pinned commit [`167aa6d537b109bb229c231ddce4616974c4da71`](https://github.com/PokemonHnS-Development/pokehns-expansion/commit/167aa6d537b109bb229c231ddce4616974c4da71) contains `NewBarkTown_EventScript_TestMan2` (state variable + four flags), and Route29's `TuscanyYes` Silk Scarf item interaction. These genuine public scripts/map metadata were checked in R41 CI with explicit original New Bark Town ↔ Route29 connection references. **That is source inspection, not native cross-engine execution**.

A separate private, structurally checked **stock Android GBA mechanics preview** was created from the user's owned vanilla Emerald; it adds three test NPCs in Littleroot, exercises Emerald's original in-game items/messages/flags/Flash with explicitly remapped source-themed event operations. It is **not** a playable three-game combined ROM, not XGBA external storage, and **has not yet been emulator-boot-tested**. The privately generated preview and its original ROM bytes are intentionally excluded from the public repository. Manual emulator acceptance remains outstanding.

## Exact-head verified automation

- [R41 exact-head original source compatibility suite](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43244509421): **35/35** focused map/three-world tests, **74/74** historical host regressions, pinned original public HnS source checks all passed.
- [R34 default parser regression suite](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43244509805): passed.
- [Native source-built Emerald battle + FireRed Flash cold-restart regression](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43244509340): 3/3 jobs passed.
- [Public privacy scan](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43244509354): passed.
- This automation generates all synthetic/test-owned ROMs in CI. It does **not** load private Team Rocket or Heart & Soul ROMs in public CI; actual-ROM numbers above came from separate private read-only local analysis.

## Reproduce privately, no original files on GitHub

```sh
python3 tools/xgba_r41_three_rom_trial.py \
 --source emerald="/private/emerald.gba" \
 --source rocket="/private/team-rocket.gba" \
 --source heart_soul="/private/heart-and-soul.gba" \
 --windows 60000 --out "/private/r41-evidence.json"
```

Or import Heart & Soul original map segments while preserving all zero entries:

```sh
python3 tools/xgba_r34_binary_maps.py "/private/heart-and-soul.gba" \
 --allow-null-maps --source-id heart_soul --export "/private/heart_soul_original_maps"
```

## Required next game mechanics test

**Direct native source-aware gameplay integration**: in pinned patched mGBA, use actual imported Heart & Soul and Team Rocket source namespaced resources while original Emerald is running; route one chosen source event through an explicit compatibility adapter, validate the actual guest in-game effect with genuine LCD screenshots/GIF and actual Flash/save cold reboot; only then attempt safe map/warp transitions and battle/party/inventory interoperability. For arbitrary custom engine scripts, unsupported opcodes and mismatched save layouts must fail closed. The guest still has 256 KiB EWRAM, so 80 MiB stored on the host does not imply 80 MiB of guest RAM or a three-game merged release.
