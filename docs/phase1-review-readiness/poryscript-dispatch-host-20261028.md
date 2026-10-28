# Phase 1 — source-extracted FireRed map-script dispatch (2026-10-28)

Partial subsystem evidence only; no whole-file semantic disposition or approval.

Pinned pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982:
src/script.c blob d0433bdda062b138e53d1a1d3184b4566ad7d9dc,
include/constants/map_scripts.h blob 1353de360cf1e00b6efbb26ec59c4822c99b59bf,
include/constants/quest_log.h blob fe284ba133ccc28053515c501979741b3960212f.

The independent host-C experiment extracts unchanged pinned C bodies for
MapHeaderRunScriptType, five RunOn*MapScript wrappers,
TryRunOnFrameMapScript and TryRunOnWarpIntoMapScript. Exact source
constants are pinned and extracted. Controlled lookup/execution stubs
observe sixteen cases: each wrapper with and without a script; last-playback
frame suppression; unmatched/matched frame table; ordinary playback
distinction; and unmatched/matched warp-table immediate execution.

Eleven source semantic mutations and four output mutations must fail closed.
The result is text-only CI evidence on the exact draft-branch head.

Dependency closure: actual Poryscript CLI table producer (prior green);
GNU ARM table bytes/relocations (prior green); pinned FireRed table reader
(previous host-C green); new dispatch consumers of reader returns.
Unresolved: mGBA instruction execution of the emitted table, malformed
native pointer safety, stock gameplay reachability of Dive Warp wrapper,
and independent complete-file review. Gate FAIL_INCOMPLETE.
