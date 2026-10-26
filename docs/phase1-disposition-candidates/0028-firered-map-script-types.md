# Phase 1 whole-file analyst candidate — FireRed map-script constants

**PENDING INDEPENDENT REVIEW; NOT APPROVED.** `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `include/constants/map_scripts.h`, verified Git blob `1353de360cf1e00b6efbb26ec59c4822c99b59bf`. [Pinned source](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/constants/map_scripts.h).

## Complete file semantics
The entire file is a guarded preprocessor constant header, with no functions, storage, executable definitions or pointer types. Guard: `GUARD_CONSTANTS_MAP_SCRIPTS_H`. It assigns seven consecutive nonzero map-script event types: `MAP_SCRIPT_ON_LOAD=1`, `ON_FRAME_TABLE=2`, `ON_TRANSITION=3`, `ON_WARP_INTO_MAP_TABLE=4`, `ON_RESUME=5`, `ON_DIVE_WARP=6` (**explicitly commented unused**), and `ON_RETURN_TO_FIELD=7`. No type 0 or sentinel value is declared in this file. The header does not prescribe table termination, trigger ordering or runtime dispatch.

## Cross-file and expansion obligations
The pinned `asm/macros/map.inc` `map_script` macro writes the type as a single byte, followed by a four-byte script pointer; `map_script_2` writes two 16-bit comparison fields and a 32-bit pointer. This header defines only type IDs; do not infer that all seven are reachable or that script pointers may be widened without modifying compiled consumers. Review the mapjson producer, dispatch switch, table termination and editor representation, including the unused type 6, for every supported build variant.

## Outstanding verification
Pinned blob and complete content verified; no exhaustive consumer search, compiled binary comparison, runtime trigger coverage or independent reviewer verdict. Reviewer: **none**; status **pending**; gate **0 credit / FAIL_INCOMPLETE**.
