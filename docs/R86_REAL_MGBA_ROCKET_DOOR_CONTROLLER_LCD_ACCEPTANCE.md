# R86: owner-private real mGBA physical Rocket room acceptance

R85 now binds all 435 private original source page records, including three original R48 NPC witness packets, to the exact SHA-256 of the **source-built Emerald** game, while preserving original R17 boot and external map resources. R86 adds a real emulator execution mode, not a host map switch: original `GBACore` receives a limited script of authentic physical GBA key presses via `core->setKeys`, frame-by-frame `runFrame`. At each native R80 proof counter increment it reads **only** original Emerald EWRAM `gXgbaR80SourceRoomProof` and captures **real LCD PNG** from the active video buffer. The only accepted transition order is original Rocket source `0x010009` -> original Rocket room `0x012304` -> original Rocket landing `0x010009`, with two physically spawned original maps, original art/actor verification, no rejected resources and two actual LCD captures.

The owner-private controller script contains **only** lines `<frame_count decimal> <button_mask hex> <snapshot 0|1>`; mask bits 0..9 are A, B, SELECT, START, RIGHT, LEFT, UP, DOWN, R, L. Comment lines begin `#`. Each input segment is bounded to 2400 frames, entire plan 36000 frames and 256 actions. Choose an input script based on actual played positions, **do not fabricate** an arrival. The R80 proof address must be read from the exact native Emerald ELF symbol table; no guessed addresses.

Run after building the patched original Emerald ROM and XGBA mGBA and binding owner-private R79 with R85:
```sh
python3 tools/xgba_r86_private_rocket_mgba_acceptance.py \
  --built-emerald /private/pokeemerald_modern.gba \
  --bound-private-manifest /private/r85-bound/manifest.json \
  --patched-mgba /private/mgba-build/xgba-mgba-headless \
  --controller-script /private/r86-real-keys.txt \
  --emerald-elf-r80-proof 0x020XXXXX \
  --private-evidence-dir /private/r86-lcd
```
The R86 runner refuses missing private sources and requires the owner-private R85 source manifest attestation; no original ROMs/ZIPs/PNG are published to the public repository. The runner only writes a successful acceptance report once the original game physically traverses both correct doors and the patched emulator captures both arrival LCD frames. This cannot yet be executed by public GitHub Actions, which only have authored source fixtures and genuine Emerald build assets, not the user's private Rocket provider.

**Status:** R86 source and real mGBA build hooks are implemented, tests verify code and ABI. The actual owner-private mGBA player journey and true three-world Fly acceptance are not claimed until real native screenshots and proof logs exist. Foreign-world Flash persistence and Heart & Soul original art remain separate blockers.
