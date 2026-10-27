# Phase 1 P0 — Trainer Tower active-prefix integrity versus physical-sector presence

**27 October 2026 · exact-pinned source trace and synthetic byte model · NOT an emulator test or independent approval.** Pinned FireRed: [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982). Phase 1 **FAIL_INCOMPLETE**; Phase 2 untouched.

## Source identities and producer/consumer closure

| Source | Exact Git blob | Role |
| --- | --- | --- |
| src/cereader_tool.c | 395be0bcbed8454e645a9f5670cde3024eda508e | Set/floor validators, split writer and paired reader |
| src/save.c | 36b960f375c92711aa49b99bdfe9c6b3a99d6b1c | Special-sector sentinel, physical flash reader/writer |
| src/util.c | b32799584937a120a03b08897886f08adc033fce | Actual additive byte checksum |
| include/cereader_tool.h | 5cb5a9ebc32db23de07800ccce124bcb28d3ef15 | Set/floor declarations and checksum fields |
| include/save.h | 87fb9b615b434b58823d15688056695acda9feab | Sector constants, counter-offset and sentinel |
| include/constants/trainer_tower.h | ea0039ea1408c06b8c968cfde8e2628213b2a0dc | Eight-floor and challenge-type bounds |

**Producer:** CEReaderTool_SaveTrainerTower_r (src/cereader_tool.c:45–60) zeroes the temporary buffer, copies the first SEC30_SIZE bytes, changes byte 1 to GetTrainerHillUnkVal(), writes physical sector 30, then zeroes and fills the buffer with the remaining SEC31_SIZE bytes and writes sector 31. The first-sector byte-1 change is part of the native producer and must be preserved by a byte-exact save comparison. The writer returns failure if either write fails; atomicity of two physical writes is **not** established.

**Reader:** CEReaderTool_LoadTrainerTower_r (src/cereader_tool.c:70–83) requires both special-sector reads to return 1, copies both halves, and invokes ValidateTrainerTowerData. TryReadSpecialSaveSector (src/save.c:831–855) checks a four-byte sentinel and copies 4,092 bytes, not a conventional save-slot checksum. Its success does not authenticate the copied Trainer Tower payload.

**Logical validator:** ValidateTrainerTowerData (src/cereader_tool.c:29–43) requires 1 <= numFloors <= 8, validates each floor **only for i < numFloors**, and compares the stored set checksum against CalcByteArraySum(floors, numFloors * sizeof(floor)). ValidateTrainerTowerTrainer (:18–27) checks floor index, challenge type and a per-floor checksum over the bytes preceding the floor's checksum field. CalcByteArraySum (src/util.c) simply adds bytes into a 32-bit accumulator; it is not an order-sensitive or cryptographic digest. The set checksum does **not** cover the eight-byte set header.

## Conditional active-prefix boundary

The separately established [ARMv4T Clang layout witness](PHASE1_P0_FIRERED_TOWER_ARM_LAYOUT_2026-10-27.md) measured 992 bytes per floor, 8 bytes of set header, and a 7,944-byte complete set. This checker **reuses** those numbers; it does not compile the ABI again. The split is **3,976 bytes in sector 30** (header + four floors) and **3,968 bytes in sector 31** (four floors). The physical special-sector wrapper has 4,092 payload bytes; the remainder is padding in the native writer.

| Authored numFloors | Floor bytes included in logical checksum | Floor bytes outside logical checksum | Physical sector 31 sentinel required? |
| --- | ---: | ---: | --- |
| 1 | 992 | 6,944 | Yes |
| 4 | 3,968 | 3,968 (entire second half) | Yes |
| 5 | 4,960 | 2,976 | Yes |
| 8 | 7,936 | 0 | Yes |

For a four-floor set, **sector 31 is required to have the expected sentinel even though its four floor records are not inspected by the set/floor checksum checks**. Conversely, for five floors, the fifth floor in sector 31 participates in both validation layers while the remaining three floors do not. This is a **conditional source-level representation contract**, not evidence that unused floor bytes affect gameplay, that a normal save is malformed, or that the game accepts a missing second sector.

A deterministic synthetic record model constructs valid per-floor and set checksums for counts 1, 4, 5 and 8. Changing a byte in an inactive floor leaves these modeled predicates true; changing a byte in an active floor makes them false; a missing second sentinel always fails. A two-byte permutation inside an active floor preserves both additive checksums after constructing the initial valid checksums. That is a checksum-collision **model**, not a claim that a specific altered trainer record is accepted by all game consumers.

## Reproduction and fail-closed boundaries

Run [the checker](../tools/phase1_tower_prefix_integrity.py) against a local checkout of the **exact pinned commit**:

    python3 tools/phase1_tower_prefix_integrity.py --source-dir /path/to/pinned-pokefirered --self-test --out tower-prefix-integrity.json

It checks six exact Git blob IDs, source anchors and removal-mutation controls, and emits separate synthetic results. [Dedicated CI workflow](../.github/workflows/phase1-tower-prefix-integrity.yml) obtains the pinned sources independently. **A passing workflow at the exact commit is required before recording CI success.**

**Unresolved:** original agbcc layout equivalence; compiled/linked binary validation paths; physical flash partial-write/recovery behaviour; mGBA/hardware tests with one-to-eight-floor fixtures and checksum collisions; consumers of inactive floors; Qt/editor import-export preservation; extension/sidecar integrity requirements; independent full-file review of the involved implementations. Do not convert these gaps into PASS. This dossier adds no independent approval and makes no Phase 2 changes.
