#!/usr/bin/env python3
"""Third P0 packet cross-batch source partial index; no independent approval."""
import copy,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
INDEX=BASE/"third-packet-partial-handoff-index-20261030.json"
PACKET_BLOB="c998c2ea8c887968e586b1792c5207ecb5286839"
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def check(r,p):
 s=r["source"];i=p["identity"]
 assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"])==(i["repository"],i["pinned_commit"],i["path"],i["git_blob_sha1"])
 assert p["priority"]=="P0" and p["independently_approved"] is False
 assert r["machine_dossier_sha256_reconciled_via_original_byte_receipt"]==p["dossier_sha256"]
 assert r["whole_source_sha256_from_packet"]==p["whole_blob_sha256"]
 assert r["analyst_status"]=="PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
 assert r["whole_file_semantic_coverage"] is False and r["independent_reviewer"] is None and r["independent_verdict"]=="NEEDS_REVIEW"
 assert r["license_status"].startswith("PENDING_")
 assert r["platform_scope"]=="AUTHORED_FIRERED_SCRIPT_SOURCE_ONLY_NOT_EXECUTED"
 assert r["evidence_class"]=="PINNED_AUTHORED_SOURCE_ONLY"
 assert len(r["line_anchors"])>=(6 if p["source_lines"]<8 else 8) and len(r["dependency_edges"])>=4 and len(r["unresolved"])>=4 and r["source_observations"]
 assert (r["map_json_static_wiring"]["git_blob_sha1"] and r["map_json_static_wiring"]["required_event_scripts"]) if r["packet_index"]<204 else r["packet_index"] in range(204,260)
def reject(r,p):
 try:check(r,p)
 except (AssertionError,KeyError,TypeError):return
 raise AssertionError("forged partial or independent approval accepted")
def main():
 idx=json.loads(INDEX.read_bytes())
 assert idx["schema"]=="xgba.phase1.third_packet_partial_handoff_index.v1"
 raw=(ROOT/idx["packet"]).read_bytes()
 assert blob(raw)==idx["packet_blob_sha1"]==PACKET_BLOB
 packet=json.loads(raw)["packets"]
 receipt=json.loads((ROOT/idx["original_machine_receipt"]).read_bytes())
 assert receipt["machine_dossier_byte_checks"]==100 and receipt["phase1_gate"]=="FAIL_INCOMPLETE" and receipt["packet_git_blob_sha1"]==PACKET_BLOB
 first=json.loads((ROOT/idx["first_packet_index"]).read_bytes())
 second=json.loads((ROOT/idx["second_packet_index"]).read_bytes())
 assert first["remaining_p0_partial_source_inspected"]==100 and first["independent_p0_approved"]==0
 assert second["second_packet_partial_source_inspected"]==83 and second["remaining_p0_partial_source_inspected"]==183
 assert second["independent_p0_approved"]==second["independent_total_approved"]==0
 assert idx["batches"]==["docs/phase1-review-readiness/remaining-p0-four-firered-powerplant-rocket-20261030.json","docs/phase1-review-readiness/remaining-p0-eight-firered-routes-204-211-20261030.json","docs/phase1-review-readiness/remaining-p0-eight-firered-routes-212-219-20261030.json","docs/phase1-review-readiness/remaining-p0-eight-firered-saffron-seafoam-seven-220-227-20261030.json","docs/phase1-review-readiness/remaining-p0-eight-firered-sevenisland-tanoby-228-235-20261030.json","docs/phase1-review-readiness/remaining-p0-eight-firered-tanoby-trainertower-silph-236-243-20261030.json","docs/phase1-review-readiness/remaining-p0-eight-firered-silph-sixisland-244-251-20261031.json","docs/phase1-review-readiness/remaining-p0-eight-firered-sixisland-threeisland-252-259-20261031.json"]
 assert idx["batch_sizes"]==[4,8,8,8,8,8,8,8]
 assert idx["third_packet_partial_source_inspected"]==60 and idx["second_packet_partial_source_inspected"]==83 and idx["first_packet_partial_source_inspected"]==100
 assert idx["remaining_p0_partial_source_inspected"]==243 and idx["remaining_p0_without_partial_source_inspection"]==66
 assert idx["curated_p0_partial_source_inspected"]==29 and idx["total_p0_partial_source_inspected"]==272
 assert idx["independent_p0_approved"]==idx["independent_total_approved"]==idx["whole_file_semantic_approved"]==0
 assert idx["phase1_gate"]=="FAIL_INCOMPLETE"
 seen=set();negatives=0
 for path,count in zip(idx["batches"],idx["batch_sizes"]):
  d=json.loads((ROOT/path).read_bytes())
  assert d["source_packet"]==idx["packet"] and d["source_packet_blob_sha1"]==PACKET_BLOB
  assert d["gate"]=="FAIL_INCOMPLETE" and d["independent_p0_approved"]==d["independent_total_approved"]==0
  assert len(d["records"])==count and d["new_partial_indices"]==[r["packet_index"] for r in d["records"]]
  for r in d["records"]:
   n=r["packet_index"]
   assert n in range(200,260) and n not in seen;seen.add(n)
   p=packet[n-200];check(r,p)
   for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","fabricated"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("analyst_status","APPROVED"),("evidence_class","STOCK_GAMEPLAY"),("line_anchors",[])):
    bad=copy.deepcopy(r);bad[field]=value;reject(bad,p);negatives+=1
   for field,value in (("path","wrong.inc"),("git_blob_sha1","0"*40)):
    bad=copy.deepcopy(r);bad["source"][field]=value;reject(bad,p);negatives+=1
   bad=copy.deepcopy(r);bad["machine_dossier_sha256_reconciled_via_original_byte_receipt"]="0"*64;reject(bad,p);negatives+=1
 assert sorted(seen)==list(range(200,260)) and negatives==600,(seen,negatives)
 print("P0_THIRD_HANDOFF_INDEX_PASS third_partial=60 second_partial=83 first_partial=100 other_p0_partial=243 curated=29 total_partial=272 negatives=600 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
