# R72 owner-private BIG TEST — attempted 14 November 2026 (fail-first)

## Verdict: BLOCKED before live three-world mGBA gameplay

**This is not a passed Emerald → Rocket → Heart & Soul → Emerald Fly test.** The actual original Emerald native emulator playthrough, original NPC text rendering, full foreign-world route, encounter state and Flash cold-restart acceptance were not executed.

A fresh in-session owner-private test was run against the **original R64 377-resource three-world provider** and the accessible genuine original Emerald and Rocket ROMs. All four saved Heart & Soul v2.0.6 GBA entries were located in the user's private Library; every attempt to obtain their raw bytes was explicitly denied by the file provider. Sprite-PNG archives cannot substitute for the SHA-pinned complete ROM.

### Real private resource test results (source-safe statistics)

| Check | Result |
|---|---|
| R64 host manifest resources with checked SHA-256 | **377/377 valid**, no duplicate IDs or ranges |
| R49/R51/R52 source map identities and graph/index CRC integrity | **2,856** original maps (Emerald 518, Rocket 1,778, HnS 560) |
| Original map NPC records | **17,089** checked within source event records |
| Original warp event records retained in immutable private store | **7,146** |
| Exact original ROM-to-private-grid byte matches | **518/518 Emerald**, **1,778/1,778 Rocket** |
| R48 original NPC script/text packets and CRC | **3/3** source-qualified witnesses |
| Mutation refusal | **1,000** altered host resources detected by SHA + **768** modified NPC-packet bytes detected by CRC |
| Preflight resource cycles (500 × 4 route vertices, **not emulator travel**) | **2,000** tested, 1,500 resource-closed, **500 blocked on HnS** |

**Landing prerequisite inventory**:

- Emerald 0:9: original native game ROM source art already exists; R63 native return must not require separate R53/R56 source0 art. Original dialogue resource is included.
- Rocket 0:9: original viewport sprite IDs `6,9,17,64` and both source-original tileset resources are present in R64: **zero missing source resources**. Resource closure is **not a native Fly arrival**.
- Heart & Soul 0:4: original viewport sprite IDs `406,489,16400` lack source-qualified R56 art (15 resources); original source R53 tileset meta for descriptors `0x00f885e4` and `0x00f8823c` is also absent (2 resources): **17 missing source resources**. Its source ROM was not readable to recover them.

All public source/statistical evidence excludes ROM art, user-private metadata manifests, game text, complete game images and save files. This private preflight was executed locally against the user's access-authorized file copies; it is **not** a GitHub Actions gameplay pass. The test script and JSON report were provided separately in the active user session, not committed as private assets.

### Independent live-gameplay gaps exposed by current original-Emerald code

`integration/emerald/xgba_r50_original_engine_events.inc` currently sets `events.warpCount=0`, `header.mapScripts=NULL` and `header.connections=NULL` for foreign-world maps. These require source-aware handlers before claims of intact original routes, quests, event scripts or encounters. R48 currently handles exactly one R48 NPC dialogue witness per world, not the full source-specific script interpreter. A complete original cross-world cold-resume save contract is also unproven.

### Required genuine acceptance, in order

1. Make the original Heart & Soul full ROM raw-byte accessible in the execution environment; authenticate exact SHA `cdfb9e1f83f72c05cb47af40fdf5635567b1973bcb759e070ad0971f67a49191`. **Do not put original copyrighted ROMs or private packs into public GitHub.**
2. Privately compile/bind HnS R53 tilesets and R56 original NPC 406/489/16400 assets, rerun R68/R72 host closure until **zero missing**.
3. Run the **real original Emerald patched engine** with native mGBA, user-private three-world provider, mGBA-host resource I/O and GBA EWRAM MMIO. Capture actual LCD PNG/GIF/host logs; any blank frames or emulated stand-in content must be marked failed.
4. Perform player input and real transitions: Emerald witness dialogue → Rocket Fly → Rocket actual source NPC interaction/dialogue → Heart & Soul Fly → Johto actual source NPC interaction/dialogue → Emerald native return; verify source ID, palettes, OAM/animation, map collision, warp/spawn, scripts, flags.
5. Validate battle/encounter transitions, save, emulator shutdown/restart, Flash restoration and all three world namespaces. Verify no duplicate/bad-egg data corruption. This is the **only** full gameplay acceptance path.

**PR must remain DRAFT.** The 12 successful existing workflows and the R72 private host preflight do not satisfy this end-to-end acceptance contract.

Verified original GitHub branch at test initiation: `403b69c81435ae0edbdac1776e83e972224b9676`.
