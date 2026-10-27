# Analyst whole-file candidate 0047 — FireRed script command dispatch table

**ANALYST-PREPARED ONLY; independent review pending.** Pinned source: [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/script_cmd_table.inc](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/script_cmd_table.inc), Git blob SHA-1 `c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1`. Inspected all **219 authored lines** (220 split lines including trailing newline).

## Complete-file semantic disposition

| Source lines | Role |
| --- | --- |
| 1–3 | `.align 2` and the `gScriptCmdTable::` global label |
| 4–67 | One 32-bit `ScrCmd_*` handler pointer per opcode, contiguous from `0x00` through `0x3f`: control flow, locals, comparison, audio and warps |
| 68–107 | Opcode `0x40` points to `ScrCmd_setdivewarp`, `0x41` to `ScrCmd_setholewarp`; later slots include object, movement, trainer and message handlers |
| 108–165 | Dialog, item, party, field-effect and weather handler entries, with numeric slot comments |
| 166–216 | Remaining commands include `0xa2` setmetatile, `0xa7` setmaplayoutindex and final `0xd4` bufferitemnameplural |
| 217–219 | Blank separator; `gScriptCmdTableEnd::` label; extra `.4byte ScrCmd_nop` placed **after** the end label |

The table contains **213 consecutive valid entries** (`0x00`–`0xd4`), each a 4-byte pointer: **852 source-level table bytes** before the exclusive-end label, plus one extra 4-byte nop pointer outside the indexed table. The table defines **bytecode command opcodes**, not map-header script *type* tags: opcode `0x40` and map-script type `6` belong to separate namespaces.

## Consumers, dependencies and open checks

Pinned [`src/script.c`](0048-firered-script-interpreter-runtime.md) reads a command byte, computes a command-table pointer and rejects a pointer at or beyond `cmdTableEnd` before invoking the handler. The pinned [event assembler macros](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/asm/macros/event.inc) emit matching opcodes. [`include/script.h`](0049-firered-script-context-abi-header.md) defines the handler signature and context pointers. Full `ScrCmd_*` implementation linkage, conditional build variants, compiled symbol addresses, malformed bytecode, pointer-arithmetic bounds, Poryscript emission and runtime execution remain to be independently verified. No compiled or runtime approval is implied. **Phase 1 FAIL_INCOMPLETE.**
