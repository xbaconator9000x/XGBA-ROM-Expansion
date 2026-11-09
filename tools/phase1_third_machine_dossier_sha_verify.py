#!/usr/bin/env python3
"""Original compressed machine dossier byte reconciliation for third P0 packet ONLY."""
from __future__ import annotations
import copy
import json
from pathlib import Path
from phase1_bulk_triage import read_queue,checked_dossiers,canonical,digest,git_blob,PINS

ROOT=Path(__file__).resolve().parents[1]
SNAP=ROOT/"semantic-snapshots/current"
BASE=ROOT/"docs/phase1-review-readiness"
RECEIPT=BASE/"machine-dossier-byte-reconciliation-0200-0299-20261030.json"
PACKET=BASE/"packet-0200-0299.json"
BLOBS={"candidate_review_dossiers.jsonl.gz":"3b982876c7d810a827af8c80c7e5d9231fdaa327","semantic_review_queue.csv.gz":"52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268","phase1_mapping_gate.json":"dab5789433dc55cf325a917a220d060088bf1d29"}
PACKET_BLOB="c998c2ea8c887968e586b1792c5207ecb5286839"
def check(record,original):
 ident=record["identity"];prov=original["provenance"]
 assert ident["repository"] in PINS
 assert (ident["repository"],ident["pinned_commit"],ident["path"],ident["git_blob_sha1"])==(prov["repository"],prov["pinned_revision"],prov["path"],prov["git_blob_sha"])
 assert ident["pinned_commit"]==PINS[ident["repository"]]
 assert record["dossier_sha256"]==digest(canonical(original))
 assert record["whole_blob_sha256"]==prov["source_content_sha256"]
 assert record["priority"]==original["machine_assessment"]["priority"]=="P0"
 assert record["state"]=="MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION"
 assert record["independently_approved"] is False
 assert original["review"]["semantic_signoff"] is False and original["review"]["reviewer"] is None
def reject(record,original):
 try:check(record,original)
 except (AssertionError,KeyError,TypeError):return
 raise AssertionError("forged original dossier or approval accepted")
def main():
 receipt=json.loads(RECEIPT.read_bytes())
 assert receipt["schema"]=="xgba.phase1.third_packet_machine_dossier_byte_reconciliation.v1"
 assert receipt["original_snapshot_git_blobs"]==BLOBS
 assert receipt["packet_git_blob_sha1"]==PACKET_BLOB
 assert receipt["packet"]=="docs/phase1-review-readiness/packet-0200-0299.json"
 assert receipt["machine_dossier_byte_checks"]==100 and receipt["original_machine_inventory_rehashed"]==14834
 assert receipt["packet_indices"]=="200..299" and receipt["validation_status"]=="REQUIRES_EXACT_HEAD_ACTIONS_SUCCESS"
 assert receipt["independent_p0_approved"]==receipt["independent_total_approved"]==receipt["whole_file_semantic_approved"]==0
 assert receipt["phase1_gate"]=="FAIL_INCOMPLETE"
 for name,sha in BLOBS.items():
  assert git_blob((SNAP/name).read_bytes())==sha
 gate=json.loads((SNAP/"phase1_mapping_gate.json").read_bytes())
 assert gate["decision"]=="FAIL_INCOMPLETE" and gate["approved_semantic_dispositions"]==0
 assert gate["p0_review_candidates"]==338 and gate["machine_generated_dossiers"]==14834
 queue=read_queue(SNAP)
 original=checked_dossiers(SNAP,queue)
 assert len(original)==len(queue)==14834
 raw=PACKET.read_bytes()
 assert git_blob(raw)==PACKET_BLOB
 packet=json.loads(raw)
 assert packet["review_packets"]==len(packet["packets"])==100
 assert packet["phase1_gate"]=="FAIL_INCOMPLETE"
 assert packet["independent_approvals_added"]==packet["prepared_whole_file_dispositions_added"]==0
 prior=set()
 for path in ("packet-0000-0099.json","packet-0100-0199.json"):
  d=json.loads((BASE/path).read_bytes())
  assert d["phase1_gate"]=="FAIL_INCOMPLETE"
  prior|={(r["identity"]["repository"],r["identity"]["path"]) for r in d["packets"]}
 assert len(prior)==200
 seen=set();negatives=0
 for r in packet["packets"]:
  i=r["identity"];key=(i["repository"],i["path"])
  assert key not in prior and key not in seen and key in original
  seen.add(key);d=original[key]
  check(r,d)
  for field,value in (("dossier_sha256","0"*64),("whole_blob_sha256","0"*64),("priority","P3"),("independently_approved",True),("state","APPROVED")):
   bad=copy.deepcopy(r);bad[field]=value;reject(bad,d);negatives+=1
  bad=copy.deepcopy(r);bad["identity"]["git_blob_sha1"]="0"*40;reject(bad,d);negatives+=1
  bad=copy.deepcopy(d);bad["review"]["semantic_signoff"]=True;reject(r,bad);negatives+=1
 assert len(seen)==100
 for field,value in (("phase1_gate","PASS"),("independent_approvals_added",1)):
  bad=copy.deepcopy(packet);bad[field]=value
  assert bad!=packet
  negatives+=1
 forged_gate=dict(gate,approved_semantic_dispositions=1)
 assert forged_gate!=gate;negatives+=1
 assert git_blob((SNAP/"candidate_review_dossiers.jsonl.gz").read_bytes()+b"XGBA_FORGED_BYTES")!=BLOBS["candidate_review_dossiers.jsonl.gz"];negatives+=1
 assert negatives==704,negatives
 print("P0_THIRD_MACHINE_DOSSIER_PASS records=100 original_inventory=14834 negatives=704 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
 print("P0_THIRD_MACHINE_SCOPE compressed original bytes and source digests, NOT independent full-file semantic review, compiled/runtime or licensing")
if __name__=="__main__":main()
