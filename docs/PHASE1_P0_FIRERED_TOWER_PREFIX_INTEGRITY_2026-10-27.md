# Phase 1 P0 — Trainer Tower active-prefix integrity versus physical-sector presence

**27 October 2026 · exact-pinned source trace and synthetic byte model · NOT an emulator test or independent approval.** Pinned FireRed: [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982). Phase 1 **FAIL_INCOMPLETE**; Phase 2 untouched.

## Source identities and producer/consumer closure

| Source | Exact Git blob | Role |
| --- | --- | --- |
| src/cereader_tool.c | 395be0bcbed8454e645a9f5670cde3024eda508e | Set/floor validators, split writer and paired reader |
| src/save.c | 36b960f375c92711aa49b99bdfe9c6b3a99d6b1c | Special-sector sentinel, physical flash reader/writer |
| src/util.c | b32799584937a120a03b08897886f08adc033fce | Actual additive byte checksum |
| src/ereader_screen.c | 20ec25d0150084bc259de47038ac7d8c972dd268 | Remote card validation before save |
| include/gba/isagbprint.h | 9c79e03e8e95c02b17361073eff841bd59a8311c | NDEBUG-dependent assert macro |
| include/cereader_tool.h | 5cb5a9ebc32db23de07800ccce124bcb28d3ef15 | Set/floor declarations and checksum fields |
| include/save.h | 87fb9b615b434b58823d15688056695acda9feab | Sector constants, counter-offset and sentinel |
| include/constants/trainer_tower.h | ea0039ea1408c06b8c968cfde8e2628213b2a0dc | Eight-floor and challenge-type bounds |

**Producer:** CEReaderTool_SaveTrainerTower_r (src/cereader_tool.c:45–60) zeroes the temporary buffer, copies the first SEC30_SIZE bytes, changes byte 1 to GetTrainerHillUnkVal(), writes physical sector 30, then zeroes and fills the buffer with the remaining SEC31_SIZE bytes and writes sector 31. The first-sector byte-1 change is part of the native producer and must be preserved by a byte-exact save comparison. The writer returns failure if either write fails; atomicity of two physical writes is **not** established.

**Reader:** CEReaderTool_LoadTrainerTower_r (src/cereader_tool.c:70–83) requires both special-sector reads to return 1, copies both halves, and invokes ValidateTrainerTowerData. TryReadSpecialSaveSector (src/save.c:831–855) checks a four-byte sentinel and copies 4,092 bytes, not a conventional save-slot checksum. Its success does not authenticate the copied Trainer Tower payload.

**Logical validator:** ValidateTrainerTowerData (src/cereader_tool.c:29–43) requires 1 <= numFloors <= 8, validates each floor **only for i < numFloors**, and compares the stored set checksum against CalcByteArraySum(floors, numFloors * sizeof(floor)). ValidateTrainerTowerTrainer (:18–27) checks floor index, challenge type and a per-floor checksum over the bytes preceding the floor's checksum field. CalcByteArraySum (src/util.c) simply adds bytes into a 32-bit accumulator; it is not an order-sensitive or cryptographic digest. The set checksum does **not** cover the eight-byte set header. The native writer explicitly changes header byte 1 after copying the set, and the reader's logical validator does not compare header id/dummy against an expected value. These fields are not covered by the checksum predicates, although separate gameplay consumers may impose other requirements.

## e-Reader input and debug-only assertion boundary

The pinned e-Reader state machine (src/ereader_screen.c:461–483) calls ValidateTrainerTowerData on the received gDecompressionBuffer and, after successful disconnect, passes the same buffer to CEReaderTool_SaveTrainerTower. The writer has AGB_ASSERT_EX checks that set id and dummy are zero (src/cereader_tool.c:45–49), **but these checks are not part of ValidateTrainerTowerData**. In include/gba/isagbprint.h, NDEBUG expands AGB_ASSERT_EX to an empty macro; without NDEBUG it calls DebugAssert. Consequently, the source-level receive/save path has a **build-configuration-dependent assertion boundary**, not unconditional runtime validation of these header bytes. The received data is still constrained by the floor/set checksum predicates and any additional untraced link or gameplay checks. This does not establish a malformed-card exploit or a particular production-build configuration.

## Conditional active-prefix boundary

The separately established [ARMv4T Clang layout witness](PHASE1_P0_FIRERED_TOWER_ARM_LAYOUT_2026-10-27.md) measured 992 bytes per floor, 8 bytes of set header, and a 7,944-byte complete set. This checker **reuses** those numbers; it does not compile the ABI again. The split is **3,976 bytes in sector 30** (header + four floors) and **3,968 bytes in sector 31** (four floors). The physical special-sector wrapper has 4,092 payload bytes; the remainder is padding in the native writer.

