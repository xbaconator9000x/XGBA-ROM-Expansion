# Analyst whole-file candidate 0049 — FireRed script context public ABI

**ANALYST-PREPARED ONLY; independent review pending.** Pinned source: [pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script.h](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script.h), Git blob SHA-1 `ce10c87266a8019eeefaaf787f43b291e7a58624`. Inspected complete **78-line** header (79 split lines including final newline).

## Complete-file semantic disposition

| Lines | Role |
| --- | --- |
| 1–6 | Include guard, `global.h`, forward declaration |
| 7–8 | `ScrCmdFunc` is a `bool8 (*)(ScriptContext *)` function pointer; `Script` is a byte array |
| 10–21 | Context fields: three one-byte flags (`stackDepth`, `mode`, `comparisonResult`), native callback, script byte pointer, 20-element return-pointer stack, handler table start/end pointers, four 32-bit data slots |
| 23 | `ScriptReadByte(ctx)` reads and increments script pointer without a local length check |
| 25–58 | Interpreter, context, field control, map-script, RAM-script and quest-log API declarations |
| 60–75 | Remaining UI/signpost state API declarations |
| 77–78 | Extern RAM-script return pointer and walkaway timer; guard closes |

This file declares an ABI but does not define storage, execution, serialization or compiled layout. Pointer size, alignment, structure field order, handler signature and stack size must be preserved or translated explicitly. **20 declared return slots does not mean 20 usable nested calls**: pinned [`src/script.c`](0048-firered-script-interpreter-runtime.md) rejects the twentieth push through its `stackDepth + 1 >= ARRAY_COUNT` check.

## Dependencies and unresolved checks

Pinned [`src/script.c`](0048-firered-script-interpreter-runtime.md) implements the interface, and [`data/script_cmd_table.inc`](0047-firered-script-command-dispatch-table.md) supplies the numeric handler mapping. `global.h` supplies the underlying types. Pending: `sizeof`/`offsetof` and assembly consumers in both compiler variants, malformed bytecode, native callback lifetime, save/emulator interoperability, source dependency closure and authenticated independent review. **Phase 1 FAIL_INCOMPLETE.**
