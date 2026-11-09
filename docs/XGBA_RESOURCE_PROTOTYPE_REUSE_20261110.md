# XGBA opt-in resource expansion prototype — source reuse, not re-audit

**Status: IMPLEMENTATION PENDING. This is a product-prototype draft, not a Phase 1 semantic approval, a working expanded ROM or a hardware compatibility claim.**

## Sources to build upon — do not rediscover or duplicate

- [GBATEK](https://mgba-emu.github.io/gbatek/): established GBA memory, cartridge and wait-state mapping. Standard ROM has one 32 MiB CPU-visible window in three wait-state regions.
- [mGBA pinned Matrix source](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c): actual 64 MiB Matrix cartridge mapping; preserve this hardware behaviour, including paging, prefetch effects and savestate restoration.
- [XGBA existing Matrix native regression](../tests/mgba_bank_boundary.c), [source-pinned report](PHASE1_P0_MATRIX_NATIVE_BOUNDARY_PROBE_2026-10-26.md) and [external resource contract](PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md). Reuse these 34 baseline tests, do not recreate a 64 MiB Matrix model.
- [GBARecomp Matrix adaptation](https://github.com/mstan/gbarecomp/blob/main/src/gba/gba_matrix_memory.cpp), reference only. Its repository uses **PolyForm Noncommercial** licensing. Do not copy its source into XGBA without permission/licence compatibility review. mGBA uses **MPL-2.0** and requires preserving notices and covered-source obligations when copying code.
- [pret pokefirered](https://github.com/pret/pokefirered) and [Porymap](https://github.com/huderlem/porymap): source-based consumers, not proof that original hardware supports arbitrary ROM size.

## Narrow architectural decision

1. **Vanilla GBA:** unchanged <=32 MiB game works unchanged in existing emulators and on ordinary cartridges.
2. **Native Matrix:** unchanged 64 MiB mapped video-cart behaviour is independently implemented in mGBA and covered in our regression baseline. It is **not** a universal Pokemon ROM expansion scheme. Do not assign tasks to merely re-prove it.
3. **XGBA experimental:** preserve executable ROM and normal pointers. Store extra assets outside the ROM in a versioned sidecar, keyed by stable resource IDs with explicit mapping and hashes. Read only through **opt-in** host tooling. No arbitrary CPU pointer into external bytes, no reinterpretation of ROM2_EX, EEPROM, e-Reader or flash/save.
4. **Future integration:** stage a bounded resource into existing RAM/VRAM or an explicitly supported emulator extension; keep live buffer lifetime, DMA, audio, save and savestate identity consistent. Never claim normal GBA hardware compatibility for a host-only loader.
5. No copyrighted ROM assets in tests. Source identities and test evidence are mandatory.

## Delivery packages — non-overlapping scopes, in order

| ID | Required new code/test files | Acceptance |
|---|---|---|
| **R1** | `tools/xgba_resource_sidecar.py`, `tests/test_xgba_resource_sidecar.py` | **Real bytes, not just documentation:** streaming validated v1 manifest and resource reads, bounded offsets/sizes, checksums, no path traversal, mutation/short read/overflow controls, test a sparse 96 MiB sidecar without loading all bytes into RAM |
| **R2** | `tools/xgba_resource_pack.py`, `tests/test_xgba_resource_pack.py` | Deterministic package builder using R1, stable IDs, duplicate detection, atomic replace on success, byte-identical rebuild, failure rollback and exact identity tests |
| **R3** | `tools/xgba_resource_bridge.py`, `tests/test_xgba_resource_bridge.py` | Opt-in host staging proof with bounded windows and life-cycle; simulate ROM pointer preservation, save/snapshot identity, collision with native Matrix/EEPROM/flash cases; no emulator source edits until safely validated |

Each stage must produce meaningful executable tests, preserve pinned upstream source and explicitly label limitations. The independent review gate stays at **0 approvals** until a real reviewer independently signs off. CI passing is not signoff.

**Stop rules:** unexpected GitHub account access, duplicate Agent Task, ambiguous task POST, changed PR identity, tests failing, no code delta, changing source pins, missing expected files, or billing policy uncertainty. No agents may merge this branch, modify `main`, or alter unrelated projects.

Autonomous dispatch is managed separately in `.github/workflows/xgba-autonomous-product.yml`. Finite scope and daily limits are deliberate: uninterrupted delivery means reliably processing the known queue, not inventing work or silently consuming credits forever.