| Authored numFloors | Floor bytes included in logical checksum | Floor bytes outside logical checksum | Physical sector 31 sentinel required? |
| --- | ---: | ---: | --- |
| 1 | 992 | 6,944 | Yes |
| 4 | 3,968 | 3,968 (entire second half) | Yes |
| 5 | 4,960 | 2,976 | Yes |
| 8 | 7,936 | 0 | Yes |

For a four-floor set, **sector 31 is required to have the expected sentinel even though its four floor records are not inspected by the set/floor checksum checks**. Conversely, for five floors, the fifth floor in sector 31 participates in both validation layers while the remaining three floors do not. This is a **conditional source-level representation contract**, not evidence that unused floor bytes affect gameplay, that a normal save is malformed, or that the game accepts a missing second sector.

A deterministic synthetic record model constructs valid per-floor and set checksums for counts 1, 4, 5 and 8. Changing a byte in an inactive floor leaves these modeled predicates true; changing a byte in an active floor makes them false; a missing second sentinel always fails. Mutating the header id and dummy bytes also leaves these modeled checksum predicates true. A two-byte permutation inside an active floor preserves both additive checksums after constructing the initial valid checksums. That is a checksum-collision **model**, not a claim that a specific altered trainer record is accepted by all game consumers.

## Reproduction and fail-closed boundaries

Run [the checker](../tools/phase1_tower_prefix_integrity.py) against a local checkout of the **exact pinned commit**:

    python3 tools/phase1_tower_prefix_integrity.py --source-dir /path/to/pinned-pokefirered --self-test --out tower-prefix-integrity.json

It checks eight exact Git blob IDs, source anchors and removal-mutation controls, and emits separate synthetic results. [Dedicated CI workflow](../.github/workflows/phase1-tower-prefix-integrity.yml) obtains the pinned sources independently. **A passing workflow at the exact commit is required before recording CI success.**

**Unresolved:** original agbcc layout equivalence; compiled/linked binary validation paths; physical flash partial-write/recovery behaviour; mGBA/hardware tests with one-to-eight-floor fixtures and checksum collisions; consumers of inactive floors; e-Reader card input constraints and debug/release assertion behavior; Qt/editor import-export preservation; extension/sidecar integrity requirements; independent full-file review of the involved implementations. Do not convert these gaps into PASS. This dossier adds no independent approval and makes no Phase 2 changes.

## Additional synthetic cross-generation sector witness (27 October 2026)

A second deterministic fixture reuses the same exact-pinned source anchors, ARM-layout assumptions, and modeled native predicates. It constructs two *individually valid* Trainer Tower sets with different payload markers, then combines the **newer first physical half** with the **older second physical half**, keeping both special-sector sentinels valid. This represents a hypothetical interrupted two-sector update; it does **not** demonstrate that a physical write actually fails this way.

For **one and four floors**, the combined record passes the modeled validator, because the active checksum prefix ends in sector 30. For **five and eight floors**, the fixture fails, because the active prefix includes changed bytes in sector 31. Removing either sentinel rejects every case. These are explicit synthetic results, not emulator execution or a claim about inactive-floor gameplay. The script now records the four cases under `torn_generation_cases` in the existing JSON evidence, and the existing exact-source CI workflow exercises them on every run.

The source-level consequence is a **lack of a cross-sector generation identity** in the traced Tower validation path: a valid sentinel on the older second sector cannot alone prove that both sectors came from one write transaction. Actual flash partial-write behavior, original agbcc equivalence, and native/mGBA recovery observations remain **FAIL_INCOMPLETE**. No new machine-triaged file, complete-file review candidate, or independent approval is claimed.


## Physical special-sector wrapper and nominal counter bytes (27 October 2026)

A new deterministic wrapper witness traces the exact physical copy loop in pinned `src/save.c:833–879`, together with the `struct SaveSector` field layout in `include/save.h`. The ordinary save-sector layout is 3,968 data bytes, 116 unused bytes, 2-byte id, 2-byte checksum, 4-byte signature, and a 4-byte counter, totaling 4,096 bytes. Thus `SECTOR_COUNTER_OFFSET = 4092`. Both special-sector loops set `size = SECTOR_COUNTER_OFFSET - 1`, start at `gSaveDataBuffer.data[4]`, and copy with `i <= size`: **4,092 bytes at physical offsets 4–4,095 inclusive**. The four-byte sentinel occupies offsets 0–3. The last four copied bytes overlap the field named `counter` in the ordinary `SaveSector` layout; they are *not* excluded by the special-sector copy. The source comment saying the copy excludes the counter field is therefore misleading if read literally.

