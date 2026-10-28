# Poryscript map-script ABI — original-agbcc linked reader boundary (2026-10-28)

**PENDING EXACT-HEAD CI; FAIL_INCOMPLETE; independent approvals 0.**

This is a separate compiled-boundary investigation from the already green pinned Poryscript CLI/GNU ARM table fixture and the nine host-C execution cases. It builds unchanged `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982` (`src/script.c` blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`) using original `pret/agbcc@da598c1d918402c42c0c0d7128ba14567f3175e9` and checks the actual linked `MapHeaderGetScriptTable` and `MapHeaderCheckScriptTable` function symbols and their disassembly. The runner requires real ROM-addressed text symbols, load/branch instructions and seven fail-closed disassembly mutations. The ELF SHA-256, source identities and function instruction summaries are archived, never the ROM or ELF.

**Scope:** These are compiled linked reader witnesses, not executed ARM instructions, malformed pointer safety, or mGBA runtime consumption. The prior host pointer guard was a test shim, not native protection. Compiler inlining, missing symbols or unexpected instruction lowering must be investigated rather than silently treated as success. Reviewer should inspect full caller graph, link-table relocation, unaligned table byte reads, and actual emulator behavior before any semantic approval. Phase 2 remains untouched.
