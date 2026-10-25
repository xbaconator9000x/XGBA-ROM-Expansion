# Phase 1 v2.2 — source-backed field-script pointer roles

**Pinned source:** `pret/pokefirered` commit `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`, `src/scrcmd.c` Git blob `97b695ee2f6fca80a3b78f52f6a444f696fe5814`.

**Passing audited pipeline:** [run 40184922277](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40184922277). Evidence: `audit-output/field_pointer_role_contracts.csv.gz` and `field_pointer_role_summary.json`. **19 individual command handler roles, 21 source-verified 32-bit operand reads.**

## Why a 32-bit word cannot be automatically promoted to an XGBA handle

The same `ScriptReadWord(ctx)` ABI appears in code with incompatible pointer uses:

| Role | Source examples | ABI requirement |
| --- | --- | --- |
| Raw **writable byte address** | [`ScrCmd_setptr`, `ScrCmd_setptrbyte`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L300-L318) | A native memory address; writes directly through `u8 *`. Never reinterpret a sidecar resource ID as a writable pointer. |
| Raw **readable byte address** | [`loadbytefromptr`, compare-pointer commands](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L293-L298) | Dereferences byte memory immediately; requires native or explicitly bounded virtual-memory semantics. |
| Raw **memory copy** | [`ScrCmd_copybyte`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L329-L334) | Both destination and source are actual addresses; cannot assume either is a resource handle. |
| **Native function pointer** | [`callnative` and `gotonative`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L92-L125) | Two different C callback signatures: `void(void)` direct call and `bool8(void)` scheduled via `SetupNativeScript`. Neither accepts an arbitrary tag. |
| **Field script target pointer** | [`goto`, `call`, conditional variants](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L133-L169) | Script call/return stack and PC role, not raw writable data. Explicit extension negotiation and pointer lifetime required. |
| **Relocated or virtual script target** | [`setvaddress`, `vgoto`, `vcall`, conditional variants](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L171-L210) | `sAddressOffset` rebases script-address operands relative to the current bytecode pointer. External resources cannot silently bypass it. |

The audit stores source-line boundaries, source-section SHA-256, opcode ID, typed role and role-specific required source expressions for all **19** command handlers. Of those, **nine** have script/control/virtual-address roles, **two** are native function-pointer operations, and **eight** explicitly read or write byte memory (three with writable destinations). Code is reviewed to the described role; deeper side effects and runtime pointer validity remain unverified.

## Expansion compatibility consequence

**Contract XS22-TYPED-32BIT-OPERANDS:** Attach opcode- and operand-position-specific metadata to the expansion relocation schema. A new external resource identifier must never masquerade as an ordinary C callback or byte-memory pointer, and must never override a vanilla script's virtual offset semantics. Preserve all 32-bit legacy opcodes and handler widths by default; implement tagged resources through explicit opt-in version negotiation and type-safe runtime dispatch.

**Important nuance:** These 19 role descriptions are verified *source-level semantic findings*, **not 19 signed-off whole-file dispositions**, proof that every helper it calls is side-effect free, or proof of viable external-resource execution.

Related: [Legacy NOP padding and six no-consume dummy opcodes](LEGACY_NOP_SCRIPT_ABI_v22.md), [original 461 opcode assembler ABI](SCRIPT_ASSEMBLER_ABI_v21.md), [CPU memory and bank-window compatibility](SEMANTIC_DEPENDENCIES_v16.md).

**Phase 1 whole-file gate remains FAIL_INCOMPLETE.**
