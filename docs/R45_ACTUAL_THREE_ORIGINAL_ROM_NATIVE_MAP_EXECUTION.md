# R45 — Actual user-supplied Emerald, Rocket and Heart & Soul map pixels IN THE NATIVE EMULATOR

**Executed 13 November 2026, private original user ROMs.** Implementation [merged PR #116](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/116) at commit [33b1000c](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/33b1000c7bb7a117a87d71e32dfde68250660ce0).

## Genuine, new runtime achievement

An actual pinned patched mGBA **executed a freestanding ARM7 GBA map-viewer program**. Its game CPU fetched **13 original Pokémon ROM-derived resources** from beyond 32 MiB through the XGBA guest MMIO system, then responded to native emulated GBA controller inputs **R → R → Right → A → L**. These were NOT text-only "Emerald / Rocket / Johto" labels used by R43. Actual pixels in the native mGBA's GBA Mode 3 VRAM were copied to six authentic 240×160 frame captures.

| Original private ROM used for assets | Actual map group:number | Map width×height | Distinct original metatiles | GBA resource pages |
|---|---|---|---|---|
| Pokémon Emerald (U), 16 MiB | 0:9, Littleroot Town | 20×20 | 63 | 3 |
| Team Rocket Edition English 3.06, 32 MiB | 0:9, source's own Littleroot | 24×25 | 75 | 4 |
| Heart & Soul 2.0.6, 32 MiB | 0:0, New Bark Town | 30×39 | 142 | 6 |

**Private integrity evidence:** Each of the above 13 external binary pages was re-derived from the user's actual original ROM bytes independently of the package ZIP and SHA-256 compared with the final sidecar. The whole three source files' local hashes also matched expected private identities. The contents of these user-owned ROM files, game-derived graphic assets, emulator frames and save files are **not committed** to public GitHub.

**Runtime verified:** 17 actual source-namespaced SHA-checked external fetches (3 initial Emerald + 4 Rocket + 6 Heart & Soul + 4 reacquired Rocket); **0 source lookup failures and 0 SHA failures**. The guest's source-specific status and original geometry were independently checked in emulated GBA memory at every transition. The GBA Right D-pad advanced the real map viewport exactly **16 pixels**. A toggled an emulated attributes/collision overlay on Heart & Soul. L reacquired Rocket assets. The initial original ROM viewer **failed** because its 3 KiB homebrew cartridge was not padded to a conventional ROM size; padding to 4 MiB resolved GBA out-of-bounds program data reads. The patched Linux native mGBA image API did not expose its frame pointers for Mode 3, so R45 captured the **real guest Mode-3 BG2 VRAM** instead, verifying actual GBA display control and preserving source pixels without a host renderer.

### Exact-head public CI versus private runtime

- [Exact-head R45 native patched mGBA compiler #43340267407](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43340267407): **passed**. Builds a real native mGBA executable with assertions for all three original source geometries and input transitions. The public CI **never includes or runs the private original ROM map bytes**. Its verified patched native emulator binary was downloaded and exercised with private user-generated assets outside public CI; this succeeded with 17/17 source reads.
- [Existing consolidated native FireRed/Emerald source and memory regression #43340267799](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43340267799): **passed**.
- [Public source/ROM privacy scan #43340267754](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43340267754): **passed**.

The six private actual GBA VRAM frames and a GIF are in the original user's conversation test kit; **not** in public GitHub Actions artifacts, to avoid sharing extracted copyrighted graphics. The private bundle for the Android R43 tester includes a new properly padded homebrew executable and 13 sidecar pages at offsets above 32 MiB, and has a correct matching source hash. **On-device Android boot, controls and performance still await user acceptance; only native Linux mGBA was executed here**.

## Exactly what is NOT proven

**The freestanding ARM7 map-viewer is not the unmodified original Pokémon Emerald overworld engine.** Original Rocket and Heart & Soul map scripts, NPCs, dynamic sprites, collision decisions, battle triggers, triggers/warps, shared inventory, save-block layout and custom engine callbacks were not executed in this R45 test; there is **no playable three-game merge**. The A-button overlay only visualises source map attribute flags; it does not implement gameplay collision. The Rocket map has visible black gaps and palette/layout reconstruction defects. The final Rocket frame stays red due to the persistent A-button overlay. These issues are recorded, not concealed as successful graphical fidelity.

For real three-engine gameplay integration, build source namespace translation keyed by **(source, original map group, original map number)**, adapt original map geometry and primary+secondary tilesets into the original Emerald field camera/renderer instead of Mode 3, preserve original events/warps/scripts with fail-closed custom opcode translation, and stress shared original game EWRAM/Flash lifetimes. R41 proved there are **566 collisions in active original numeric IDs with different geometry**, so a shared numeric-only map registry is unsafe. R40/R42 already demonstrate genuine original Emerald interpreter and Flash for *authored* external event scripts, while R17–R31 prove original Emerald camera/map travel using *Emerald* resource packs. R45 is the required source-authentic map-data/runtime bridge; linking it to original engine mechanics remains future implementation, not current test proof.
