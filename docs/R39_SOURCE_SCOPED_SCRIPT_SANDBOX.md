# R39 — Source-scoped event-script sandbox (NOT live ROM-hack execution)

**VERIFIED / MERGED · 12 November 2026.** [PR #106](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/106) merged as [`0423c98`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/0423c98b450778841c1b276401f2c1a570ab27b7). **27/27 focused host script tests, 60/60 previous R34–R37 parser regressions, the 96 MiB three-ROM source-mounted script test, pinned Emerald command-profile verification, native FireRed Flash cold restart, native Emerald four-battle arena eviction, and repository privacy scan all passed on the exact PR head.** [R39 CI](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43219151164) · [native regression](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43219151212) · [privacy audit](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43219151300). This layer directly follows verified R38's three complete 32 MiB independently mounted source ROMs. It addresses semantic isolation, not ROM storage capacity.

## Implemented scope

- Compile from a **real R36 script root** inside an R38 source-identity-verified backing page store, in small read windows, into an immutable, source-bound instruction representation. All reachable branches are checked before any event state can change. The compiler refuses unknown opcodes, invalid pointers, cross-source source-ID confusion, unsupported engine-native callbacks, warps, trainer-battle layouts and incomplete branches.
- A **host-only replay sandbox** implements a deliberately restricted subset of original Emerald commands: jumps, conditional jumps, call/return, 16-bit variables, comparisons, flags, trainer-defeated flags, and policy-gated item transactions. Condition IDs and word-width layouts are anchored to a fixed commit of original `pret/pokeemerald`. Unsupported commands **fail closed**, never silently convert to no-ops.
- Source-specific state stores keep original numeric flag IDs, original event var IDs, item IDs and trainer IDs separate for every independently identified ROM. No global merged flag table or universal shared save is assumed. Source IDs and full original-ROM SHA-256 values bind both compiled scripts and snapshots.
- Execute against a working state clone and commit **only after successful `end`**. Invalid conditions, out-of-budget loops, recursive call overflow, absent inventory policy, malformed bytecode, forged IR and unexpected return all leave persistent source state unchanged.
- Explicit `BagPolicy` is a synthetic compatibility **contract**, not proof of actual Emerald bag pockets, capacity, species/item remapping, ROM-hack mechanics or save layout. The replay models result values but does not touch physical GBA Flash or invoke original game callbacks.
- Source snapshots store bounded structured records and checksums, verify original-ROM identity on restore, reject inconsistent source sets and duplicate entries, and apply all-world restoration atomically. A checksum detects accidental corruption; it is **not cryptographic authentication** against an intentional writer.

## Verifiable test boundaries

- Fast negative/script host tests, including 60,000 deterministic interleaved source-specific event replays, conditional control flow, nested calls, state rollback, modelled inventory, corruption, source mismatch and script identity checks.
- A second test uses the **actual R36 SHA-256 page format and R38 host pool**, mounts three distinct **synthetic** 32 MiB original-structure ROM images, compiles from the *same original numeric script offset* in all sources, and separately commits their flags with snapshot roundtrip. This tests 96 MiB **stored**, not 96 MiB GBA RAM.
- Existing R34–R37 regressions and an independent pinned `pret/pokeemerald` command implementation check.
- The separately verified R38 all-byte/90,000-window storage stress is retained; R39 does not duplicate its entire workload inside every unit test.

Run locally:

```sh
PYTHONPATH=tools:tests python3 -m unittest test_xgba_r39_script_sandbox.ScriptSandbox -v
PYTHONPATH=tools:tests python3 -m unittest test_xgba_r39_script_sandbox.R39RealPagePoolIntegration -v
```

CI: `.github/workflows/xgba-r39-script-sandbox.yml`. The real user-owned Team Rocket Edition English 3.06 image is not committed, copied into public CI, or embedded into test fixtures.

## Critical limitations / R40 direction

**R39 is a host sandbox and is not real Emerald event-script execution in patched mGBA.** It does not resolve arbitrary custom script opcodes, original engine `special` callbacks, trainer battle formats, native movement/warp, custom Pokémon mechanics, item pocket structures, or live shared saves. Source identities are isolated by design; this is not a claim of completed cross-ROM gameplay.

R40 should tackle **genuine native Emerald adapter integration**, beginning with a minimal source-scoped event command subset in a source-built Emerald/mGBA fixture and real game state observed through Flash save and cold restart. Separately build a **private three-real-ROM fixture** when an independently owned third Emerald-family binary and the private Team Rocket extracted page set are both available. Preserve original source data regardless of runtime compatibility, and keep private ROM/game bytes off public GitHub.
