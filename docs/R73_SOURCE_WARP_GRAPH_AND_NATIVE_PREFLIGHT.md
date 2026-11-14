# R73 — Original same-source warp routing, not a completed Fly

Owner-private R64 data, 377 SHA-verified resources: 2,856 original maps, 7,146 original warp records. Conservative source-qualified result: **6,952** ordinary resolved, **91** dynamic (127), **69** source coordinate outside declared grid, **25** destination warp index outside count, **5** destination coordinate outside grid and **4** destination map missing. Exceptional records are preserved and quarantined; no claim that the original ROM data is corrupt.

By world: Emerald 1,261/1,313 ordinary; Rocket 4,280/4,399; Heart & Soul 1,411/1,434. Rocket 0:9 warps point to Rocket group 35 destinations rather than Emerald's map group. A numeric map/group collision is not a valid world transition.

R73 adds a native C source-qualified route validator plus real Emerald R50/R51 read-only preflight that uses original R49 source warp bytes and authentic target R51/R49 pages. No new 16KiB EWRAM allocation, no rewritten originals, no foreign flags or unqualified map ID casts. Native Emerald events deliberately remain warpCount=0 because arbitrary target original graphics, scripts, and saves are not installed. R73 is route **preflight only**, not emulator-executed door travel. Heart & Soul source-art gap remains 17 resources; real three-ROM gameplay acceptance still blocked. Keep PR draft.
