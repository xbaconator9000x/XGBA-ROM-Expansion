# XGBA ROM Expansion — source-grounded interoperability research

## Current project status

**Phase 1 source mapping: FAIL_INCOMPLETE.** No XGBA unlimited-memory ROM/runtime has been implemented or released. This repository is a persistent, source-pinned research and test environment.

Start here: **[Current authoritative Phase 1 status](docs/PHASE1_STATUS.md)**.

- Five pinned source repositories, **14,834 tracked files** inventoried and **4,685 source/config blobs** verified. The mapping dossiers are automated, not independent semantic signoffs; **0/14,834 dispositions approved**.
- [34/34 native mGBA synthetic-cartridge regression checks](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40204719637): original ROM loader, ARM/Thumb fetch and bank remaps, EEPROM/e-Reader, DMA3, local and whole-emulator savestates. **Four native unsafe behaviours remain known.**
- [Fail-closed evidence gate](tools/verify_native_mgba_regressions.py): requires all 34 named checks and four native-gap observations, verifies result metadata and test SHA, and has ten negative fixtures. [Confirmed CI execution](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40205086061).
- [Opt-in expansion compatibility constraints](docs/PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md): the native mGBA Matrix physical address is only 26 bits (64 MiB), so a future arbitrary-size sidecar would need a separate resource addressing/streaming protocol.
- CI source evidence and immutable checkpoints are kept under `semantic-snapshots/`, `docs/`, `tools/` and GitHub Actions artifacts. Never infer Phase 1 completion from lexical census or native-emulator regression success.

### Reproducing the native mGBA regression

On a network-connected Linux build host with Git, GCC, CMake and Python 3:

```bash
bash tests/run_pinned_mgba_boundary.sh
python3 tools/verify_native_mgba_regressions.py --self-test
# Existing compiled-mgba CI also captures the machine-readable verification record.
```

The script clones/checks out exact pinned upstream mGBA, validates Git blob hashes and builds a separate synthetic-cartridge test executable; it does not modify mGBA itself.
