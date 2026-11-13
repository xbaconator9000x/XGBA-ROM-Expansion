# R48–R49 — Complete original-ROM event intake for the real three-world Fly/NPC journey

**Status: source-data intake and emulator/guest ABI tested. Original-world Fly + NPC interaction NOT YET verified.**

The specific requested acceptance journey is:

1. In the actual source-built **Pokémon Emerald** overworld, talk to its real
   Littleroot NPC and use the real Fly animation/landing mechanic
2. Fly from Emerald to **Team Rocket Edition**'s actual map, with its original
   graphics, collision and NPC objects instantiated in the **original Emerald engine**
3. Approach a **real original Rocket NPC with physical D-pad+A**, execute the
   original script and display **original dialogue**, with original game state
4. Fly to **Heart & Soul** Goldenrod City, talk to a **real HnS NPC** using
   original event bytecode and native text UI
5. Fly back to Emerald and verify real map, NPC, party, source-qualified
   quest flags, inventory and **genuine Flash save/cold restart**
6. Capture **separate genuine native mGBA LCD GIFs** for each Fly departure,
   each arrival, each NPC encounter, the return and the end-to-end sequence.
   No offline mockup or rewritten dialogue may stand in for these GIFs.

These first NPCs are **functional probes, not limits of original data import**.

## Completed original-source intake — read-only owner ROMs, 13 Nov 2026

**This scan used all three complete user-owned original binary ROMs** and
verified their exact SHA-256 identities. It did NOT synthesize example NPCs.

| Original source | Populated maps | NPC/object records | Warp records | Coordinate triggers | Background interactions | Worst single-map event bytes (including source header) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Emerald | 518 | 2,941 | 1,313 | 375 | 720 | 1,936 |
| Rocket Edition 3.06 | 1,778 | 9,410 | 4,399 | 1,378 | 2,923 | 2,316 |
| Heart & Soul v2.0.6 | 560 | 4,738 | 1,434 | 587 | 1,054 | 2,640 |
| **All originals** | **2,856** | **17,089** | **7,146** | **2,340** | **4,697** | **2,640** |

Heart & Soul's 935 null map slots remain source-local holes. Each map's
complete four original event arrays are preserved **byte-for-byte**, including
original ROM script pointers, object graphics IDs and original event metadata.
No NPC/script/event was dropped from this catalog. All objects, maps, warps
and event records from the user originals were verified against their full
source ROM SHA-256 and packed into **3 immutable 16KiB map-index pages + 41
immutable 16KiB event pages = 44 source-owned XGBA resources**. Each original
map's complete events fit in a single page and are referenced by a sorted,
source-aware `(source,group,map)` key. Nothing requires 44 pages to be
resident in GBA EWRAM simultaneously.

**Private output:** `XGBA_R49_Private_Full_Three_ROM_Original_NPC_Warp_Event_Pack.zip`.
This contains proprietary game-derived bytes and is for the user, **not**
a public GitHub artifact. The public repository contains only
`tools/xgba_r49_all_original_map_events.py` and authored test fixtures.

**Actual native integration code:** `integration/common/xgba_r49_full_original_map_events.h`
binary-searches the 2,856 unique source-qualified map records by 16KiB page,
validates the original per-map CRC, original header offset, record counts and
bounds, and returns the actual original object/warp/coord/background bytes
without rewriting pointers. Guest fetches use SHA-validated provider resources
and a **caller-leased 16KiB scratch buffer**; a bad source never yields an
executable map event record. C11/ASan/freestanding tests are independent of
copyrighted originals.

**Necessary scalability improvement:** native patched-mGBA previously had a
hard 16-extra-resource cap. It now uses a dynamically grown host resource
registry, with strict checks and a bounded 65,535-entry limit; the Python
launcher shares the same bound. The native Emerald CI acceptance registers
32 additional authored source-event-shaped resources without increasing GBA
guest RAM. This is host registration capacity—not proof that foreign
original events ran inside the game.

## Authentic first script witnesses

`tools/xgba_r48_original_npc_assets.py` extracts three complete original
source verified 9-byte script+dialogue witnesses, preserving the original
script code and text exactly. The original game's NPC A-button scripting
function and Fly-in callback are now patched under opt-in, preserving
normal original Emerald behavior and Flash-saving.

**Gating and explicitly missing functionality:** no foreign source map has
yet completed original Emerald engine graphics, object-sprite instantiation,
collision, original warp, NPC script compatibility, Fly selection UI and
landing, or state persistence. The R48 proof counters cannot mark Fly as
successful merely because a source selector changed. The script bridge
refuses to substitute a foreign source NPC unless the actual map/NPC
is loaded with verified geometry/placement. The original source's 11,788
NPC script references and custom callbacks will require broader interpreter
translation; three simple witnesses are not the end goal.

## GIF integrity

- **Available:** true original Emerald LCD before/after native Flash save,
  prior real R45 source-owned three-map graphics in the separate map viewer
- **Not available / not claimed:** actual Emerald original-engine Fly→Rocket
  real NPC, Fly→HnS real NPC, Fly→Emerald and full-run GIF

Any GIF showing those missing actions without the underlying real native
guest proof would be a simulation, not an engineering acceptance artifact.
