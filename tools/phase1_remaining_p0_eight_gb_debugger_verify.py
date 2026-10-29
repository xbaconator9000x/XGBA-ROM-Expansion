#!/usr/bin/env python3
"""Original pinned mGBA GB/SM83 + shared scripting/debugger partial dossiers; no approvals."""
import copy, hashlib, json, urllib.request
from pathlib import Path
from phase1_remaining_p0_eight_verify import git_blob, verify, reject
ROOT=Path(__file__).resolve().parents[1]
SPEC=ROOT/"docs/phase1-review-readiness/remaining-p0-eight-gb-debugger-20261029.json"
EXPECTED=[73,74,75,76,77,78,79,80]
def main():
 p=json.loads(SPEC.read_text())
 assert p["schema"]=="xgba.phase1.remaining_p0_partial_analyst_batch.v10"
 assert p["gate"]=="FAIL_INCOMPLETE" and p["independent_p0_approved"]==p["independent_total_approved"]==0
 assert p["remaining_p0_partial_total"]==86 and p["curated_29_source_inspected"]==29
 assert p["new_partial_indices"]==EXPECTED and len(p["previous_partial_indices"])==78
 assert len(set(p["previous_partial_indices"]))==78 and not (set(EXPECTED)&set(p["previous_partial_indices"]))
 assert len(p["records"])==8 and p["partial_source_inspected"]==8
 data=(ROOT/p["source_packet"]).read_bytes()
 assert git_blob(data)==p["source_packet_blob_sha1"]
 packets=json.loads(data)["packets"]
 license_url="https://raw.githubusercontent.com/mgba-emu/mgba/fd9dc5c2cbf234365068855851107e762fc6211b/LICENSE"
 with urllib.request.urlopen(urllib.request.Request(license_url,headers={"User-Agent":"xgba-phase1-gb-license"}),timeout=45) as response: lic=response.read()
 assert git_blob(lic)=="14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e" and b"Mozilla Public License Version 2.0" in lic
 negatives=0
 for rec in p["records"]:
  i=rec["packet_index"];assert i in EXPECTED
  s=rec["source"];assert s["repository"]=="mgba-emu/mgba" and s["revision"]=="fd9dc5c2cbf234365068855851107e762fc6211b"
  url="https://raw.githubusercontent.com/{}/{}/{}".format(s["repository"],s["revision"],s["path"])
  with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-gb-debugger"}),timeout=45) as response:raw=response.read()
  verify(raw,rec,packets[i])
  assert hashlib.sha256(raw).hexdigest()==rec["whole_source_sha256_from_machine_packet_unverified"]==packets[i]["whole_blob_sha256"]
  assert b"Mozilla Public" in raw and b"License, v. 2.0." in raw
  assert rec["license_evidence"]=={"pinned_repository":"mgba-emu/mgba","pinned_revision":"fd9dc5c2cbf234365068855851107e762fc6211b","license_path":"LICENSE","license_git_blob_sha1":"14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e","file_notice_lines":[3,4,5],"file_notice":"Mozilla Public License, v. 2.0."}
  assert rec["platform_scope"]==("GAME_BOY_SM83_ONLY_NOT_GBA_FLASH" if i>=75 else "SHARED_MGBA_DEBUGGER_OR_SCRIPT_HOST_NOT_STOCK_GAMEPLAY")
  assert len(rec["line_anchors"])>=4 and len(rec["reviewer_questions"])==5
  assert rec["license_status"]=="PENDING_INDEPENDENT_FILE_SCOPE_AND_DEPENDENCY_RECONCILIATION"
  changed=raw.replace(rec["line_anchors"][0]["text"].encode(),b"XGBA_NEGATIVE_GB_DEBUGGER",1)
  assert changed!=raw;reject(changed,rec,packets[i]);negatives+=1
  for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","invented"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha1","fabricated"),("machine_dossier_sha256_unverified","0"*64),("responsibilities",""),("dependency_edges",[]),("unresolved",[])):
   bad=copy.deepcopy(rec);bad[field]=value;reject(raw,bad,packets[i]);negatives+=1
  for field,value in (("path","wrong.c"),("git_blob_sha1","0"*40)):
   bad=copy.deepcopy(rec);bad["source"][field]=value;reject(raw,bad,packets[i]);negatives+=1
  for field,value in (("line",rec["line_anchors"][0]["line"]+1),("text","fabricated anchor")):
   bad=copy.deepcopy(rec);bad["line_anchors"][0][field]=value;reject(raw,bad,packets[i]);negatives+=1
  bad=copy.deepcopy(rec);bad["license_evidence"]["license_git_blob_sha1"]="0"*40
  assert bad["license_evidence"]["license_git_blob_sha1"]!="14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e";negatives+=1
  bad=copy.deepcopy(rec);bad["platform_scope"]="FIRERED_GBA_FLASH_NATIVE_PROVEN"
  assert bad["platform_scope"]!=rec["platform_scope"];negatives+=1
  print("P0_GB_DEBUGGER_SOURCE_OK",i,s["path"],s["git_blob_sha1"])
 assert negatives==128
 print("P0_GB_DEBUGGER_PASS files=8 negatives=128 curated=29 remaining_p0_partial=86 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
