#!/usr/bin/env python3
"""Source-only stock Trainer Tower lobby script -> original FALSE stub closure.
No natural mGBA gameplay execution, external e-Reader acceptance, or approval.
"""
import argparse,hashlib,json,subprocess
from pathlib import Path
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={
 "data/maps/TrainerTower_Lobby/scripts.inc":"b2543ec3f7fe3481bb43ebe3bf783e33b668c9c5",
 "asm/macros/trainer_tower.inc":"94d9efe775658c7865d74f8819b9c5bfb74db893",
 "data/specials.inc":"d880bf6b9dc9fd765f0b85e6d698411e3da81d5d",
 "src/trainer_tower.c":"732b3f2ed31ed95d6476b9e111d53f759c448d81",
 "src/cereader_tool.c":"395be0bcbed8454e645a9f5670cde3024eda508e"}
ANCHORS={
 "lobby_choice":("data/maps/TrainerTower_Lobby/scripts.inc",[
 "TrainerTower_Lobby_EventScript_ChooseChallenge::",
 "case 0, TrainerTower_Lobby_EventScript_BeginChallenge",
 "case 3, TrainerTower_Lobby_EventScript_BeginChallenge",
 "TrainerTower_Lobby_EventScript_BeginChallenge::",
 "copyvar VAR_0x8005, VAR_RESULT",
 "ttower_startchallenge"]),
 "macro":("asm/macros/trainer_tower.inc",[
 ".macro ttower_startchallenge",
 "setvar VAR_0x8004, TRAINER_TOWER_FUNC_START_CHALLENGE",
 "special CallTrainerTowerFunc"]),
 "special":("data/specials.inc",["def_special CallTrainerTowerFunc"]),
 "dispatcher":("src/trainer_tower.c",[
 "[TRAINER_TOWER_FUNC_START_CHALLENGE]        = StartTrainerTowerChallenge",
 "void CallTrainerTowerFunc(void)",
 "SetUpTrainerTowerDataStruct();",
 "sTrainerTowerFunctions[gSpecialVar_0x8004]();",
 "FreeTrainerTowerDataStruct();"]),
 "setup":("src/trainer_tower.c",[
 "static void SetUpTrainerTowerDataStruct(void)\n{",
 "if (ReadTrainerTowerAndValidate() == TRUE)",
 "CEReaderTool_LoadTrainerTower(&sTrainerTowerState->data);",
 "const struct EReaderTrainerTowerSetSubstruct * header_p = &gTrainerTowerLocalHeader;"]),
 "challenge":("src/trainer_tower.c",[
 "static void StartTrainerTowerChallenge(void)\n{",
 "if (!ReadTrainerTowerAndValidate())",
 "TRAINER_TOWER.validated = TRUE;",
 "TRAINER_TOWER.validated = FALSE;"]),
 "stub":("src/cereader_tool.c",[
 "bool32 ReadTrainerTowerAndValidate(void)\n{",
 "return FALSE;"])
}
def need(ok,why):
 if not ok: raise ValueError(why)
SCOPE={
 "lobby_choice":("TrainerTower_Lobby_EventScript_ChooseChallenge::","TrainerTower_Lobby_EventScript_DeclineChallenge::"),
 "macro":(".macro ttower_startchallenge",".endm"),
 "dispatcher":("static void (*const sTrainerTowerFunctions[])(void) = {","void GetTrainerTowerOpponentName(u8 *dest)"),
 "setup":("static void SetUpTrainerTowerDataStruct(void)\n{","static void FreeTrainerTowerDataStruct(void)\n{"),
 "challenge":("static void StartTrainerTowerChallenge(void)\n{","static void GetOwnerState(void)\n{"),
 "stub":("bool32 ReadTrainerTowerAndValidate(void)\n{",None)
}
def region(s,label):
 if label not in SCOPE:return (0,len(s))
 start,end=SCOPE[label]
 i=s.find(start)
 need(i>=0,"missing source scope "+label)
 j=s.find(end,i+len(start)) if end else len(s)
 need(j>i,"missing end scope "+label)
 if label=="macro":j+=len(end)
 return (i,j)
def check(s):
 for label,(path,anchors) in ANCHORS.items():
  i,j=region(s[path],label)
  fragment=s[path][i:j]
  positions=[fragment.find(x) for x in anchors]
  need(all(k>=0 for k in positions),"missing scoped anchor "+label)
  need(positions==sorted(positions),"source ordering drift "+label)
  if label=="stub":
   need(fragment.split("}",1)[0].count("return FALSE;")==1,"stub FALSE changed")
 need(s["data/maps/TrainerTower_Lobby/scripts.inc"].count("ttower_startchallenge")==1,"lobby macro count")
 return True
def negatives(s):
 n=0
 for label,(path,anchors) in ANCHORS.items():
  for anchor in anchors:
   changed=dict(s)
   i,j=region(s[path],label)
   frag=s[path][i:j]
   need(anchor in frag,"ineffective scoped mutation")
   changed[path]=s[path][:i]+frag.replace(anchor,"PHASE1_NEGATIVE",1)+s[path][j:]
   need(changed[path]!=s[path],"ineffective negative")
   try: check(changed)
   except ValueError: n+=1
   else: raise AssertionError("escaped "+label+" "+anchor)
 return n
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--firered",type=Path,required=True)
 p.add_argument("--output",type=Path,required=True)
 a=p.parse_args()
 def git(*args):return subprocess.check_output(["git","-C",str(a.firered),*args],text=True).strip()
 need(git("rev-parse","HEAD")==PIN,"pinned revision")
 for path,sha in BLOBS.items():need(git("hash-object",path)==sha,"blob drift "+path)
 s={path:(a.firered/path).read_text() for path in BLOBS}
 check(s);n=negatives(s)
 out={"evidence_class":"PINNED_TRAINER_TOWER_STOCK_SCRIPT_SOURCE_ONLY",
      "pin":PIN,"blobs":BLOBS,
      "source_mutations_rejected":n,
      "script_to_dispatcher_to_false_stub_source_reachable":True,
      "actual_gameplay_reachability_executed":False,
      "external_e_reader_data_reachable":False,
      "native_arm_sector_transaction_in_this_test":False,
      "phase1_gate":"FAIL_INCOMPLETE","independent_approvals":0}
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
 print("TRAINER_TOWER_STOCK_SCRIPT_SOURCE_PASS negatives=%d gate=FAIL_INCOMPLETE approvals=0"%n)
if __name__=="__main__":main()
