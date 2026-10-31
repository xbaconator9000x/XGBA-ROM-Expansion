#!/usr/bin/env python3
"""Fail-closed six source-only partial P0 handoffs, no approvals."""
import copy,hashlib,json,urllib.request
from pathlib import Path
from phase1_remaining_p0_eight_verify import git_blob,verify
ROOT=Path(__file__).resolve().parents[1]
SPEC=ROOT/"docs/phase1-review-readiness/remaining-p0-six-qt-go-libretro-20261029.json"
EXPECTED=[34,48,49,50,57,62]
LIC={"mgba-emu/mgba":["LICENSE","14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e","MPL-2.0 with separate permissive libretro.h header notice"],"huderlem/porymap":["LICENSE.md","65c5ca88a67c30becee01c5a8816d964b03862f9","LGPL-3.0 repository license, file-level scope pending"],"huderlem/poryscript":["LICENSE.md","bc574ff56a7df993996053c7b2afec43e80bdd64","MIT repository license, file-level scope pending"]}
SCOPE={"34":"LIBRETRO_ABI_SOURCE_NOT_NATIVE_EXECUTION","48":"PORYMAP_EDITOR_SOURCE_NOT_NEW_NATIVE_TEST","49":"PORYMAP_MAINWINDOW_SOURCE_NOT_NEW_NATIVE_TEST","50":"PORYMAP_PROJECT_SOURCE_NOT_NEW_NATIVE_TEST","57":"PORYSCRIPT_EMITTER_GO_TEST_NOT_GAMEPLAY","62":"PORYSCRIPT_PARSER_GO_TEST_NOT_GAMEPLAY"}
def read(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-p0"}),timeout=45) as r:return r.read()
def check(raw,rec,packet):
 verify(raw,rec,packet)
 assert hashlib.sha256(raw).hexdigest()==rec["whole_source_sha256_from_machine_packet_unverified"]==packet["whole_blob_sha256"]
 assert rec["platform_scope"]==SCOPE[str(rec["packet_index"])]
 assert rec["evidence_class"]=="PINNED_SOURCE_ONLY"
 assert len(rec["reviewer_questions"])==5
 assert len(rec["dependency_edges"])>=2 and len(rec["unresolved"])>=2
 assert rec["license_status"]=="PENDING_INDEPENDENT_FILE_SCOPE_AND_DEPENDENCY_RECONCILIATION"
 src=rec["source"];lic=rec["license_evidence"]
 assert lic["repository"]==src["repository"] and lic["revision"]==src["revision"]
 assert [lic["license_path"],lic["license_git_blob_sha1"],lic["license_scope_note"]]==LIC[src["repository"]]
 if rec["packet_index"]==34:
  assert b"The following license statement only applies to this libretro API header" in raw
  assert b"Permission is hereby granted" in raw
def reject(raw,rec,packet):
 try:check(raw,rec,packet)
 except (AssertionError,KeyError,IndexError,TypeError,UnicodeDecodeError):return
 raise AssertionError("forged source/approval accepted")
def main():
 p=json.loads(SPEC.read_text())
 assert p["schema"]=="xgba.phase1.remaining_p0_partial_analyst_batch.v12"
 assert p["new_partial_indices"]==EXPECTED and len(p["previous_partial_indices"])==94
 assert sorted(p["new_partial_indices"]+p["previous_partial_indices"])==list(range(100))
 assert p["remaining_p0_partial_total"]==100 and p["partial_source_inspected"]==len(p["records"])==6
 assert p["gate"]=="FAIL_INCOMPLETE" and p["curated_29_source_inspected"]==29
 assert p["independent_p0_approved"]==p["independent_total_approved"]==0
 data=(ROOT/p["source_packet"]).read_bytes()
 assert git_blob(data)==p["source_packet_blob_sha1"]
 packets=json.loads(data)["packets"]
 for repo,(path,sha,note) in LIC.items():
  pin=next(r["source"]["revision"] for r in p["records"] if r["source"]["repository"]==repo)
  raw=read(f"https://raw.githubusercontent.com/{repo}/{pin}/{path}")
  assert git_blob(raw)==sha
 negatives=0
 for rec in p["records"]:
  i=rec["packet_index"];assert i in EXPECTED
  s=rec["source"];raw=read("https://raw.githubusercontent.com/{}/{}/{}".format(s["repository"],s["revision"],s["path"]))
  check(raw,rec,packets[i])
  changed=raw.replace(rec["line_anchors"][0]["text"].encode(),b"XGBA_NEGATIVE_SOURCE",1)
  assert changed!=raw;reject(changed,rec,packets[i]);negatives+=1
  for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","fabricated"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha1","fake"),("machine_dossier_sha256_unverified","0"*64),("responsibilities",""),("dependency_edges",[]),("unresolved",[]),("platform_scope","STOCK_GAMEPLAY"),("evidence_class","NATIVE_RUNTIME"),("whole_source_sha256_from_machine_packet_unverified","0"*64)):
   bad=copy.deepcopy(rec);bad[field]=value;reject(raw,bad,packets[i]);negatives+=1
  for field,value in (("path","wrong"),("git_blob_sha1","0"*40)):
   bad=copy.deepcopy(rec);bad["source"][field]=value;reject(raw,bad,packets[i]);negatives+=1
  for field,value in (("line",rec["line_anchors"][0]["line"]+1),("text","forged")):
   bad=copy.deepcopy(rec);bad["line_anchors"][0][field]=value;reject(raw,bad,packets[i]);negatives+=1
  bad=copy.deepcopy(rec);bad["license_evidence"]["license_git_blob_sha1"]="0"*40
  reject(raw,bad,packets[i]);negatives+=1
  print("P0_QT_GO_LIBRETRO_SOURCE_OK",i,s["path"],s["git_blob_sha1"])
 assert negatives==108
 print("P0_QT_GO_LIBRETRO_PASS files=6 negatives=108 packet=100/100 remaining_p0_partial=100 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
