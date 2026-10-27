# Phase 1 whole-file analyst candidate — FireRed background-event constants

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** Pinned `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, path `include/constants/event_bg.h`, verified Git blob `64f3331b86082e31455ec3354175cedf02f6200e`. [Pinned source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/constants/event_bg.h).

## Whole-file inventory
This is a single guarded C preprocessor header (`GUARD_CONSTANTS_EVENT_BG_H`), containing exactly seven integer definitions, no declarations, functions or executable storage. Facing-direction values are `BG_EVENT_PLAYER_FACING_ANY=0`, `NORTH=1`, `SOUTH=2`, `EAST=3`, `WEST=4`; event kinds `BG_EVENT_HIDDEN_ITEM=7` and `BG_EVENT_SECRET_BASE=8`. Values 5 and 6 are **not defined in this file**; that is not evidence they are unused elsewhere.

## ABI and interoperability
The pinned `asm/macros/map.inc` `bg_event` emits the kind as one byte and selects a distinct 4-byte payload representation when kind equals `BG_EVENT_HIDDEN_ITEM`. `bg_sign_event` passes a facing-direction constant as that kind. `bg_secret_base_event` passes kind 8 and is documented unused in FRLG by the macro source. The header itself neither validates a direction nor establishes runtime handling, which depends on the native background-event consumer and generator. Importers must preserve numeric values and the hidden-item union's byte layout, rather than interpreting all 4-byte payloads as script pointers.

## Reviewer checklist
Verify all consumers and build variants, C struct union interpretation, mapjson generation and editor source preservation, including invalid/reserved values and hidden-item payload overflow. Confirm whether secret-base values are unreachable instead of relying on the comment alone. Exact source and hash verified; compiler, emulator, round-trip and independent review **not completed**. Reviewer **none**; gate contribution **0 / FAIL_INCOMPLETE**.
