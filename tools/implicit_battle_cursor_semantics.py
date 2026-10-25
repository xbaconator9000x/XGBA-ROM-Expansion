#!/usr/bin/env python3
"""Explain eight apparently cursor-inactive battle opcodes through helper semantics.

Does NOT declare full operand/side-effect safety. Distinguishes delegated
SetMoveEffect dispatch, script stack pop, and action/selection completion.
All assertions are pinned to exact source blobs and syntactic handler bodies.
"""
import csv,gzip,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered")
OUT=Path("audit-output")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
EXPECTED={
 "src/battle_script_commands.c":"67f90a37044db87091b2174f78fe1e31ad2ef10d",
 "src/battle_util.c":"bb66a0144b6144a72e1d9b22321c541e22302f7e"}
CHECKS={
 "Cmd_seteffectprimary":("DELEGATES_SET_MOVE_EFFECT","SetMoveEffect(TRUE, 0);"),
 "Cmd_seteffectsecondary":("DELEGATES_SET_MOVE_EFFECT","SetMoveEffect(FALSE, 0);"),
 "Cmd_return":("STACK_PC_RESTORE","BattleScriptPop();"),
 "Cmd_end":("END_ACTION_STATE","gCurrentActionFuncId = B_ACTION_TRY_FINISH;"),
 "Cmd_end2":("END_ACTION_STATE","gCurrentActionFuncId = B_ACTION_TRY_FINISH;"),
 "Cmd_endselectionscript":("SELECTION_FLAG_COMPLETE","gBattleStruct->selectionScriptFinished"),
 "Cmd_finishaction":("END_ACTION_STATE","gCurrentActionFuncId = B_ACTION_FINISHED;"),
 "Cmd_finishturn":("END_TURN_STATE","gCurrentTurnActionNumber = gBattlersCount;")}
def sha(b):return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:raise RuntimeError("Wrong commit")
 raw={}
 for path,dig in EXPECTED.items():
  b=(ROOT/path).read_bytes()
  if sha(b)!=dig:raise RuntimeError("Source hash mismatch "+path)
  raw[path]=b.decode("utf-8","surrogateescape")
 src=raw["src/battle_script_commands.c"]
 util=raw["src/battle_util.c"]
 if not re.search(r"#define INCREMENT_RETURN[\s\S]{0,300}gBattlescriptCurrInstr\+\+;[\s\S]{0,100}return;",src):
  raise RuntimeError("Shared helper cursor increment macro changed")
 if not re.search(r"void SetMoveEffect\(bool8 primary, u8 certain\)[\s\S]{0,13000}\bINCREMENT_RETURN\b",src):
  raise RuntimeError("SetMoveEffect cursor exit policy unconfirmed")
 if not re.search(r"void BattleScriptPop\(void\)[\s\S]{0,180}gBattlescriptCurrInstr = ",util):
  raise RuntimeError("BattleScriptPop does not restore cursor")
 with gzip.open(OUT/"script_opcode_semantic_obligations.csv.gz","rt",newline="") as f:rows=list(csv.DictReader(f))
 observed={r["handler"]:r for r in rows if r["operand_schema_status"]=="BATTLE_CURSOR_ACCESS_UNRESOLVED"}
 if set(observed)!=set(CHECKS):raise RuntimeError("Unhandled cursor-implicit battle opcodes: "+str(sorted(set(observed)^set(CHECKS))))
 result=[]
 for name,(meaning,needle) in CHECKS.items():
  r=observed[name];start=int(r["definition_line"])
  lines=src.splitlines()
  segment="\n".join(lines[start-1:int(r["end_line"])])
  if needle not in segment:raise RuntimeError("Handler semantics changed "+name)
  result.append({"opcode":int(r["opcode"]),"handler":name,
    "source":"src/battle_script_commands.c","source_blob_sha":EXPECTED["src/battle_script_commands.c"],
    "definition_line":start,"semantic_class":meaning,
    "operand_cursor_action":"INDIRECT_OR_TERMINAL_CONFIRMED_BY_PINNED_SOURCE",
    "full_path_semantics_approved":False})
 report={"cursor_implicit_battle_handlers_explained":len(result),
         "expected_eight_explained":len(result)==8,
         "other_battle_opcodes_still_need_path_complete_review":248-len(result),
         "source_verified_exit_macro":True,"source_verified_BattleScriptPop":True,
         "semantic_file_approvals":0,"phase1_mapping_complete":False,
         "handlers":result,
         "limitations":["SetMoveEffect can dispatch effects, callbacks and battle scripts; not path-complete.",
           "Terminal action transitions are not equivalent to an ordinary script cursor advance.",
           "Individual helper calls need independent side-effect and stack-state review."]}
 (OUT/"script_implicit_cursor_semantics.json").write_text(json.dumps(report,indent=2)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k not in ("handlers","limitations")},indent=2))
if __name__=="__main__":main()
