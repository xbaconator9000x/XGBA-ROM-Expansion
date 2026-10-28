# Phase 1 — Trainer Tower physical sectors to mGBA Flash bank mapping (2026-10-29)

Status: SOURCE-ONLY, FAIL_INCOMPLETE, independent approvals 0/14,834.

Pinned FireRed ce6406d8c2eaf46d543c8a2606de0c3cb1951982, include/save.h blob 87fb9b615b434b58823d15688056695acda9feab and src/cereader_tool.c blob 395be0bcbed8454e645a9f5670cde3024eda508e. Pinned mGBA fd9dc5c2cbf234365068855851107e762fc6211b, src/gba/savedata.c blob fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb and savedata.h blob 6227be25e8c9d2c1cc14c06ded34389b96138577.

Reuse original FireRed Flash wrappers, existing mGBA Flash state machine, and original agbcc/GNU ARM. Do not create a replacement Flash emulator. Minimal next extension is test-only mGBA debugger/core instrumentation and controlled Flash command transactions.

FireRed assigns Trainer Tower sectors 30 and 31 in a 32-sector 1Mbit Flash layout. mGBA Flash bank switch maps bank N to data + (N << 16), sector erase uses 0x1000 bytes and the selected currentBank. Thus sector 30 is bank 1 local sector 14, file offset 0x1E000; sector 31 is bank 1 local sector 15, file offset 0x1F000. The source checker verifies both FireRed call sites, bank command dispatch, selected-bank addressing, erase width and eleven fail-closed mutations.

This is arithmetic from pinned source, NOT actual agbcc ARM/mGBA instruction execution, physical Flash, power-loss durability, two-sector atomicity, or stock Trainer Tower gameplay reachability. The existing host fake-sector mixed-generation tests remain separate. mGBA savedata.c is MPL-2.0; FireRed code and game assets need independent licensing review.

Next: trace original FireRed Flash bank-select and sector erase/program commands into actual pinned mGBA core with native ARM execution, capture bank, address, Flash state, sector hashes, partial second-write and retry, and verify stock ReadTrainerTowerAndValidate remains FALSE. Preserve positive/negative controls and do not infer physical Flash behaviour. Partial-file dossier only; all gates FAIL_INCOMPLETE.
