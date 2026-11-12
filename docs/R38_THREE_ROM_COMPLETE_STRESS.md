# R38 — Three complete original-ROM sources: large read-only import stress

**VERIFIED / MERGED · 12 November 2026.** [PR #104](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/104) merged; [R38 all-source stress CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43212716551) passed **13/13 focused tests and 60/60 prior regressions**, including 96 MiB across three synthetic original-source ROMs, 6,144 pages and 90,000 source-bound random windows. [Exact-head consolidated native FireRed/Emerald regressions](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43212716540) and [privacy audit](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43212716538) passed. The private real Team Rocket ROM was not uploaded or executed in this public test. This is intended as the first
massive three-ROM import/stress gate, not another small synthetic script test.
It is a *host storage/provenance* milestone; source-built Emerald gameplay
and cross-ROM script execution are NOT claimed here.

## Why this milestone

The XGBA roadmap calls for bringing entire independently authored game
resources into one very large addressable storage pool, not cherry-picking
maps or Pokémon. The user's concrete planned project is Pokémon Emerald,
Unofficial Team Rocket Edition English 3.06, and a third Emerald-family
ROM hack, keeping each game's **original** map IDs, scripts, asset bytes,
inventory/save semantics, and all otherwise unidentified data.

R36 already preserves every binary byte of a supported source ROM.
R37 discovers script CFG and provisional dependency IDs without executing them.
R38 composes **multiple independently verified R36 binary page stores** and
tests source-local namespacing, provenance, bounded reads, LRU cache
evictions, adversarial bounds, duplicate IDs, atomic failure, every page,
full-original-ROM digests and 90,000 deterministic randomly positioned reads.

## Test scale / verification boundary

Public reproducible CI creates **three different synthetic 32 MiB Emerald-
structure ROMs**, 96 MiB total and **6,144 distinct 16 KiB pages**, without
shipping copyrighted game assets. The fixed synthetic map group/map numbers
and same script-entry original ROM offsets deliberately collide across
sources: `(emerald, group, number)`, `(rocket, group, number)`, and
`(third, group, number)` must remain distinct.

A full all-page SHA audit and 90,000 source-scoped random guest-window
reads (up to 16 KiB each) must agree byte-for-byte with original synthetic
input. The host only keeps two 16 KiB pages staged at once during the
6,144-page cache churn test; **the ROMs are stored on disk, not simultaneously
in GBA EWRAM**. Invalid namespace, invalid pointer, corrupted index, bad
bounds, duplicate source IDs, and failed atomic mount are negative gates.

Run:

    PYTHONPATH=tools:tests python3 -m unittest \
      test_xgba_r38_multi_rom_pool.ThreeROMStress -v

The private actual Team Rocket ROM remains **outside GitHub**. A passing
synthetic R38 proves full-sized binary-store interoperability; it does
**not** by itself prove a native mGBA gameplay session loading the user's
actual Team Rocket ROM alongside Emerald and a third binary hack. The R36
private export can be supplied as one of the source indexes locally.
No whole source ROM or user save is uploaded to CI.

## Next work after this test

1. Build a bounded, explicit script intermediate representation and
   source-specific compatibility gates for R37 supported opcodes.
2. Add source-scoped event flags, vars, trainer/items/save adapter contracts;
   refuse cross-world transitions until IDs and semantics are mapped.
3. Repeat a three-source stress test with **the actual three legal private
   sources**, and then integrate synthetic cross-world runtime execution
   with native Emerald/mGBA evidence. Treat inventories, quests, scripts,
   graphics and Pokémon mechanics as separate semantic compatibility
   problems; original byte retention alone is not functional compatibility.

No claim of one-click patched ROM interoperability, unlimited physical
memory, unmodified emulator compatibility, cross-world Fly or common saves
may be based on this host-side milestone.
