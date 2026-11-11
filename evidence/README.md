# XGBA — permanent verified evidence gallery

Native emulator screenshot/GIF files here are unmodified bytes from passing exact-head CI.
No AI mockups or host-made replacement scenes. Large emulator-console JSON logs
are omitted from compact verification summaries, with their source hashes preserved.
No executable ROMs, sidecars, save files or raw proprietary game assets are archived.
Screenshots contain game imagery belonging to its rights holders and are shown
only as limited, noncommercial engineering documentation.

## R14 — external tilesets, actual house door and connected Route 1

| Pallet Town | Player's house | House exit | Route 1 |
| --- | --- | --- | --- |
| [![Outdoor](verified/r14/01-pallet-external-tiles.png)](verified/r14/01-pallet-external-tiles.png) | [![House](verified/r14/02-house-door-external.png)](verified/r14/02-house-door-external.png) | [![Return](verified/r14/03-pallet-door-return.png)](verified/r14/03-pallet-door-return.png) | [![Connected Route 1](verified/r14/04-route1-connected-external.png)](verified/r14/04-route1-connected-external.png) |

[Original R14 4/4 native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42977112057) · 
[Provenance](verified/r14/provenance.json) · [Proof summary](verified/r14/proof.json)

## R13 — the original house layout beyond 32 MiB

| Externally loaded house | Returned to Pallet | Re-entered house | Disabled-mode control |
| --- | --- | --- | --- |
| [![House](verified/r13/enabled/02-house-external.png)](verified/r13/enabled/02-house-external.png) | [![Pallet](verified/r13/enabled/03-pallet-return.png)](verified/r13/enabled/03-pallet-return.png) | [![Reload](verified/r13/enabled/04-house-reloaded.png)](verified/r13/enabled/04-house-reloaded.png) | [![Disabled](verified/r13/disabled/02-entry-refused.png)](verified/r13/disabled/02-entry-refused.png) |

[Original R13 4/4 native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42966044589) · [Provenance](verified/r13/provenance.json)

## R12 — real save-state restoration and external resource reacquisition

| Before SELECT | After SELECT | Native restore | Reacquisition |
| --- | --- | --- | --- |
| [![Initial](verified/r12/enabled/01-initial.png)](verified/r12/enabled/01-initial.png) | [![Swapped](verified/r12/enabled/02-after-select.png)](verified/r12/enabled/02-after-select.png) | [![Restored](verified/r12/enabled/03-restored.png)](verified/r12/enabled/03-restored.png) | [![Reacquired](verified/r12/enabled/04-replayed.png)](verified/r12/enabled/04-replayed.png) |

[Original R12 4/4 native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42964008063) · [Provenance](verified/r12/provenance.json)

## R11 — measured native FireRed CPU-frame throughput (not GUI FPS)

[Complete measured benchmark summary](verified/r11/r11-summary.json) · [Frame timings CSV](verified/r11/r11-frame-timings.csv) · 
[Original native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42959825105)

## R10 — live native FireRed Pallet Town sprite swap

![Original native Pallet Town GIF](verified/r10/pallet-town-live-select-swap.gif)

[Original R10 CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42955838562) · [Comparison](verified/r10/pallet-town-real-engine-comparison.png)

## R9 — same ROM, two different external graphics packs

| Crystal | Magma | Disabled fallback |
| --- | --- | --- |
| [![Crystal](verified/r9/crystal-real-mgba.gif)](verified/r9/crystal-real-mgba.gif) | [![Magma](verified/r9/magma-real-mgba.gif)](verified/r9/magma-real-mgba.gif) | [![Fallback](verified/r9/fallback-real-mgba.gif)](verified/r9/fallback-real-mgba.gif) |

[Original R9 native CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/42950960274) · [Three-run comparison](verified/r9/r9-three-runs-comparison.png)

## Permanent integrity and attribution

For every milestone, its provenance.json links to the passing source workflow
and the exact executable commit, and records the original artifact SHA-256
and per-file hashes. Original screenshots and GIFs are byte-for-byte preserved.
Compact proof summaries are clearly marked by unaltered=false and retain
the original document SHA-256. Repository history preserves these selected
documentation assets even after GitHub Actions download links expire.