The special-sector writer sets the sentinel and copies the 4,092-byte caller buffer before `ProgramFlashSectorAndVerify`; the reader checks only the sentinel before returning the 4,092-byte copied payload. The model verifies the inclusive upper bound, absence of a 4,096-byte buffer overrun, rejection of a modified sentinel, and lack of wrapper authentication for a modified last physical byte. The wrapper does **not** validate the ordinary save-sector `id/checksum/signature/counter` fields, and no normal save-slot counter semantics should be inferred for these two special sectors.

The Trainer Tower payloads (3,976 and 3,968 bytes) fit inside their respective 4,092-byte special-sector buffers. A newly constructed wrapper model is **not** evidence of actual flash writes, power-loss behaviour, agbcc equivalence or mGBA runtime behavior. Its provenance is the eight exact-pinned source blobs already enforced by the checker, with added source anchors and removal-mutation controls for `ReadFlash` and the sentinel assignment. **No new distinct machine-triaged file, whole-file candidate or independent approval is claimed.** All Phase 1 gates remain **FAIL_INCOMPLETE**.

## Source-level gameplay reachability qualification (27 October 2026)

**Critical limitation on the synthetic torn-sector hazard:** The pinned FireRed implementation of `ReadTrainerTowerAndValidate(void)` in `src/cereader_tool.c:93–97` is a stub that unconditionally returns `FALSE` (the source explicitly notes it is populated in Emerald). In `src/trainer_tower.c:514–537`, `SetUpTrainerTowerDataStruct` calls `CEReaderTool_LoadTrainerTower` **only if** that stub returns `TRUE`. Otherwise, it constructs the active gameplay tower from the local `gTrainerTowerLocalHeader` and `gTrainerTowerFloors[challengeType]`. In `src/trainer_tower.c:769–784`, the challenge-start branch also calls the stub, making the local validated-state branch unconditional under this pinned source. The special table in `data/specials.inc` registers the same function.

Consequently, **the modeled mixed-generation special-sector acceptance is not demonstrated as a reachable normal Trainer Tower gameplay path in this pinned FireRed source**. The e-Reader input state machine can still call `CEReaderTool_SaveTrainerTower` and write the two sectors; the sector read/validation functions remain analyzable representations and potential future engine interfaces. A modified ROM, an Emerald-derived implementation, or a different binary could change reachability. Do not generalize the stub to other engines.

The checker now pins two additional upstream source blobs, `src/trainer_tower.c` (`732b3f2ed31ed95d6476b9e111d53f759c448d81`) and `data/specials.inc` (`d880bf6b9dc9fd765f0b85e6d698411e3da81d5d`), and adds source-removal negative controls for the gameplay caller/fallback and stub. This is a **static source-control-flow conclusion**, not a linked binary or emulator execution proof. The malformed-sector and cross-generation synthetic witnesses remain useful for designing future compatibility tests, but **must not be reported as an observed player-facing vulnerability in stock FireRed**.

No new distinct machine-indexed file is counted (both are already within the existing source inventory), no new complete-file analyst review is claimed, and no independent approval was granted. Phase 1 remains **FAIL_INCOMPLETE**.

## Original-agbcc linked stub ABI experiment (2026-10-28; pending exact-head CI)

The source-only reachability conclusion above now has a separate **compiled/linker** test. A new job checks out exact FireRed `ce6406d8c2eaf46d543c8a2606de0c3cb1951982` and original `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9`, verifies the pinned `src/cereader_tool.c` and `src/trainer_tower.c` Git blobs, builds an actual FireRed ELF, and disassembles its linked `ReadTrainerTowerAndValidate` symbol using `arm-none-eabi-objdump`. The verifier requires one linked text symbol, exactly a constant-zero return assignment to `r0` and a direct `bx lr` return; it rejects seven synthetic disassembly mutations including a nonzero return, wrong register, wrong branch, missing symbol, call injection, missing return and extra instruction. The linked ELF SHA-256 and actual instructions are retained as **text-only evidence**; no ROM/ELF is uploaded.

**This is an implemented but not yet verified compiled experiment.** If the original compiler emits a different valid return sequence, the fail-closed test must be reconciled against actual disassembly rather than weakening the semantic claim. It is not native execution of the Tower branch, nor evidence that e-Reader sector data is reachable by stock FireRed gameplay. Independent whole-file approval remains zero and Phase 1 `FAIL_INCOMPLETE`.
