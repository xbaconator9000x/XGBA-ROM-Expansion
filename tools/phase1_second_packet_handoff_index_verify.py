#!/usr/bin/env python3
"""Cross-batch second P0 packet: exact machine identity and fail-closed partial status."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
INDEX=BASE/"second-packet-partial-handoff-index-20261030.json"
EXPECTED=list(range(100,108))+list(range(130,158))
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def validate(r,p):
 s=r["source"];i=p["identity"]
 assert p["priority"]=="P0" and p["independently_approved"] is False
 assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"])==(i["repository"],i["pinned_commit"],i["path"],i["git_blob_sha1"])
 assert r.get("machine_dossier_sha256_verified_in_original_bytes",r.get("machine_dossier_sha256_unverified"))==p["dossier_sha256"]
 assert r.get("whole_source_sha256_from_packet",r.get("whole_source_sha256_from_machine_packet_unverified"))==p["whole_blob_sha256"]
 assert r["analyst_status"]=="PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
 assert r["whole_file_semantic_coverage"] is False and r["independent_reviewer"] is None and r["independent_verdict"]=="NEEDS_REVIEW"
 assert r["license_status"].startswith("PENDING_")
 assert len(r["line_anchors"])>=4 and r["dependency_edges"] and r["unresolved"] and r.get("responsibilities",r.get("source_observations"))
 assert r["evidence_class"] in ("PINNED_SOURCE_ONLY","PINNED_AUTHORED_SOURCE_ONLY")
def reject(r,p):
 try:validate(r,p)
 except (AssertionError,KeyError,TypeError):return
 raise AssertionError("forged cross-batch record accepted")
def main():
 idx=json.loads(INDEX.read_bytes());raw=(ROOT/idx["packet"]).read_bytes()
 assert idx["schema"]=="xgba.phase1.second_packet_partial_handoff_index.v1"
 assert blob(raw)==idx["packet_blob_sha1"]=="3ddc0b8f66c8f14351a18208fa11e823f73b1d63"
 packets=json.loads(raw)["packets"]
 receipt=json.loads((ROOT/idx["original_machine_receipt"]).read_bytes())
 assert receipt["machine_dossier_byte_checks"]==200 and receipt["phase1_gate"]=="FAIL_INCOMPLETE"
 assert receipt["packet_git_blobs"][idx["packet"]]==idx["packet_blob_sha1"]
 first=json.loads((ROOT/idx["first_packet_index"]).read_bytes())
 assert first["remaining_p0_partial_source_inspected"]==100 and first["independent_p0_approved"]==0
 assert idx["batch_sizes"]==[4,4,4,8,8,4,4] and len(idx["batches"])==7
 assert idx["second_packet_partial_source_inspected"]==36 and idx["remaining_p0_partial_source_inspected"]==136
 assert idx["remaining_p0_without_partial_source_inspection"]==173 and idx["curated_p0_partial_source_inspected"]==29 and idx["total_p0_partial_source_inspected"]==165
 assert idx["phase1_gate"]=="FAIL_INCOMPLETE" and idx["independent_p0_approved"]==idx["independent_total_approved"]==idx["whole_file_semantic_approved"]==0
 seen=set();negatives=0
 for path,count in zip(idx["batches"],idx["batch_sizes"]):
  batch=json.loads((ROOT/path).read_bytes())
  assert batch["source_packet"]==idx["packet"] and batch["source_packet_blob_sha1"]==idx["packet_blob_sha1"]
  assert batch["gate"]=="FAIL_INCOMPLETE" and batch["independent_p0_approved"]==batch["independent_total_approved"]==0
  assert len(batch["records"])==count and batch["new_partial_indices"]==[r["packet_index"] for r in batch["records"]]
  for r in batch["records"]:
   n=r["packet_index"];assert n in EXPECTED and n not in seen;seen.add(n)
   p=packets[n-100];validate(r,p)
   for field,value in [("independent_verdict","APPROVED"),("independent_reviewer","fabricated"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("analyst_status","APPROVED"),("evidence_class","STOCK_GAMEPLAY"),("line_anchors",[])]:
    bad=copy.deepcopy(r);bad[field]=value;reject(bad,p);negatives+=1
   for field,value in [("path","wrong.inc"),("git_blob_sha1","0"*40)]:
    bad=copy.deepcopy(r);bad["source"][field]=value;reject(bad,p);negatives+=1
   field="machine_dossier_sha256_verified_in_original_bytes" if "machine_dossier_sha256_verified_in_original_bytes" in r else "machine_dossier_sha256_unverified"
   bad=copy.deepcopy(r);bad[field]="0"*64;reject(bad,p);negatives+=1
 assert sorted(seen)==EXPECTED and negatives==360,(sorted(seen),negatives)
 print("P0_SECOND_PACKET_INDEX_PASS second_partial=36 first_partial=100 other_p0_partial=136 curated=29 total_partial=165 negatives=360 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
