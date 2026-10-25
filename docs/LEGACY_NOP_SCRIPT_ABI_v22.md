# XGBA Phase 1 v2.2 — legacy field bytecode no-op compatibility

**Pinned FireRed revision:** `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.

## Critical source-verified behavior

The native [field opcode table](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/script_cmd_table.inc#L3-L5) (Git blob `c5d112d9ea66d258d5a372dda89b9ad96ed2b1e1`) maps **opcode 0x00 → `ScrCmd_nop`**. [Interpreter byte dispatch](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c#L115-L130) (blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`) advances the script pointer for each opcode byte. [`ScrCmd_nop`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L76-L79) simply returns FALSE without consuming an operand.

[Source macro `hidemoneybox`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/asm/macros/event.inc#L1197-L1202) (blob `142ad979d7d3093244087a247fa2b4883424f77f`) expands to three bytes:

```asm
.byte 0x94
.byte 0
.byte 0
```

Yet [the C handler](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L1839-L1846) has its two ScriptReadByte calls **commented out** and calls HideMoneyBox without advancing the bytecode cursor. The following zero bytes are therefore valid ordinary NOP opcodes during the next two interpreter steps. Their order is **not** a general three-byte operand schema that can be skipped by every new interpreter.

The pinned source audit `tools/legacy_dummy_opcode_semantics.py` verifies all these source blobs, the byte-0 dispatch, all six legacy commands with emitted but unconsumed operands, and checked-in script invocation sites:

| Command macro | Opcode | Unconsumed operand bytes | Direct checked-in script invocations |
| --- | --- | ---: | ---: |
| `initclock` | 0x2C | 4 | 0 |
| `drawboxtext` | 0x74 | 4 | 0 |
| `setberrytree` | 0x8A | 3 | 0 |
| `hidemoneybox` | 0x94 | 2 **literal zeros** | **19** |
| `getpokenewsactive` | 0x96 | 2 | 0 |
| `addelevmenuitem` | 0xB1 | 7 | 0 |

The 19 invocations include [Celadon Game Corner scripts](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/maps/CeladonCity_GameCorner/scripts.inc#L73), [Cerulean Bike Shop](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/maps/CeruleanCity_BikeShop/scripts.inc#L27) and [Fuchsia Safari Zone entrance](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/data/maps/FuchsiaCity_SafariZone_Entrance/scripts.inc#L126). Every instance is source-file hash pinned in `audit-output/legacy_dummy_opcode_source_semantics.json`.

## ABI requirements

1. **Never repurpose 0x00** as an unconditional XGBA extension escape or handle prefix in legacy field scripts: the game contains intentional ordinary NOP bytes, including padded `hidemoneybox` macros.
2. Never assume assembler operand widths equal bytes actually consumed by a handler. In particular, a broad script-pointer `+= 2` compatibility “fix” after `hidemoneybox` is not vanilla behavior.
3. The five other legacy dummy handlers also have source-emitted parameters but no active ScriptRead calls. Their use in external scripts is **not automatically safe**; bytes other than 0x00 can be parsed as arbitrary following commands.
4. Keep extension selection explicit and negotiated (script language version, tagged metadata, or dedicated opcode namespace validated by the loader), preserving the existing 213 field-script command slots unchanged.
5. Distinguish source-verified interpreter flow from emulator runtime proof. The 19 usage sites were identified in source; instrumented execution tests remain a later compatibility requirement.

## Correction to the prior automated audit

- The macro `stringvar` (event.inc:1028–1038) is **a one-byte conditional string-buffer index encoder**, not an alternative opcode-zero command. Its initial `.byte 0` is not an independently dispatched field-script opcode.
- The `drawbox` handler (scrcmd.c:1464–1473) has ScriptRead calls entirely inside a C block comment. Those reads do not execute. Excluding comments from source analysis removed this false operand mismatch.
- Five additional source-authentic mismatches then became visible because their entire body argument consumption had been commented out or dummied out; this audit intentionally preserves them as distinct legacy ABI concerns.

**Status:** these specific source facts are verified in GitHub Actions; whole-file Phase 1 signoff remains **FAIL_INCOMPLETE**.
