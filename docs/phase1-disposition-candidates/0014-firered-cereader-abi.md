# Phase 1 whole-file analyst candidate 0014 — FireRed Trainer Tower e-Reader ABI declarations

**State: PENDING_INDEPENDENT_REVIEW.** Not an independently approved disposition or gate input.

## Immutable source identity
`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; `include/cereader_tool.h`; Git blob `5cb5a9ebc32db23de07800ccce124bcb28d3ef15` verified at the exact pinned ref. [Complete file](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/cereader_tool.h). [Pinned local-floor/e-Reader branch investigation](../PHASE1_P0_FIRERED_TOWER_LOCAL_FLOOR_BRANCH_2026-10-26.md).

## Entire-file semantic inventory
1. Guard `GUARD_CEREADER_TOOL_H`; includes `global.h` and `constants/trainer_tower.h`, establishing dependencies on `u8`, `u16`, `u32`, `bool32`, `BattleTowerPokemon`, `PARTY_SIZE`, `MAX_TRAINERS_PER_FLOOR` and `MAX_TRAINER_TOWER_FLOORS`.
2. `struct TrainerTowerTrainer`: `name[11]` at documented offset `0x000`; `facilityClass` at `0x00B`; `textColor` at `0x00C`; `speechBefore[6]` at `0x00E`; `speechWin[6]` at `0x01A`; `speechLose[6]` at `0x026`; `speechAfter[6]` at `0x032`; `mons[PARTY_SIZE]` of `BattleTowerPokemon` at `0x040`. The source comments state total size 328 bytes. Padding at offsets 0x00D and 0x03E–0x03F is **implied by annotated offsets**, not enforced by packed declarations or compile-time assertions here.
3. `struct TrainerTowerFloor`: `id`, `floorIdx`, `challengeType`, `prize` as four consecutive `u8` fields at offsets 0–3; `trainers[MAX_TRAINERS_PER_FLOOR]` begins at `0x004`; `checksum` is a `u32` at annotated offset `0x3DC`. With the annotated trainer size 328 and three trainers, this yields 4 + 984 = 988 (`0x3DC`) before checksum, and a **candidate** floor size 992 (`0x3E0`) bytes. Actual ABI size/alignment must be confirmed with compiler assertions.
4. `struct EReaderTrainerTowerSetSubstruct`: `u8 numFloors`, `u8 id`, `u16 dummy`, `u32 checksum` in declaration order. Nominal size 8 under the expected ABI, not locally asserted.
5. `struct EReaderTrainerTowerSet`: repeats the four header fields and embeds `floors[MAX_TRAINER_TOWER_FLOORS]` (8 under pinned constants). The nominal size under the above inferred ABI is 8 + 8×992 = 7,944 bytes; this is **not compiled proof**, nor proof that all floor records are populated or validated.
6. Four external `bool32` function prototypes: `ValidateTrainerTowerData(struct EReaderTrainerTowerSet *ttdata)`, `CEReaderTool_SaveTrainerTower(...)`, `CEReaderTool_LoadTrainerTower(...)`, and `ReadTrainerTowerAndValidate(void)`. This header contains **no implementations**, checksums, persistence rules, file I/O, pointer validation or executable instructions.
7. Closing include guard.

## Cross-file dependencies and XGBA relevance
The e-Reader serialization ABI potentially depends on compiler padding, endianness, nested `BattleTowerPokemon` layout, `PARTY_SIZE`, trainer/floor counts, checksum computation and save/copy semantics. A future expansion cannot safely enlarge these structures or treat the dormant e-Reader path as enabled without tracing validation, save storage and actual reader/writer consumers. Existing pinned Trainer Tower work distinguishes the active local-floor branch from the e-Reader loader; source declarations here alone do not establish whether malformed records can reach a gameplay path.

## Review obligations
- **Verified:** exact pinned source and blob; every structure field and function prototype; source-annotated offsets and nominal size arithmetic.
- **Unverified:** compiled `sizeof`/`offsetof` on both compiler variants, nested Pokémon structure ABI, all callers and validation paths, e-Reader checksum acceptance, persistence and editor round trips, actual runtime reachability.
- Independent reviewer identity/date/verdict: **not supplied; pending**. Do not increment authoritative approval counts.

**Phase 1 gate: FAIL_INCOMPLETE; independent approvals 0/14,834.**
