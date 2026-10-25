# Phase 1 v2.1 — original FireRed script bytecode emission ABI

**Pinned FireRed:** `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. **Completion:** incomplete; this is a source-backed assembler ABI map, not a guarantee of safe extended script execution.

## Verified source-to-handler registry

- [Original field bytecode macro file](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/asm/macros/event.inc), Git blob `142ad979d7d3093244087a247fa2b4883424f77f`.
- [Original battle bytecode macro file](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/asm/macros/battle_script.inc), Git blob `392a387e97adc84102a529f5a932db6745303b63`.
- [Field opcode handler registry](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/script_cmd_table.inc) 0x00–0xD4 (213 slots).
- [Battle opcode handler table](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/battle_script_commands.c#L312-L565) 0x00–0xF7 (248 slots).

[Passing assembler audit](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40182747042) identified 459 direct opcode-emitting macro variants across 457 distinct command slots, including 426 fixed literal width variants, 33 nontrivial variants, and 83 auxiliary macros without a direct opcode byte. Four command slots did not have separate direct literal macros because the assembler chooses between two opcodes *inside one conditional macro*.

[Passing resolved branch and handler audit](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40183416216) accounted for all four, giving **461/461 opcode slots with pinned assembler-source emission evidence**. Additionally the C read order and byte widths of all eight local/remote movement and object variants matched the assembler's emitted operand widths.

## Conditional map-scoped command widths

| Source macro | Local map | Explicit destination map | Handler operand widths (excluding opcode) |
| --- | --- | --- | --- |
| `applymovement` | 0x4F · 7 bytes | 0x50 · 9 bytes | 2+4 / 2+4+1+1 |
| `waitmovement` | 0x51 · 3 bytes | 0x52 · 5 bytes | 2 / 2+1+1 |
| `removeobject` | 0x53 · 3 bytes | 0x54 · 5 bytes | 2 / 2+1+1 |
| `addobject` | 0x55 · 3 bytes | 0x56 · 5 bytes | 2 / 2+1+1 |

The assembler's [`map` helper macro](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/asm/macros/map.inc#L4-L7) (Git blob `83ef472c926ce767c9133ab9bd6922280b38bb2d`) emits *map group first*, then *map number*, each as one byte. [The original C interpreter handlers](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L983-L1072) (Git blob `97b695ee2f6fca80a3b78f52f6a444f696fe5814`) read the same bytes in that order. For movement, the 4-byte argument is a **movement-script pointer**, not a general integer.

## XGBA script and plugin obligations

1. Version and preserve the **opcode number and encoded operand byte width** exactly for existing scripts. A generic single width for an opcode family is unsafe.
2. A 32-bit operand is not automatically a relocatable external resource. Field scripts can contain writable RAM addresses, native callbacks, movement bytecode, ordinary jumps, string pointers and other distinct roles.
3. The field-script interpreter and battle-script interpreter have different command tables and runtime pointer lifetimes.
4. The emitted layouts cover all 461 slots, but **33 macro variants remain nontrivial**, and **461 handler side-effect paths are not fully semantically approved**. Macro emission source evidence must be reconciled with each handler's branch-dependent cursor and pointer use before compatibility signoff.
5. A future plugin should compare pinned macro/handler Git hashes between upstream versions and withhold automatic opcode remapping when either changes.

**Generated evidence files:** `script_assembler_opcode_schema.csv.gz`, `script_assembler_operand_variants.jsonl.gz`, `script_conditional_opcode_variants.csv.gz`, `script_conditional_opcode_summary.json`, `script_opcode_semantic_obligations.csv.gz`.

**All 461 assembler slots are source-accounted; Phase 1 remains FAIL_INCOMPLETE.**
