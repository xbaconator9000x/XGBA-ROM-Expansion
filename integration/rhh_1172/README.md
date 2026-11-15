# RH-Hideout expansion adapter — scoped engineering checkpoint (15 Nov 2026)

**Supported upstream pin under investigation:** RH-Hideout `pokeemerald-expansion` release `expansion/1.17.2`, exact upstream commit `79dd436920845ebc145577649de624f65298c209`. Verified against upstream `Makefile` at that tag: default Emerald (`BPEE`), `make firered` (`BPRE`), and `make leafgreen` (`BPGE`); FireRed and LeafGreen use `MAP_VERSION=firered`. These are three *build targets of the same expansion codebase*, not the ABI of pret/pokefirered or CFRU.

## Reused infrastructure

The existing XGBA `integration/mgba/xgba_mgba_device.h` exposes opt-in 32-bit MMIO at `0x04FF8000`, magic `0x58474241`, ABI 1, EWRAM resource-ID and destination pointers, bounded fetch status/length and 16-KiB transfer limit. Its provider authenticates source identity and SHA-256. The existing `integration/fire_red/xgba_guest.h` demonstrates guest-originated MMIO. Existing Emerald and FireRed native tests, cache invalidation, DMA source protection and lease lifecycle remain separate evidence, not proof of RHH integration.

`xgba_rhh_guest.h` is a **new, opt-in guest-side entry point**. It fails compilation for non-32-bit builds, missing opt-in, or ambiguous target selection; rejects zero/oversized pages, non-EWRAM pointers, unsupported host magic/version and non-success or oversized responses. The caller must own its lease and keep DMA/decompression consumers alive until safe release. This adapter deliberately does not redefine the host ABI or create a new emulator implementation.

## Build and acceptance gate — not yet passed

1. Fetch the *exact* upstream commit, verify SHA and build clean `make -j2`, `make firered -j2`, `make leafgreen -j2` using upstream's required ARM toolchain. No game ROMs should be committed.
2. Integrate the header in each **actual upstream loader path** (map or graphics) with a build flag, a bounded dedicated EWRAM lease and an external resource absent from the compiled ROM. Preserve upstream unmodified build with the flag off.
3. Run the resulting three actual GBA binaries in the pinned patched mGBA with source-identity-bound provider pages, verify in-game MMIO read, real EWRAM and VRAM bytes, cache eviction/reacquisition, Flash cold restart and genuine LCD captures. Reject wrong ABI, mismatched provider, missing pages, stale leases and stock emulator. Native test logs and exact-head CI required before any pass claim.
4. Independently evaluate pret/pokefirered and CFRU-derived hacks by source/patch identity and their own symbols/layout; do **not** treat RHH's FireRed target as proof of either.

**Current result:** first guest MMIO adapter committed; no upstream build, loader-hook execution, patched-mGBA gameplay, Flash cold-restart or screenshots completed. Compatibility remains **unverified**. PR #123's three-world work is frozen and not part of this branch.
