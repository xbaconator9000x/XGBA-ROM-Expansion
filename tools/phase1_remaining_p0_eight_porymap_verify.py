#!/usr/bin/env python3
"""Eight original pinned Porymap event/connection P0 partial analyst dossiers."""
import copy,json,urllib.request
from pathlib import Path
from phase1_remaining_p0_eight_verify import git_blob,verify,reject
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=json.loads((ROOT/"docs/phase1-review-readiness/remaining-p0-eight-porymap-20261029.json").read_text())
 assert p["gate"]=="FAIL_INCOMPLETE" and p["independent_p0_approved"]==p["independent_total_approved"]==0
 assert p["curated_29_source_inspected"]==29 and p["remaining_p0_partial_total"]==46
 assert len(p["records"])==p["partial_source_inspected"]==8
 assert len(set(p["previous_partial_indices"]))==38 and not set(p["previous_partial_indices"])&set(p["new_partial_indices"])
 packet_bytes=(ROOT/p["source_packet"]).read_bytes()
 assert git_blob(packet_bytes)==p["source_packet_blob_sha1"]
 packets=json.loads(packet_bytes)["packets"]
 negatives=0
 for rec in p["records"]:
  i=rec["packet_index"];assert i in p["new_partial_indices"]
  s=rec["source"]
  url="https://raw.githubusercontent.com/{}/{}/{}".format(s["repository"],s["revision"],s["path"])
  with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-porymap-p0"}),timeout=45) as response:raw=response.read()
  verify(raw,rec,packets[i])
  assert rec["evidence_class"]=="PINNED_SOURCE_ONLY" and len(rec["reviewer_questions"])>=4
  changed=raw.replace(rec["line_anchors"][0]["text"].encode(),b"XGBA_EDITOR_NEGATIVE",1)
  assert changed!=raw
  reject(changed,rec,packets[i]);negatives+=1
  for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","invented"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha1","fabricated"),("machine_dossier_sha256_unverified","0"*64),("responsibilities",""),("dependency_edges",[]),("unresolved",[])):
   bad=copy.deepcopy(rec);bad[field]=value;reject(raw,bad,packets[i]);negatives+=1
  for field,value in (("path","wrong.cpp"),("git_blob_sha1","0"*40)):
   bad=copy.deepcopy(rec);bad["source"][field]=value;reject(raw,bad,packets[i]);negatives+=1
  for field,value in (("line",rec["line_anchors"][0]["line"]+1),("text","wrong source")):
   bad=copy.deepcopy(rec);bad["line_anchors"][0][field]=value;reject(raw,bad,packets[i]);negatives+=1
  print("P0_PORYMAP_SOURCE_OK",i,s["path"],s["git_blob_sha1"])
 assert negatives==112
 print("P0_PORYMAP_PASS files=8 negatives=112 curated=29 remaining_p0_partial=46 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
