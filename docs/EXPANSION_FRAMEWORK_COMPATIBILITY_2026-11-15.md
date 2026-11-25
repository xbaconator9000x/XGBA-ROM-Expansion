# XGBA expansion-framework compatibility — priority 1

**Decision: 15 November 2026 (Australia/Brisbane).**
**Status: source-adapter implementation in progress; NO expanded-engine native gameplay acceptance yet.**

## Explicit suspension of the old three-ROM integration

Pause draft [PR #123](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/123)
without closing, resetting, merging, or deleting it. Its complete-source inventories,
Rocket/Celadon, Heart & Soul/Goldenrod, and original Emerald/Lilycove work are
valuable preserved checkpoints. Do not build further three-world tests until
the user explicitly resumes them.

The expansion architecture, **not a three-game port**, is now the highest priority.

## What "FireRed expansion" means here

Upstream [RH-Hideout/pokeemerald-expansion](https://github.com/rh-hideout/pokeemerald-expansion)
now supports **three build variants in one framework**:

| Upstream variant | Command | Game macro | XGBA EWRAM resource ID |
| --- | --- | --- | --- |
| Emerald | make emerald | EMERALD | expansion.emerald.bridge |
| FireRed | make firered | FIRERED | expansion.firered.bridge |
| LeafGreen | make leafgreen | LEAFGREEN | expansion.leafgreen.bridge |

RHH added FRLG support in its 1.15 series; the first test baseline here is
**release tag expansion/1.17.2** (31 October 2026). CI resolves and reports
the actual commit of that tag. This is **not** a claim that original
pret/pokefirered, CFRU/DPE, or arbitrary independently modified FireRed
binaries use the same linker layout and hooks. Treat those as separately
versioned compatibility profiles.

## What was already working, and what was missing

- **Already demonstrated**: the shared XGBA guest MMIO ABI (0x04FF8000,
  magic 0x58474241, ABI 1) and native mGBA sidecar fetches in original
  pret/pokefirered and pret/pokeemerald source builds, including EWRAM/
  VRAM and genuine Flash recovery under selected tests.
- **Not previously established**: a source adapter and executed native
  loader for RHH's pokeemerald-expansion Emerald and FRLG variants,
  with their modified heaps, linker tables, callbacks, saves, and art
  loading.
- **Not established by this bootstrap**: functional RHH maps/graphics,
  native sidecar fetch in an actual expansion game, real LCD evidence,
  Flash cold restart, save-state recovery, Android performance or
  support for arbitrary ROM hacks.

This new branch implements a deliberately **small but genuine source
bootstrap**: validates the upstream build matrix, inserts a source-level
probe after the original heap initialization, reuses the existing XGBA
MMIO guest header, gives each variant a distinct resource ID and
diagnostic marker, then returns to the upstream game path even without
an external provider. It restores src/main.c on any normal build
completion or exception. Invalid source signatures and duplicate
application fail closed; synthetic negative tests cover both.

The upstream ARM build matrix runs for all three targets and checks
the real ELF symbols, not just Python fixtures. **A successful source
build by itself is not native external-storage acceptance.**

## Required next acceptance gates (do not substitute tests)

1. Build pinned RHH Emerald, FireRed and LeafGreen with the source adapter
   and prove the original source is restored. Record upstream Git SHA,
   XGBA head, EWRAM linker usage and emitted ROM size.
2. With the SAME patched mGBA provider already used for vanilla tests,
   boot both Emerald and FireRed RHH variants and verify each guest
   actually fetches a SHA-checked page from beyond 32 MiB into real
   EWRAM. Disabled provider must read zero pages and leave the sentinel.
   Capture native 240x160 LCD and guest register proof. LeafGreen
   should pass the same gate before labelled supported.
3. Integrate runtime resource hooks into the actual RHH map/tileset and
   battle asset lifetimes, with measured EWRAM, BG/OBJ VRAM, OAM,
   palette, decompression and DMA limits. No synthetic substitutes.
4. Exercise repeated map transitions, cache eviction and native Flash
   save/cold restart for at least one real external resource per
   framework game variant. Test missing/mismatched packs fail closed.
5. Only then advertise *version-pinned, tested* RHH compatibility and
   extend to user forks, separate pret/pokefirered profiles, and
   if separately verified, CFRU/DPE-like FireRed hacks.

Never commit copyrighted ROMs, compiled ROM binaries, extracted private
Nintendo art, private provider packs, Flash saves or signing secrets
to public GitHub. Native CI evidence and source-safe synthetic fixtures
are acceptable. Keep implementation reports precise about each gate.
