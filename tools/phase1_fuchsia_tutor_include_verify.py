#!/usr/bin/env python3
"""Fail-closed original FireRed Fuchsia Substitute Tutor static include closure, not runtime/approval."""
import copy, hashlib, json, urllib.request
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]/"docs/phase1-review-readiness"
D=BASE/"fuchsia-tutor-static-include-closure-20261030.json"
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
def blob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def get(path):
 req=urllib.request.Request(f"https://raw.githubusercontent.com/pret/pokefirered/{PIN}/{path}",headers={"User-Agent":"xgba-phase1-source-closure"})
 with urllib.request.urlopen(req,timeout=45) as f:return f.read()
def check(d,src):
 assert d["source_revision"]==PIN and d["source_repository"]=="pret/pokefirered"
 assert d["scope"]=="PINNED_ORIGINAL_SOURCE_STATIC_INCLUDE_AND_LABEL_CLOSURE_ONLY"
 assert d["whole_file_semantic_coverage"] is False and d["independent_reviewer"] is None and d["independent_verdict"]=="NEEDS_REVIEW"
 assert d["independent_p0_approved"]==d["independent_total_approved"]==0 and d["gate"]=="FAIL_INCOMPLETE"
 assert d["license_status"]=="PENDING_INDEPENDENT_ORIGINAL_ASSET_AND_DERIVATIVE_LICENSING"
 assert len(d["source_findings"])==4 and len(d["unresolved"])>=4
 assert [f["path"] for f in d["files"]]==["data/maps/FuchsiaCity/map.json","data/maps/FuchsiaCity/scripts.inc","data/scripts/move_tutors.inc","data/event_scripts.s"]
 for f in d["files"]:
  raw=src[f["path"]]
  assert blob(raw)==f["blob"]
  lines=raw.decode("utf-8").splitlines()
  assert lines[f["line"]-1]==f["anchor"]
 for f in (d["additional_include"],d["tutor_flag_line"]):
  lines=src[f["path"]].decode("utf-8").splitlines()
  assert lines[f["line"]-1]==f["anchor"]
 m=json.loads(src["data/maps/FuchsiaCity/map.json"])
 assert any(x.get("script")=="FuchsiaCity_EventScript_SubstituteTutor" for x in m["object_events"])
 local=src["data/maps/FuchsiaCity/scripts.inc"]
 tutor=src["data/scripts/move_tutors.inc"]
 asm=src["data/event_scripts.s"]
 assert b"FuchsiaCity_EventScript_SubstituteTutor::" not in local
 assert b"FuchsiaCity_EventScript_SubstituteTutor::" in tutor
 assert b"FLAG_TUTOR_SUBSTITUTE" in tutor
 assert b'.include "data/maps/FuchsiaCity/scripts.inc"' in asm
 assert b'.include "data/scripts/move_tutors.inc"' in asm
def reject(d,src):
 try:check(d,src)
 except (AssertionError,KeyError,TypeError,IndexError,UnicodeDecodeError,ValueError):return
 raise AssertionError("FORGED_STATIC_CLOSURE_ACCEPTED")
def main():
 d=json.loads(D.read_bytes())
 src={f["path"]:get(f["path"]) for f in d["files"]}
 check(d,src)
 negatives=0
 for f in d["files"]:
  bad=dict(src);bad[f["path"]]=src[f["path"]]+b" "
  reject(d,bad);negatives+=1
  bad=copy.deepcopy(d);bad["files"][d["files"].index(f)]["blob"]="0"*40
  reject(bad,src);negatives+=1
  bad=copy.deepcopy(d);bad["files"][d["files"].index(f)]["line"]+=1
  reject(bad,src);negatives+=1
 for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","fabricated"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("scope","COMPILED_STOCK_GAMEPLAY"),("gate","PASS"),("source_findings",[]),("unresolved",[]),("independent_p0_approved",1),("source_revision","0"*40)):
  bad=copy.deepcopy(d);bad[field]=value;reject(bad,src);negatives+=1
 for field in ("additional_include","tutor_flag_line"):
  bad=copy.deepcopy(d);bad[field]["line"]+=1;reject(bad,src);negatives+=1
 assert negatives==24,negatives
 print("P0_FUCHSIA_TUTOR_STATIC_PASS original_blobs=4 include_edges=2 negatives=24 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
