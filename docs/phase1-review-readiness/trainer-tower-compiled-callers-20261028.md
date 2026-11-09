# Trainer Tower — original-agbcc linked caller boundary, 2026-10-28

**PENDING EXACT-HEAD CI; FAIL_INCOMPLETE; independent approvals 0.**

Immutable FireRed pin `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `src/trainer_tower.c` blob `732b3f2ed31ed95d6476b9e111d53f759c448d81`, `src/cereader_tool.c` blob `395be0bcbed8454e645a9f5670cde3024eda508e`, original agbcc `da598c1d918402c42c0c0d7128ba14567f3175e9`.

**Source closure.** `SetUpTrainerTowerDataStruct` checks `ReadTrainerTowerAndValidate() == TRUE` before invoking `CEReaderTool_LoadTrainerTower`, without checking the loader return; the false branch constructs local floors. `StartTrainerTowerChallenge` calls the same stub and assigns the validated flag accordingly. `CallTrainerTowerFunc` and `PrintTrainerTowerRecords` call setup, but actual gameplay reachability is not proved by these source edges.

**Compiled experiment.** Reuse the already-required original-agbcc FireRed ELF, independently confirm the linked stub still returns zero, and check one direct Thumb BL from each of the two linked caller functions to the exact same stub symbol address. Four source mutations and seven linked-disassembly mutations must fail. Archive only the JSON, immutable source identities and ELF SHA-256. If a static symbol is absent or inlined, report failure and inspect compiler evidence; do not relax the assertion without a justified alternative.

**Limits and reviewer questions.** A compiled callsite is not an executed callsite. This does not prove external e-Reader data reachable in stock gameplay, two-sector native Flash transaction atomicity, any extension build's semantics, or whole-file independent approval. Reviewer must independently reproduce ELF callsites, enumerate any additional callers and validate failure handling before considering a disposition. Prior host-C partial destination mutation remains separate green evidence, not repeated here.
