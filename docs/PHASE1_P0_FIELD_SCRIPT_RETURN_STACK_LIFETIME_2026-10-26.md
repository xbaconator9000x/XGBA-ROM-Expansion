# Phase 1 P0 — live field-script pointers, return-stack capacity and bank lifetime

**Date:** 2026-10-26. **Source revision:** `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.

**Status: source-interpreted pending independent whole-file review and compiled/emulated execution proof.** This is not XGBA implementation and does not amend `semantic_dispositions.csv.gz`.

## Exact pinned file identity

| File | Git blob SHA-1 | Semantically traced anchors |
| --- | --- | --- |
| [`include/script.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/script.h) | `ce10c87266a8019eeefaaf787f43b291e7a58624` | `ScriptContext.stack[20]`, `scriptPtr`, `stackDepth`, local `data[4]` |
| [`src/script.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c#L82-L200) | `d0433bdda062b138e53d1a1d3184b4566ad7d9dc` | `RunScriptCommand`, `ScriptPush`, `ScriptPop`, `ScriptCall`, `ScriptReturn`, `ScriptReadWord` |
| [`src/scrcmd.c`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L118-L256) | `97b695ee2f6fca80a3b78f52f6a444f696fe5814` | `ScrCmd_call`, `ScrCmd_call_if`, `ScrCmd_vcall`, `ScrCmd_vcall_if`, `ScrCmd_callstd`, `ScrCmd_callstd_if` |

## Observed execution semantics

1. The interpreter stores native addresses, not opaque resource IDs: `ctx->scriptPtr` is a live pointer; the return stack is `const u8 *stack[20]`; `ScriptReadWord` reads four little-endian operand bytes from `scriptPtr`.
2. **Off-by-one capacity rule:** `ScriptPush` rejects a push when `stackDepth + 1 >= ARRAY_COUNT(stack)`. From initial depth zero, that permits **19 successful nested push operations**, not 20. The 20th operation returns a failure code.
3. **Unchecked caller failure:** `ScriptCall` invokes `ScriptPush(ctx, ctx->scriptPtr);` and then assigns `ctx->scriptPtr = ptr;` **regardless of the push's return value**. Consequently, at maximum stack depth, a nested call can enter another script without saving its own return location. Subsequent return follows the previous frame's address instead. This is a source-derived control-flow consequence; no compiled-ROM overflow fixture has yet been executed.
4. `ScriptPop` returns NULL when the stack is empty; `ScriptReturn` assigns that NULL to `scriptPtr`. `RunScriptCommand` detects NULL on its next dispatch and stops. The handoff is non-throwing and does not preserve the attempted failed call location.
5. The six named native `ScrCmd_*` entrypoints route into the same `ScriptCall` operation, including rebased virtual addresses and standard-script table entries. Calling a standard script is therefore not exempt from the return-stack capacity rule.
6. `ScrCmd_waitstate`, `ScriptContext_Stop` and `ScriptContext_Enable` can suspend/resume the interpreter with `ctx->scriptPtr` and its return stack still live. A bank swap or sidecar unload while a script is suspended must not invalidate these addresses.

## XGBA compatibility and safety obligations

- **SCRIPT-STACK-001:** Maintain exact legacy interpretation and exception behaviour for unmodified games. An opt-in extension may introduce a new larger or safer stack only behind an explicitly versioned interpreter ABI; a larger physical resource file alone does nothing to the stack.
- **SCRIPT-PC-002:** Before remapping/unloading any resource bank, enumerate/pin the currently executing script PC, all live return addresses and any pending native callback or wait-state references. Defer bank changes until a safe point or translate through a versioned stable-handle trampoline. The GBA interpreter has no native garbage collector for these pointers.
- **SCRIPT-RET-003:** New extension interpreters should fail closed on stack exhaustion and preserve deterministic unwinding. Do not silently adopt the source's ignored push-failure behaviour if extending stack semantics.
- **SCRIPT-RELOC-004:** Classify scripts, rebased vaddresses, RAM byte read/write operands and ARM Thumb function pointers separately. These operands cannot be blindly rewritten into arbitrary 64-bit host-side offsets.
- **SCRIPT-SAVE-005:** Saved games and emulator savestates must bind suspended script/bank identity and return addresses to exact external bytes; reject missing/changed resource backing.

## Reproduction and review gate

`tools/field_script_stack_lifetime_semantics.py` pins all three Git blobs and the upstream commit, locates each named C function body, preserves exact source line ranges, checks ordered control flow and verifies all six `ScrCmd` caller paths. **Seven deliberate source mutations** must be rejected, including changing stack capacity, changing the push guard, adding an error check, losing the post-failure jump, replacing the opcode fetch or call target. Output: `firered-variant-evidence/field_script_stack_lifetime_contract.json`, attached to pinned classic/modern FireRed CI.

This supplements the existing `tools/field_pointer_role_contracts.py` typed 19-handler catalog and `tools/script_opcode_semantic_obligations.py` full opcode inventory. It is narrower in scope but includes a concrete *consumer liveness* dependency these lexical inventories do not themselves prove.

**Completion requires:** source-executed contract verifier PASS, compiled emulator fixture for deep calls, wait/resume and bank mutation, matched compiler/linker operands, and independently reviewed whole-file semantic dispositions. Until then this remains a strong **candidate semantic interpretation**, not signed-off architecture or a Phase 1 gate success.
