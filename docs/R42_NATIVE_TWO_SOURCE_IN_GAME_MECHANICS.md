# R42 — Original Emerald native gameplay with two external events and genuine Flash

**VERIFIED and MERGED · 13 November 2026.** Implementation [PR #112](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/112), commit [c61bcb0](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/c61bcb0f9c3332af9a67769c0cc8d4e8bc0501aa).

## Genuine native LCD and CI

- [R42 original Emerald game CI #43248913066](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43248913066): **6/6 actual native gameplay tests** and **4/4 event-bytecode tests** passed.
- [Five genuine 240x160 LCD frames and provenance JSON](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43248913066/artifacts/13958802571) show the source-built original Emerald overworld, Rocket-labelled dialogue, Johto-labelled dialogue, the real Flash save message, and the cold-restarted original game.
- [Unchanged R40 native script/Flash CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43248913118), [native FireRed Flash + Emerald four-battle EWRAM regressions](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43248912748), and [public privacy audit](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43248912493): all passed. Original ROM binaries, user saves and extracted source ROM assets are not published.

## Actual original Emerald mechanics

The test rebuilds pinned pret/pokeemerald in patched native mGBA, running actual Littleroot with verified external map/tileset resources. It separately reads **two SHA-256 checked, source-namespaced 96-byte script+text assets from beyond 32 MiB**, relocates their verified text pointers into bounded actual guest EWRAM, and executes with **Emerald's original ASYNCHRONOUS ScriptContext_SetupScript / gScriptCmdTable**. This invokes the *real game's* dialogue UI, original item-pickup implementation, native event flags/variables and Flash save code.

- Emulated **R button**: Rocket-labelled event changes original event variable **0x40FD to 0x524B**, sets native flag **0x08F1**, grants a genuine Emerald **Nugget**, and displays the exact original game-rendered message **ROCKET CACHE FOUND!**. Original A-button input closes the message.
- Emulated **L button**: Heart & Soul/Johto-labelled event changes event variable **0x40FC to 0x484E**, sets native flag **0x08F2**, grants a genuine **Silk Scarf**, and displays **JOHTO SIGNAL ONLINE!** in Emerald's original UI.
- Both native Bag items, two flags and two variables are independently verified in **actual game memory**. Already-completed flags prevent repeated granting in the test adapter.
- Emulated **SELECT** invokes original Emerald TrySavingData and Flash sectors. A **new native mGBA process** reloads the actual saved Flash via LoadGameSave / CB2_ContinueSavedGame and proves **both original Bag items, flags and variables survived** without replaying or re-fetching either event script. Five genuine LCD images and non-ROM proof JSON are retained.

The original GBA **256 KiB EWRAM physical limit remains unchanged**: two external scripts occupy only 96 bytes each in working RAM. No 80 MiB GBA RAM is claimed.

## Strict scope: authored adapters, not copied original scripts

**These two playable-looking event scripts are test-authored Emerald compatibility translations of source concepts from Team Rocket Edition and public Heart & Soul. They are NOT unmodified original Team Rocket Edition map scripts or Heart & Soul custom game-engine scripts, nor is there a playable combined three-game title.** No actual cross-region warp, custom engine callback translation, shared Pokémon party, or multi-engine save interchange is yet proven. The separate R41 private three-original-ROM data test established **80 MiB read-only**, 2,856 structurally valid original maps, **935** Heart & Soul zero-pointer holes, and **566** conflicting original numeric map IDs. The next phase must use original source triple keys (source, group, map) and attempt real data-derived warp/event/battle functionality instead of treating same-numbered maps as interchangeable.

## Hands-on Android distinction

The separate **private** 16 MiB modified Emerald mechanics preview has three new Littleroot NPCs with source-labelled reward/event mechanics. It is a **stock emulator** GBA test fixture, **not** the native R42 XGBA sidecar build and **not yet boot-verified on an Android emulator**. The preview ROM and IPS are not present in this public repository. A user should back up existing saves, launch a new save file, interact with the three NPCs, inspect the Bag for Potion/Nugget/Silk Scarf, save and reload, and report whether each one-time reward persists. The R42 native game is validated under patched headless mGBA on GitHub Actions; it is not distributed as an Android XGBA emulator APK.
