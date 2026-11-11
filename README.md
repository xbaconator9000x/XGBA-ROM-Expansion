# XGBA — Expanding What a Game Boy Advance Game Can Access

**Executed expansion proof: R6–R18 verified · 11 November 2026**

> **A real, source-built Pokémon FireRed executable running in the native mGBA core successfully used graphics bytes stored _beyond the conventional 32 MiB GBA ROM window_.** The game received a validated external resource through an opt-in host bridge, used FireRed's own sprite-sheet loading routine, and copied the expected bytes into emulated GBA object VRAM.
>
> **R6 integration milestone: 32/32 tests passed**, including the positive executable-game test and five executed fallback/failure cases. [Passing push CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940797581) · [Passing pull-request CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940805793) · [Experimental implementation, PR #40](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/40).

**The milestones are real; the expansion platform is not yet a finished product.** R6 used a temporary test host; R7–R15 progressed to game-initiated requests in a patched native mGBA core, actual LCD screenshots, live FireRed graphics swaps, native CPU-frame benchmarking, emulator save-state rollback, external map layouts and secondary tilesets, physical door/route navigation, and original FireRed Flash saving followed by a completely new emulator process continuing from the save; R16 demonstrates the **same external-resource interface in original source-built Pokémon Emerald**, including real EWRAM and LCD frames; R17 extends that proof to **Emerald's original Littleroot Town map grid, border and complete secondary tileset sourced externally and verified during actual D-pad movement**; R18 establishes **Emerald's original Flash save followed by an independent cold emulator restart, native save continuation and external map reacquisition**. These results do **not** establish a stock-emulator release, Android or GUI frame-rate performance, unrestricted CPU-addressable ROM, or original GBA hardware compatibility.

## Verified evidence — screenshots, animations and executable results

**[Browse the permanent evidence gallery: original FireRed screenshots, GIFs and SHA-256 manifests](evidence/README.md)**

**[Browse the permanent evidence gallery: original FireRed and Emerald LCD screenshots, GIFs and SHA-256 manifests](evidence/README.md)**

**Start here:** these are evidence from the *actual source-built game running in native mGBA*, not AI mockups or manually assembled gameplay animations. Each result links to the executed GitHub Actions run and, where available, its downloadable evidence archive. Implementation PRs remain separate from this documentation; none of these results establishes stock-mGBA, original GBA hardware or Android compatibility.

| Milestone | What was independently demonstrated | Executed CI | Visual / machine-readable evidence |
| --- | --- | --- | --- |
| **[R18](#latest-verified-milestone--r18-original-emerald-flash-cold-continue-and-reloaded-external-map)** | Original decompiled Emerald Flash sector save, complete emulator shutdown, new mGBA process continuing in externally backed Littleroot, native map/secondary BG VRAM reacquisition and corrupt-pack refusal. **5/5 passed.** | [Exact-head native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42995836013) · [matching PR run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42995826637) | [Original Emerald LCD PNGs and proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42995836013/artifacts/13844226288) · [permanent R18 evidence](evidence/verified/r18/provenance.json) |
| **[R17](#r17-real-emerald-littleroot-map-and-secondary-tileset)** | Original decompiled Emerald's Littleroot map grid/border and full secondary tileset stripped from built ROM, fetched externally, independently checked in native EWRAM and BG VRAM, and physically walked via D-pad. **6/6 passed.** | [Exact-head native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42993487976) · [matching PR CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42993559059) | [Original LCD PNGs](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42993487976/artifacts/13842542465) · [Permanent R17 evidence](evidence/verified/r17/provenance.json) |
| **[R16](#r16-source-built-emerald-reuses-xgba-native-provider)** | **First cross-game XGBA runtime proof:** original decompiled Pokémon Emerald boots in patched mGBA, guest-requests a sidecar beyond 32 MiB, receives validated real EWRAM bytes, and continues its original main loop; disabled mode reads zero bytes. **5/5 passed.** | [Exact-head native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990445836) · [matching PR run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990454718) | [Original Emerald LCD PNGs + proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990445836/artifacts/13840644779) · [Permanent gallery](evidence/README.md) |
| **[R15](#r15-genuine-flash-save-cold-restart-and-external-assets)** | Original FireRed Flash sector save, complete emulator shutdown, new mGBA process continuing in the external house, validated external graphics and corrupted-pack refusal. **4/4 native tests passed.** | [Exact-head CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42987149871) | [Four original LCD PNGs and proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42987149871/artifacts/13840560384) · [Permanent gallery](evidence/README.md) |
| **[R14](#r14-normal-door-navigation-and-external-secondary-tilesets)** | **Natural D-pad door entry/exit and Pallet Town → Route 1 connected travel; actual map layouts, secondary tilesets and BG VRAM from outside 32 MiB. 4/4 passed.** | [Exact-head native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42977112057) | **[Four original FireRed LCD PNGs + proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42977112057/artifacts/13835737289)** |
| **[R13](#r13-real-firered-map-geometry-outside-the-rom)** | Original house layout and border absent from ROM, real native warp/re-entry and disabled control. 4/4 passed. | [Native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966044589) | [Six original LCD PNGs + proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966044589/artifacts/13831536868) |
| **[R12](#r12-verified-native-firered-save-state-recovery)** | Real save-state rollback, graphics restoration and subsequent provider re-fetch. 4/4 passed. | [Native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964008063) | [Eight LCD PNGs + JSON proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964008063/artifacts/13830302814) |
| **[R11](#r11-real-firered-pallet-town-cpu-frame-benchmark)** | Actual FireRed CPU-frame benchmark under enabled and disabled native mGBA, not GIF timing. | [Exact-head CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959825105) | [Measured benchmark report](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959825105/artifacts/13828577188) |
| **R10** | Live external graphics swapped inside FireRed's original Pallet Town overworld. | [Native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955838562) | [Genuine native GIF/PNG captures](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955838562/artifacts/13827221467) |
| **[R9](#earlier-verified-milestone--r9-same-rom-different-external-graphics-packs)** | Same executable ROM, different externally stored graphics packs and native-rendered controllable scene. | [Native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42950960274) | [Three GIFs, original PNG frames and proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42950960274/artifacts/13824972843) |
| **R8** | Native mGBA LCD displays externally supplied pixels in a source-built FireRed program. | [Executed CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42947434354) | [See run and PNG proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42947434354) |
| **R6** | FireRed integration and host-controlled external resource delivery; 32/32 tests. | [Executed CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940797581) | [Implementation and reproducible tests, PR #40](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/40) |

**How to check a claim:** open its CI run, inspect the test step and the reported head commit, then open the evidence archive. R16 [native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990445836) ran at `b182dfa07a45673630c13d234b64a0e3d8e26a66`, with [unaltered Emerald screenshots](evidence/verified/r16/provenance.json) and the same unchanged resource protocol as FireRed. For R15, [native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42987149871) executed [PR #60's tested head](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/60) `f5ea62128463272089d66cd2ca13e807b14095ad`; four original **240×160 PNG screenshots** and the source-report hashes are also [archived permanently](evidence/verified/r15/provenance.json). The house screenshots before save and after cold boot are byte-for-byte identical. Runs document the *tested* revision, which can differ from later branch updates.

**Evidence publication rule for every future milestone:** promote a claim to *verified* only after exact-head execution succeeds; link **the passing run, evidence archive (PNG/GIF/log/JSON as appropriate), source PR/commit, and precise tested scope** in this table and the milestone section. Record actual test counts and explicitly distinguish native executable output from mockups, benchmarks and unexecuted builds. If an evidence type was not captured, mark it unavailable rather than substituting fabricated screenshots.

**Artifact retention:** GitHub Actions evidence ZIPs are time-limited. Selected original R9–R18 screenshots, GIFs, compact proofs and file-by-file SHA-256 manifests have been [committed to the repository](evidence/README.md); their Git history no longer depends on Actions artifact expiry. The original source execution and full logs remain linked for independent verification. No ROMs, raw resource packs or game saves are archived.

## Latest verified milestone — R18: original Emerald Flash, cold continue and reloaded external map

**11 November 2026 · Draft [PR #65](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/65) · exact tested head `261442f961c9121752f944b0c9fedbfb2999bd7a` · [native push CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42995836013) and [matching PR CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42995826637) both passed 5/5 focused tests.**

On the original source-built **Pokémon Emerald** engine, already using an XGBA-external Littleroot Town map and secondary tileset, a test-only SELECT control invoked the game's genuine `TrySavingData` Flash-sector save routine. The native emulator then **completely terminated**, retaining a real Flash save backed by mGBA's persistent save-file interface. A **second, independently launched mGBA process** used Emerald's trainer-ID-aware save-pointer relocation and actual `LoadGameSave(SAVE_NORMAL)` / `CB2_ContinueSavedGame` path to resume in Littleroot. Actual externally reloaded map-grid geometry and decompressed BG VRAM were independently checked.

A **third fresh native mGBA process** loaded the valid game save but rejected an intentionally corrupted external asset. Tests confirmed the original Flash save was unchanged. Three original **240×160 native Emerald LCD screenshots** were recorded before saving, after writing, and after cold continuation. The save file itself was never included in public artifacts.

| Exact native R18 acceptance | Executed result |
| --- | --- |
| Original Emerald Flash save and persistent 128 KiB payload | Passed |
| Separate-process original Emerald cold continue | Passed |
| External Littleroot map and full secondary BG tileset reacquired | Passed |
| Bad external pack rejected without modifying the valid Flash | Passed |
| Three authentic Emerald LCD frames and native emulator proof | Passed |

**Evidence:** [Exact-head native CI, 5/5](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42995836013) · [matching pull-request CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42995826637) · [original LCD and proof artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42995836013/artifacts/13844226288) · [permanent evidence gallery](evidence/README.md) · [R18 SHA-256 provenance](evidence/verified/r18/provenance.json).

**Scope:** this verifies Emerald's original save routines invoked via a **test-only SELECT shortcut**, not the graphical Start → Save menu. The fixture still bypasses Emerald's title/truck introduction and currently externalises one native map, not arbitrary routes, battles or species. Missing/corrupt critical packs fail closed without a polished game-facing recovery screen. The emulator is patched mGBA; stock emulators, physical hardware, Android and expanded guest VRAM/EWRAM are **not** claimed. The implementation remains draft, stacked on R17/R16/R15; only documentation/evidence is merged to main.

## R17: real Emerald Littleroot map and secondary tileset

**11 November 2026 · Draft [PR #64](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/64) · exact tested head `1dcb7427edec36110cc894097ea745802b516f72` · [push CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42993487976) and [PR CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42993559059) passed 6/6 functional native tests.**

In source-built **original Pokémon Emerald** (`pret/pokeemerald MODERN=1`), the original Littleroot Town 20×20 map, border and full Petalburg secondary tileset—including compressed tile graphics, palettes, metatiles and attributes—were **removed from the executable ROM**. A source-level adapter used the same XGBA guest/provider interface as FireRed to retrieve the verified pack from **beyond the ordinary 32 MiB ROM window**. The actual Emerald overworld loaded the map and graphics into native GBA working memory.

Native acceptance independently compared source asset bytes with the staged EWRAM pack and the actual game map grid, confirmed decompressed tile bytes in native BG VRAM, and verified changed player coordinates after **physical D-pad input**. Disabled mode refused the missing map and made no external provider reads. Two genuine **240×160 Emerald LCD screenshots** show the externally loaded town before and after movement.

| Native R17 acceptance | Result |
| --- | --- |
| Original decompiled Emerald with original map and secondary tileset stripped | Passed |
| SHA-checked external pack and actual EWRAM/map grid | Passed |
| Decompressed original secondary graphics in native BG VRAM | Passed |
| Native physical D-pad movement and real LCD frames | Passed |
| XGBA-disabled missing-pack refusal with zero host reads | Passed |
| Actual ELF/linker and finite GBA EWRAM budget checks | Passed |

**Evidence:** [R17 native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42993487976) · [matching PR run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42993559059) · [two original screenshot and proof files](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42993487976/artifacts/13842542465) · [permanent screenshot gallery](evidence/README.md) · [SHA-256 provenance](evidence/verified/r17/provenance.json).

**Scope and limits:** This is one real original Emerald map and tileset. The fixture bypassed the title/truck introduction for repeatable execution, but retained native overworld movement, collision, map layout and rendering. Arbitrary map transitions, general battle assets and **Emerald Flash save/cold continue remain separate tests**. The modified emulator is opt-in mGBA; stock emulator and physical GBA compatibility have not been claimed. No ROM, game save or proprietary raw tileset is distributed in the evidence archive.

## R16: source-built Emerald reuses XGBA native provider

**11 November 2026 · Draft [PR #62](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/62) · exact tested head `b182dfa07a45673630c13d234b64a0e3d8e26a66` · [push CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990445836) and [PR CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990454718) both passed 5/5 native tests.**

For the first time, XGBA has been executed in **a non-FireRed game** without implementing a separate emulator provider: the pinned **`pret/pokeemerald` decomp** (`731ad5bfd6e6f265508d0efcca0ba42f9dcf5881`) was built with `MODERN=1`. A source-level hook in Emerald's original `src/main.c`, inserted after its real heap initialization, called the same versioned XGBA guest MMIO interface. The original native mGBA provider fetched a 64-byte resource at a validated **post-32 MiB external offset**, wrote it into real 256 KiB GBA EWRAM, and the test read those same bytes back through the guest memory bus. The game's original main loop continued for **900 additional emulated frames**; authentic native LCD output was captured.

The **same exact built Emerald ROM** was also tested with the XGBA extension disabled: the unchanged 64-byte sentinel remained in EWRAM and the host provider made **zero** external reads. Source identity, compiled ELF EWRAM address, resource hash and 32 MiB ROM ceiling were independently checked. Only original screenshots and non-ROM proof metadata are published.

| Native acceptance case | Executed result |
| --- | --- |
| Exact source-built original Emerald decomp and physical EWRAM | Passed; original ARM ELF and actual MMIO transfer |
| Enabled external provider and 64-byte sidecar | Passed; actual guest-initiated request and independent memory comparison |
| Same ROM with extension disabled | Passed; zero external reads and unchanged destination |
| Emerald original main-loop and LCD | Passed; 900 additional frames, two genuine 240×160 LCD PNGs |
| FireRed/Emerald engine ABI differences | 11 pinned source anchors validated, including Emerald's trainer-ID-derived save-pointer relocation |

**Evidence:** [Passing R16 source-built Emerald CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990445836) · [independent PR CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990454718) · [two original LCD PNGs and proof report](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42990445836/artifacts/13840644779) · [permanent native evidence gallery](evidence/README.md) · [R16 exact-head source PR #62](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/62).

**Scope:** This is a **cross-game guest/provider integration proof**, not a fully external Emerald tileset/map, Pokémon/battle, save/reboot or normal game-editor export. Emerald requires its own source-level map, allocator/linker and save-block adapter, especially `SetSaveBlocksPointers(u16)` rather than FireRed's zero-argument version. Neither game requires expanding native RAM/VRAM to communicate with the shared external resource protocol. The emulator remains patched mGBA; this is not a stock-emulator, mobile or hardware release.

## R15: genuine Flash save, cold restart and external assets

**11 November 2026 · Draft [PR #60](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/60) · tested head `f5ea62128463272089d66cd2ca13e807b14095ad` · 4/4 native functional tests passed in [primary CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42987149871) and [matching exact-head CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42987157612).**

In the pinned, source-built **actual FireRed game**, the player entered the house through normal D-pad movement. A test-only SELECT callback then invoked FireRed's **original `TrySavingData(SAVE_NORMAL)` Flash sector and checksum routines**—not a host-produced save-state. The native mGBA process shut down, leaving a real 128 KiB Flash image (plus 16 bytes of mGBA file metadata). A **new mGBA process** called original `LoadGameSave(SAVE_NORMAL)` and `CB2_ContinueSavedGame`, resumed inside the saved house, reacquired the externally stored house grid and secondary tileset, and navigated outside, acquiring the outdoor pack. Native map geometry, staged pack SHA and decompressed background VRAM were checked.

The saved house's pre-save and cold-boot screenshots are **byte-for-byte identical original 240×160 LCD PNGs**. A third, independent emulator launch checked that a deliberately corrupted external pack fails SHA validation and is refused while leaving the valid Flash save unchanged.

| Native acceptance case | Executed result |
| --- | --- |
| Original FireRed Flash save and persistent file across process shutdown | Passed; 131,072 Flash bytes plus 16-byte mGBA metadata |
| Separate-process native FireRed continue from saved house | Passed; external house graphics and grid reacquired, then Pallet Town |
| Invalid external pack / saved game integrity | Passed; corrupt pack refused before use; save unchanged |
| Native evidence | Four genuine LCD PNGs; saved house restored byte-for-byte; 4/4 unit checks passed |

**Evidence:** [Passing R15 native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42987149871) · [matching CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42987157612) · [four original native PNGs and proof JSON](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42987149871/artifacts/13840560384) · [permanent repository gallery](evidence/README.md) · [exact tested source PR](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/60). No ROM, raw proprietary tilesets or save file is distributed.

**Engineering scope and remaining work:** R15 also introduced a common source-validated, phase-aware working-memory planner (26 focused tests) for original ROM and 64-bit external assets using EWRAM, VRAM and palette budgets; it does **not** demonstrate expanded guest RAM/VRAM, arbitrary external multi-pack battle assets or non-FireRed support yet. The Flash save was invoked via a test-only SELECT shortcut, not the full graphical Start → Save menu. Missing/corrupt assets fail closed in the test fixture, but a polished user-facing error/recovery UI is not yet implemented. This remains a patched-native-mGBA proof, not an ordinary stock-emulator release.

## R14: normal door navigation and external secondary tilesets

**11 November 2026 · Draft [PR #56](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/56) · exact head `3a1988e99da9285e8d194e9b1bbf9b3d936b6d3e` · 4/4 focused native tests passed; all seven R7–R13 regressions passed.**

The actual pinned FireRed game uses physical GBA D-pad inputs to enter the player's house, leave it, and follow the native collision grid across the seamless Pallet Town–Route 1 connection. Both external maps (House 1F, 13×10; Route 1, 24×40), their borders and their complete indoor/outdoor secondary tilesets (compressed tile graphics, palettes, metatiles and attributes) are stripped from the compiled ROM and supplied through two resource packs at offsets above 32 MiB. Pallet Town and Route 1 share the outdoor secondary tileset.

| Native acceptance case | Executed result |
| --- | --- |
| Physical D-pad house entry, exit and seamless Route 1 connection | Passed |
| External map geometry and complete secondary tilesets | Exact staged pack SHA-256, native map grid/border and native decompressed BG VRAM verified |
| Working-memory lifecycle | One linker-bounded heap-tail arena, three external reads (outdoor → indoor → outdoor), same arena address throughout |
| Original resources absent from ROM | Compiled map and tileset ranges stripped; both packs beyond 32 MiB |
| Native rendering | Four genuine 240×160 LCD PNGs; enabled scene changes verified |

**Evidence:** [passing R14 exact-head PR CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42977112057) · [four native screenshots and proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42977112057/artifacts/13835737289). The job log records all four tests passing and `PASS_R14_ACTUAL_FIRERED_EXTERNAL_TILESETS`. No ROMs or raw proprietary resources are distributed.

**Engineering lesson:** The initial two-pack static allocation exceeded the physical 256 KiB EWRAM limit; even a single static arena overflowed. The final implementation reserves the tail of FireRed's existing heap and bounds every heap initialization, protecting the pack through native transitions and checking save-copy scratch bounds. The actual guest arena address is independently checked against the linker boundaries. Earlier failures and their corrections remain visible in PR #56 and its CI history. **Scope:** primary tilesets, NPC/event definitions, encounter tables and scripts remain ROM-resident; this is a bounded enabled-core proof using a post-Oak fixture, not stock-emulator compatibility, arbitrary-size maps or a released platform.

## R13: real FireRed map geometry outside the ROM

**11 November 2026 · Draft [PR #54](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/54) · exact head `f3ae6846e5971c0617674d5cef98be5331b91b2d` · 4/4 focused native tests passed on both push and PR CI.**

The actual **Player's House 1F** layout was removed from the compiled FireRed ROM: its original 13×10 metatile grid (260 bytes) and 2×2 border (8 bytes) were replaced by zero placeholders before compilation. The test verified that the original full 260-byte map sequence was absent from the ROM, which remained within 32 MiB. The original **268-byte layout payload** was stored at sidecar offset **33,562,624 (32 MiB + 8 KiB)**.

The source-built FireRed game requests the external layout through XGBA, stages it in EWRAM and enters the house using the genuine FireRed `DoWarp` / `WarpIntoMap` / `CB2_LoadMap` path. Native map-grid and border contents are checked against the original bytes and SHA-256. The game then returns to ROM-resident Pallet Town, evicts the external layout and re-enters the house, requiring a fresh provider read.

| Native acceptance case | Executed result |
| --- | --- |
| External layout entry → Pallet Town → re-entry | 3 transitions, 2 host reads, native grid SHA verified |
| Extension disabled | 0 transitions, 0 host reads; external entry safely refused |
| Original map data | Full original metatile sequence absent from ROM; payload beyond 32 MiB |
| Native renderer | 4 enabled + 2 disabled original 240×160 LCD PNGs; enabled scene changes verified |

**Evidence:** [passing R13 push CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966044589) · [push screenshots and proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966044589/artifacts/13831536868) · [passing exact-head PR CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966059991) · [PR screenshots and proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966059991/artifacts/13830909294). All six R7–R12 regression workflows passed at the R13 head. The four R13 tests check disabled refusal, original map absence and external offset, real entry/return/re-entry, and native LCD frames. No ROM or raw map binaries are distributed.

**Scope:** R13 proves external **map geometry and border**, not a completely external map bundle. Native layout metadata, tilesets, events and scripts remain ROM-resident. SELECT triggers the native warp in the test fixture; walking through a physical door and arbitrary-size map support are not yet proven. This is an important functional advance: XGBA now supplies actual data used by the real map engine, not just an overlay sprite.

## R12: verified native FireRed save-state recovery

**R12 — verified native FireRed save-state recovery.** [Draft PR #53](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/53), exact head `864804eebcc90a90fb07a81ddc449440b2725827`. [Native CI, 4/4 passed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964008063) · [eight native LCD PNGs and JSON evidence](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964008063/artifacts/13830302814). Crystal → Magma → native mGBA save-state restore to Crystal → Magma again; exact OBJ VRAM SHA-256 checks and real provider read counts 1 → 2 → 2 → 3. Disabled control performed zero host reads. [Matching PR CI, 4/4 passed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964060978) · [PR evidence artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964060978/artifacts/13829574576). All R7–R11 regressions passed at the R12 head. This verifies same-ROM, same-core, same-mounted-pack emulator state rollback and fresh resource acquisition; it does not establish ordinary in-game SRAM saves, arbitrary pack-mismatch restoration or general save-state extension serialization.


**Current priority after R18:** extend the now-verified original FireRed Flash save/continue path to the actual user-facing save menu and graceful missing-pack recovery; generalize the native resource manager and versioned multi-pack format; extend verified Emerald external map and Flash save/continue to multiple map transitions, battle assets and a normal user-facing save menu; introduce further game-specific adapters; and validate graphical emulator/audio/VSync performance. Physical door navigation and Pallet Town → Route 1 connectivity remain verified from R14. Repeated endurance testing is deferred unless a specific regression warrants it.

## R11: real FireRed Pallet Town CPU-frame benchmark

**11 November 2026 · Draft [PR #52](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/52) · exact head `168d9137cb6b1576b53b6b0455d8c56a39bd943b` · 5/5 focused tests on each exact-head CI run.**

R10 ([draft PR #51](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/51), commit `2ede1b8470cbf71318e44873497a8b8d2ab51526`) moved the experiment into the **actual FireRed Pallet Town map/overworld engine**, with a SELECT-triggered live external graphics swap. [R10 push CI, 5/5 passed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955838562) · [native GIF/PNG evidence](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955838562/artifacts/13827221467) · [matching PR CI, 5/5 passed](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955844195). R11 measured the runtime cost using a **real pinned FireRed ROM and patched native mGBA CPU**, not GIF playback timing. The earlier R10 GIF held source frames for **165 ms each**, approximately **10×** a real **16.74 ms** GBA frame; its apparent sluggishness was an encoding/playback artifact, not evidence of a tenfold game slowdown.

R11 executed **six paired same-ROM trials** (three XGBA-enabled, three disabled), each with **120 warmup frames + 360 pre-swap frames + 3 SELECT frames + 360 post-swap frames**. Timing used `CLOCK_MONOTONIC` around `mCore.runFrame` and excluded PNG/GIF encoding. Results are **unthrottled native emulation throughput**, not real GUI, vsync, audio, Android or hardware frame rates.

| Measurement | PR CI runner | Separate push runner |
| --- | ---: | ---: |
| Disabled, before SELECT (median) | 1865.083 FPS | 1119.142 FPS |
| Enabled, before SELECT (median) | 1865.589 FPS | 1130.095 FPS |
| Disabled, after SELECT (median) | 1870.672 FPS | 1146.004 FPS |
| Enabled, after SELECT (median) | 1875.427 FPS | 1133.968 FPS |
| SELECT → second asset ready (median) | 0.635484 ms | 1.034608 ms |
| SELECT → second asset ready (emulated frames) | 1 | 1 |

**Interpretation:** Compare enabled/disabled **within** a runner; absolute throughput differs between shared CI hosts. The faster PR runner observed no measured frame exceeding **16.74 ms** during its trials. This does **not** prove frame-limited 59.7 FPS graphical playback or eliminate future streaming, cache, save-state or device-specific bottlenecks.

**Evidence:** [R11 exact-head PR CI, successful](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959825105) · [PR benchmark report artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959825105/artifacts/13828577188) · [R11 exact-head push CI, successful](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959790780) · [push runner report artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959790780/artifacts/13828024036). R7–R10 regression checks remained green at R11. GitHub Actions artifacts are retention-limited.

**Functional integration continuation:** see R12–R18 above. Repeated stress testing is deferred; all native implementation milestones remain experimental on draft branches, not released products.

## Earlier verified milestone — R9: same ROM, different external graphics packs

**11 November 2026 · Real compiled FireRed + native patched mGBA · 5/5 R9 tests passed**

**We have now visibly demonstrated resource-pack swapping while a controllable GBA scene runs.** The *same, byte-identical FireRed ROM* booted in the native modified mGBA core with two separate graphics resource packs held **past the 32 MiB cartridge ROM window**:

| Run | External resource | Observed screen behavior |
| --- | --- | --- |
| **Pack A: Crystal** | Cyan/blue native 64×64 4bpp GBA sprite, 2,048 bytes | Real game-loaded crystal emblem over tiled scene |
| **Pack B: Magma** | Red/orange/gold native GBA sprite, same ID/size/offset, different SHA-256 | Visibly different emblem without rebuilding the ROM |
| **Extension disabled** | No external reads | Controlled scene and original graphics fallback remain operational |

The source-built FireRed ARM/Thumb program sets up GBA BG0 tilemap and OAM, receives an external resource through the **game-initiated R7 mGBA MMIO interface**, and polls actual **GBA KEYINPUT** to move a player sprite. During each run the native mGBA software renderer captured **16 original 240×160 screenshots**; those captured images—not synthetic or AI-generated gameplay—were encoded into three GIF animations.

The executed test observed the player moving **(24, 92) → (38, 102)** in each run; **891 pixels** differed between the crystal and magma emblems in the central comparison region, and the disabled run performed **zero host resource lookups**. The game ROM's SHA-256 was **identical in all three runs**.

**See the actual executable evidence:** [passing R9 run and artifact](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42950960274) · [GIFs, original PNG frames, three-way comparison and proof.json](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42950960274/artifacts/13824972843) · [R9 implementation PR #49](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/49). The R9 PR CI also passed, and prior R7/R8 native regression CI remained green at the exact R9 commit.

**Important scope boundary:** R9 uses a **custom controllable tile-based proof scene inside a compiled FireRed executable**, *not* the canonical FireRed overworld map/event engine. It is not yet a standalone GUI emulator release, a drop-in arbitrary ROM patcher, or original-cartridge support. The R7–R9 implementations remain in **open draft PRs #47–#49**, preserving the previously validated baseline. The GitHub Actions GIF artifact is retention-limited; its underlying code and test procedure remain in the repository.

### The engineering progression

- **R6:** a source-built FireRed game consumed bytes beyond 32 MiB with a test host bridge.
- **R7:** FireRed issued its **own resource request** to the opt-in patched native mGBA core; exact OBJ VRAM bytes and disabled fallback verified.
- **R8:** a real compiled FireRed executable **displayed an externally loaded graphic on mGBA's actual 240×160 LCD output**. [R8 PNG proof](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42947434354).
- **R9:** two independently selected external 4bpp graphics packs visibly changed a **controllable game-side scene**, with unchanged ROM identity and recorded mGBA GIFs.
- **R10:** actual FireRed Pallet Town overworld engine performed a live SELECT-triggered external graphics swap.
- **R11:** six paired native mGBA trials measured unthrottled CPU-frame throughput and resource-ready latency, correcting misleading GIF playback pacing.
- **R12:** real native mGBA save-state rollback restored the earlier graphics and game state, then a fresh guest request re-acquired the second asset.
- **R13:** actual FireRed house map grid and border lived outside the ROM; native map transitions, eviction and re-entry loaded them from the sidecar.
- **R14:** real D-pad-driven house entry/exit and connected Route 1 navigation used full external secondary tileset packs, with source ROM assets removed and native GBA BG VRAM verified.
- **R15:** normal FireRed Flash-sector saving, complete emulator shutdown, clean continuation from the saved house and verified external resource reacquisition; mismatched external packs refused without changing the save.
- **R16:** original source-built Emerald sent real XGBA requests to the same native mGBA provider, received external bytes in EWRAM, preserved zero-read disabled mode and continued original game-loop/LCD rendering.
- **R17:** actual Emerald Littleroot map geometry, borders and secondary tileset were stripped from the linked ROM, externalized beyond 32 MiB, reconstructed in physical EWRAM/BG VRAM and physically traversed by D-pad.
- **R18:** original Emerald Flash saving, complete emulator process termination, cold continuation into externally loaded Littleroot Town and corrupted-pack refusal while preserving real Flash save data.

**Next work:** generalize the verified external map/tileset and original Flash-save fixture to the graphical in-game save UI, graceful pack-error recovery, Emerald's next external multi-map, battle assets and complete graphical save-menu adapters, more asset types and battle lifecycles; measure real graphical-emulator playback with audio/vsync; and package accessible ROM-hacking tooling. Larger resource-library tests remain valuable, but redundant endurance tests are deferred. Total external content can grow separately from the addressable cartridge window, but CPU/GBA memory limits still apply.

## Why this matters for GBA ROM hacking

Traditional GBA ROM hacking is constrained by the cartridge's CPU-visible ROM address space. Adding regions, sprites, music, dialogue, and other game data typically means fitting assets into that space, repointing them, or working around the cartridge's storage and banking conventions.

**XGBA explores a different architecture: keep the executable game inside the normal ROM window, but allow explicitly modified games and emulators to retrieve additional assets from separately stored, validated resource packages.**

If developed into reusable tooling, this could change the practical scope of emulator-targeted GBA projects:

- **More worlds and content:** additional regions, tilesets, artwork, dialogue, and potentially new scenarios without requiring every asset to reside in the cartridge ROM.
- **Larger Pokémon and character projects:** additional sprites, animations, forms, and associated content, subject to each game's engine and data-structure limits.
- **Modular distribution:** resource packs with stable identifiers, integrity checks, and source-ROM identity rather than a single ever-larger binary.
- **New editing workflows:** future integration with ROM-hacking editors and build pipelines could manage external resources directly.

These are **implications and development goals**, **not features already supported for arbitrary ROMs**. There is no claim that XGBA was the first project ever to explore emulator-assisted resources, that ordinary emulators can already run it, or that hardware limits have been eliminated.

### The key distinction: storage is not directly addressable memory

An ordinary GBA CPU cannot simply dereference an unlimited ROM pointer. The experimental mechanism separates **how much data the host can store** from **how much data the GBA can address or hold at once**.

~~~text
               Real FireRed ARM/Thumb execution
                    (ordinary GBA ROM)
                             |
                  Test-only opt-in handshake
                             |
           mGBA-linked native host resource provider
                             |
           Versioned manifest + identity + SHA-256
                             |
        External sidecar asset beyond ROM's 32 MiB
                             |
                 Bounded GBA EWRAM staging
                             |
            FireRed's native LoadSpriteSheet()
                             |
                    GBA object VRAM
                  (verified by test)
~~~

The host's resource collection could *eventually* be far larger than the ROM window because content can be loaded on demand. It is **not literally infinite**: host storage, indexing formats, data-transfer speed, game-engine changes, EWRAM/IWRAM/VRAM capacity, and runtime lifecycle constraints still matter. The demonstration **does not** directly map external bytes into the GBA CPU's ROM address space.

## What we actually proved — R6

On **11 November 2026**, the R6 executable integration test:

1. Built a **real ARM/Thumb FireRed ROM and ELF** from the pinned [pret/pokefirered](https://github.com/pret/pokefirered) source with a small, temporary opt-in test probe.
2. Ran that compiled ROM in the **actual native mGBA CPU core** built from pinned [mgba-emu/mgba](https://github.com/mgba-emu/mgba) sources. This was **not** a Python-only simulation of game execution.
3. Created an external sidecar containing a **64-byte test graphics resource at file offset 32 MiB + 8 KiB**, past the ordinary ROM window.
4. Verified the game's identity and resource integrity through the experimental host provider, then copied the validated bytes over the emulated GBA bus into bounded **EWRAM**.
5. Allowed FireRed's compiled code to call its real **sprite-sheet loading path**, then verified the exact expected data in **OBJ VRAM**.
6. Executed five additional test modes: **extension disabled**, **incorrect ROM identity**, **truncated resource**, **corrupted digest**, and **missing resource**. Each correctly used or preserved the original sprite rather than accepting invalid external data.

The full exact-commit test run reported **32 tests passed**, with the same commit passing both GitHub push and PR checks.

**Scope of the result:** the proof verifies an actual game's resource-load path and destination graphics memory. It does **not** establish a user-facing on-screen sprite presentation, live map streaming, audio streaming, general-purpose patching of existing ROM hacks, or that stock mGBA can use sidecars without modifications.

### The six delivered experimental packages

| Package | Delivered capability | What it establishes |
| --- | --- | --- |
| **R1** | Validated, bounded sidecar streaming | External resources can be addressed and read, including from sparse storage beyond 32 MiB. |
| **R2** | Deterministic resource packaging | Stable resource identity, integrity data, repeatable builds, and rollback on failure. |
| **R3** | Opt-in host staging bridge | Bounded staging and source-ROM identity checks without rewriting ordinary ROM pointers. |
| **R4** | Native FireRed static-graphics adapter | FireRed's real sprite-loader contract can consume a valid bounded EWRAM source, with original-asset fallback. |
| **R5** | Native C mGBA-linked resource provider | Versioned provider handshake, validated resource retrieval, and failure/opt-out paths using the pinned emulator library. |
| **R6** | Executed FireRed + mGBA integration | A running, compiled FireRed game actually receives and loads the post-32-MiB graphics resource; five negative cases run too. |

All six are recorded as **delivered experimental packages**. The delivery ledger and code are tracked in [PR #40](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/40) and the [autonomous product ledger](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/blob/xgba-autonomous-product-state/.xgba-autonomy/ledger.json). **PR #40 remains an unmerged draft**; this README documents the verified milestone without silently shipping its experimental implementation on the main branch.

## Reproduce the evidence

**Most direct:** inspect the [32/32 passing source-build and integration CI run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940797581), which checks out pinned FireRed and mGBA sources, installs a real ARM build toolchain, compiles FireRed and the mGBA-linked harness, and runs the positive and negative cases. The matching [pull-request run](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42940805793) is also green.

For local reproduction on a suitable Linux build host, use the **experimental branch**, not the current main branch:

~~~bash
git clone https://github.com/xbaconator9000x/XGBA-ROM-Expansion.git
cd XGBA-ROM-Expansion
git checkout phase1/xgba-optin-resource-prototype-20261110
mkdir -p upstream
git clone https://github.com/pret/pokefirered.git upstream/pokefirered
git -C upstream/pokefirered checkout --detach ce6406d8c2eaf46d543c8a2606de0c3cb1951982
git clone https://github.com/mgba-emu/mgba.git upstream/mgba
git -C upstream/mgba checkout --detach fd9dc5c2cbf234365068855851107e762fc6211b
# Install GCC, CMake, Make, binutils, arm-none-eabi-gcc,
# arm-none-eabi-nm, the ARM C runtime and graphics build dependencies.
python3 -m unittest discover -s tests -p 'test_xgba_resource_*.py' -v
~~~

For the focused experiment, run `python3 tools/xgba_resource_integration_smoke.py --json r6-proof.json` after preparing the same toolchain and pinned sources. The demonstration compiles its own ROM from source, instruments a temporary checkout, and records ROM/ELF/resource hashes and execution results. **Do not publish copyrighted game ROM bytes.**

**Upstream pins:** FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; mGBA `fd9dc5c2cbf234365068855851107e762fc6211b`. The passing product commit is [`b9632c5`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/b9632c5ae9c562bb764047657deb12d7b0ffe891).

## What comes next

The R6–R18 milestones answer increasingly practical feasibility questions for **emulator-assisted external assets**. The next task is to turn these executed, source-instrumented proofs into a reproducible, supportable workflow:

1. **Production integration:** harden the existing game-initiated native mGBA resource device and FireRed-side integration into an explicitly enabled, maintainable extension and reusable resource API.
2. **Engine support:** extend the verified sprite and map-grid integration to ordinary navigation, tilesets, palettes, other assets, and safe decompression, allocation, ownership, resource lifetimes, DMA, audio and save-state identity.
3. **Hacking tools and compatibility:** integrate resource IDs and packaging with editors/build systems; test fingerprinted game versions and modified ROMs instead of assuming universal compatibility.
4. **Release and regression:** provide runnable builds, clear setup instructions, measurable load times, fail-closed recovery and honest emulator/hardware support claims.

**Not yet proven:** a direct drop-in upgrade for existing `.gba` files, original-cartridge compatibility, ordinary stock-emulator support, arbitrarily large *simultaneously addressable* GBA memory, or a complete game expansion beyond 32 MiB.

## Earlier research and compatibility work

This breakthrough **builds on**, rather than erases, the repository's prior source-pinned hardware and ABI research:

- [Historical Phase 1 source-mapping status](docs/PHASE1_STATUS.md): `FAIL_INCOMPLETE`, including the 14,834-file inventory. Mapping and independent whole-file semantic approvals remain incomplete, but a full mapping pass is **not a prerequisite** for the demonstrated opt-in prototype.
- [34 native mGBA Matrix and cartridge regression checks](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40204719637): banking, ROM access, DMA, save and savestate behavior, including known unsafe behaviors. This is separate from the external-sidecar proof.
- [External resource/banking constraints](docs/PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md): GBA address-space realities and why existing 64 MiB Matrix banking is not the same as an open-ended sidecar resource protocol.

**XGBA is an experimental engineering project, not a finished ROM-hacking product.** But the distinction now matters: we have moved beyond a proposed design and demonstrated that a running GBA game can use validated external resources stored past its ordinary cartridge ROM window. The next challenge is to make that capability practical, reproducible, and available to the wider ROM-hacking community.
