#!/usr/bin/env python3
"""Verify R39 replay anchors against the pinned original Emerald implementation.

The test does NOT claim that the host sandbox replays all real ROM-hack events.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import xgba_r37_script_graph as r37
import xgba_r39_script_sandbox as r39

PIN = "731ad5bfd6e6f265508d0efcca0ba42f9dcf5881"
ANCHORS = {
    "ScrCmd_setvar": "*ptr = ScriptReadHalfword(ctx);",
    "ScrCmd_addvar": "*ptr += ScriptReadHalfword(ctx);",
    "ScrCmd_subvar": "*ptr -= VarGet(ScriptReadHalfword(ctx));",
    "ScrCmd_copyvar": "*ptr = *GetVarPointer(ScriptReadHalfword(ctx));",
    "ScrCmd_setorcopyvar": "*ptr = VarGet(ScriptReadHalfword(ctx));",
    "ScrCmd_checkflag": "ctx->comparisonResult = FlagGet(ScriptReadHalfword(ctx));",
    "ScrCmd_additem": "gSpecialVar_Result = AddBagItem(itemId, (u8)quantity);",
    "ScrCmd_removeitem": "gSpecialVar_Result = RemoveBagItem(itemId, (u8)quantity);",
    "ScrCmd_checkitemspace": "gSpecialVar_Result = CheckBagHasSpace(itemId, (u8)quantity);",
    "ScrCmd_checkitem": "gSpecialVar_Result = CheckBagHasItem(itemId, (u8)quantity);",
    "ScrCmd_checktrainerflag": "ctx->comparisonResult = HasTrainerBeenFought(index);",
    "ScrCmd_settrainerflag": "SetTrainerFlag(index);",
    "ScrCmd_cleartrainerflag": "ClearTrainerFlag(index);",
    "ScrCmd_return": "ScriptReturn(ctx);",
    "ScrCmd_goto": "ScriptJump(ctx, ptr);",
    "ScrCmd_call": "ScriptCall(ctx, ptr);",
}


def verify(root):
    src = (root/"src"/"scrcmd.c").read_text()
    operators = (root/"include"/"constants"/"comparison_operators.h").read_text()
    table = ("{1, 0, 0}","{0, 1, 0}","{0, 0, 1}",
             "{1, 1, 0}","{0, 1, 1}","{1, 0, 1}")
    assert len(r39.CONDITIONS) == len(table) == 6
    for i,values in enumerate(table):
        if values not in src:
            raise AssertionError("Pinned original Emerald comparison table changed")
        if tuple(x=="1" for x in values.strip("{}").split(", ")) != r39.CONDITIONS[i]:
            raise AssertionError("Script condition table does not match original")
    for key in ("LESS_THAN", "EQUAL", "GREATER_THAN",
                "LESS_THAN_OR_EQUAL", "GREATER_THAN_OR_EQUAL", "NOT_EQUAL"):
        if operators.count(key) < 1:
            raise AssertionError("Comparison ID missing from pinned engine: "+key)
    for key,fragment in ANCHORS.items():
        start = src.find("bool8 "+key+"(struct ScriptContext *ctx)")
        if start < 0 or fragment not in src[start:src.find("\n}",start)+2]:
            raise AssertionError("Emerald original command implementation mismatch: "+key)
    if not r39.OPERATIONS <= set(r37.SPECS):
        raise AssertionError("R39 includes opcodes not in R37 verified layout subset")
    if any(x in r39.OPERATIONS for x in (0x25,0x39,0x5c,0x67,0xff)):
        raise AssertionError("Native callback / warp / trainer battle mistakenly allowed")
    if r37.SPECS[0x16]["fmt"]!="HH" or r37.SPECS[0x29]["fmt"]!="H":
        raise AssertionError("Event var or flag operand width mismatch")
    print("PASS_R39_PINNED_ORIGINAL_EMERALD_SCRIPT_SEMANTICS commit="+PIN)
    return True


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    args=p.parse_args()
    if not verify(args.source):
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
