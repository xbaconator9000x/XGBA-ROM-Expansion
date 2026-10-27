# Phase 1 whole-file analyst candidate 0013 — FireRed Trainer Tower constants

**State: PENDING_INDEPENDENT_REVIEW; not approved.**

## Pinned upstream identity
`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`; `include/constants/trainer_tower.h`; exact Git blob `ea0039ea1408c06b8c968cfde8e2628213b2a0dc` (verified at pinned ref). [Full source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/constants/trainer_tower.h). Cross-file evidence: [Trainer Tower local-floor record types](../PHASE1_P0_FIRERED_TOWER_LOCAL_FLOOR_RECORD_TYPES_2026-10-26.md), [floor progress](../PHASE1_P0_FIRERED_TOWER_FLOOR_PROGRESS_2026-10-26.md).

## Whole-file declaration and value inventory
1. Header guard `GUARD_CONSTANTS_TRAINER_TOWER_H`.
2. Challenge types: `SINGLE=0`, `DOUBLE=1`, `KNOCKOUT=2`, `MIXED=3`; the comment says mixed challenges use one of the first three per floor. **Four overall challenge values are not interchangeable with the three per-floor record types.**
3. Statuses: `LOST=0`, `UNK=1` (comment says never set, possibly e-Card related), `NORMAL=2` (not started/ongoing). The comment is not proof of unreachable `UNK` for all malformed saved states.
4. Prize IDs: `HP_UP=0`, `PROTEIN=1`, `IRON=2`, `CARBOS=3`, `CALCIUM=4`, `ZINC=5`, `BRIGHT_POWDER=6`, `WHITE_HERB=7`, `MENTAL_HERB=8`, `CHOICE_BAND=9`, `KINGS_ROCK=10`, `SCOPE_LENS=11`, `METAL_COAT=12`, `DRAGON_SCALE=13`, `UP_GRADE=14`. This header declares IDs only, not prize distribution logic or valid array lengths.
5. Capacity constants: `MAX_TRAINER_TOWER_FLOORS=8`, `MAX_TRAINERS_PER_FLOOR=3`.
6. Dispatch IDs `TRAINER_TOWER_FUNC_*`: `INIT_FLOOR=0`, `GET_SPEECH=1`, `DO_BATTLE=2`, `GET_CHALLENGE_TYPE=3`, `CLEARED_FLOOR=4`, `GET_FLOOR_CLEARED=5`, `START_CHALLENGE=6`, `GET_OWNER_STATE=7`, `GIVE_PRIZE=8`, `CHECK_FINAL_TIME=9`, `RESUME_TIMER=10`, `SET_LOST=11`, `GET_CHALLENGE_STATUS=12`, `GET_TIME=13`, `SHOW_RESULTS=14`, `CLOSE_RESULTS=15`, `CHECK_DOUBLES=16`, `GET_NUM_FLOORS=17`, `SHOULD_WARP_TO_COUNTER=18`, `ENCOUNTER_MUSIC=19`, `GET_BEAT_CHALLENGE=20`. Values are contiguous 0–20; no local range-check implementation.
7. Text selection IDs: `INTRO=2`, `PLAYER_LOST=3`, `PLAYER_WON=4`, `AFTER=5`. No declarations for IDs 0/1 in this header; do not infer they are invalid globally.
8. `TRAINER_TOWER_MAX_TIME=215999` with comment `60 * 60 * 60 - 1`; numeric equivalence holds. The unit and overflow handling must be verified in consumers.
9. Closing guard; no functions, storage allocations or runtime checks in this file.

## Dependency and expansion relevance
Consumers include Trainer Tower dispatch, scripts, saved challenge/floor state, prize tables and e-Reader floor structures. Exact source investigations show source-level indexing risks when saved IDs are not locally range-checked before a table access, but this constants file alone proves **neither an exploit nor an invalid-state runtime path**. A future expanded editor must preserve distinction among overall challenge IDs, per-floor type, dispatch opcode, prize index and text index; do not widen or repurpose IDs without validating all consumers and save serialization.

## Evidence boundary / independent reviewer
- **Verified:** complete pinned file, Git blob, all numeric constants and comments.
- **Open:** complete consumer census and bounds proofs for saved challenge IDs, floor progress, prize/text selection, dispatcher, e-Reader records, compiled tables and runtime invalid-input tests.
- Reviewer identity/date/verdict: **not supplied**; approval **pending**. Do not count this analyst candidate as an approved disposition.

**Phase 1 FAIL_INCOMPLETE; 0/14,834 independently approved.**
