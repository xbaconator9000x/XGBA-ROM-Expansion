#!/usr/bin/env python3
"""Regenerate third P0 machine packet from original five source-reconciled shards; never approval."""
from __future__ import annotations
import copy
import json
from pathlib import Path
from phase1_review_packets import load_shards,validate_integrity,packets,canonical

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
SHARDS=ROOT/"docs/phase1-machine-triage"
NEW=BASE/"packet-0200-0299.json"
def check(r,expected,original):
 assert r["identity"]==expected["identity"]==original["identity"]
 assert r["priority"]==expected["priority"]==original["priority"]=="P0"
 assert r["dossier_sha256"]==expected["dossier_sha256"]==original["evidence"]["dossier_sha256"]
 assert r["whole_blob_sha256"]==expected["whole_blob_sha256"]==original["whole_file_structure"]["whole_blob_sha256"]
 assert r["source_lines"]==expected["source_lines"]==original["whole_file_structure"].get("source_lines")
 assert r["candidate_include_edges"]==expected["candidate_include_edges"]
 assert r["candidate_incoming_include_edges"]==expected["candidate_incoming_include_edges"]
 assert r["unresolved_or_ambiguous_includes"]==expected["unresolved_or_ambiguous_includes"]
 assert r["risk_flag_line_anchors"]==expected["risk_flag_line_anchors"]
 assert r["review_tasks"]==expected["review_tasks"] and len(r["review_tasks"])==5
 assert r["state"]=="MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION"
 assert r["independently_approved"] is False
 assert original["independent_approval"] is False and original["prepared_whole_file_candidate"] is False
def reject(r,expected,original):
 try:check(r,expected,original)
 except (AssertionError,KeyError,TypeError):return
 raise AssertionError("forged third-packet identity, dossier or approval accepted")
def main():
 records,shards=load_shards(SHARDS)
 assert len(records)==2000
 integrity=validate_integrity(SHARDS,shards,len(records))
 full=packets(records,shards,max_packets=300,integrity_sha256=integrity)
 assert len(full["packets"])==300 and all(p["priority"]=="P0" for p in full["packets"])
 for start,end,path in ((0,100,"packet-0000-0099.json"),(100,200,"packet-0100-0199.json"),(200,300,"packet-0200-0299.json")):
  d=dict(full,packets=full["packets"][start:end],review_packets=100)
  assert (BASE/path).read_bytes()==canonical(d),("machine packet drift",path)
 new=json.loads(NEW.read_bytes())
 assert new["review_packets"]==100 and len(new["packets"])==100
 assert new["phase1_gate"]=="FAIL_INCOMPLETE" and new["independent_approvals_added"]==new["prepared_whole_file_dispositions_added"]==0
 assert new["upstream_integrity_sha256"]==integrity
 assert new["verified_machine_triage_records"]==2000
 seen=set();negatives=0
 for i,r in enumerate(new["packets"]):
  expected=full["packets"][200+i]
  key=(r["identity"]["repository"],r["identity"]["path"])
  assert key not in seen and key in records;seen.add(key)
  original=records[key]
  check(r,expected,original)
  for field,value in (("independently_approved",True),("dossier_sha256","0"*64),("whole_blob_sha256","0"*64),("state","APPROVED"),("source_lines",0),("priority","P3"),("candidate_incoming_include_edges",r["candidate_incoming_include_edges"]+1),("unresolved_or_ambiguous_includes",r["unresolved_or_ambiguous_includes"]+1),("review_tasks",[]),("candidate_include_edges",[{"forged":True}]),("risk_flag_line_anchors",{"forged":[1]})):
   bad=copy.deepcopy(r);bad[field]=value;reject(bad,expected,original);negatives+=1
  for field,value in (("git_blob_sha1","0"*40),("pinned_commit","0"*40)):
   bad=copy.deepcopy(r);bad["identity"][field]=value;reject(bad,expected,original);negatives+=1
 assert len(seen)==100
 for field,value in (("phase1_gate","PASS"),("independent_approvals_added",1),("prepared_whole_file_dispositions_added",1),("review_packets",101)):
  bad=copy.deepcopy(new);bad[field]=value
  assert canonical(bad)!=NEW.read_bytes()
  negatives+=1
 assert negatives==1304,negatives
 print("P0_THIRD_PACKET_PASS records=100 source_reconciled_machine=2000 negatives=1304 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
 print("P0_THIRD_PACKET_SCOPE original machine shard identities and SHA strings, NOT yet original compressed dossier bytes for indices 200..299 or independent semantic review")
if __name__=="__main__":main()
