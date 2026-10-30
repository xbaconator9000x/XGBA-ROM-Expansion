#!/usr/bin/env python3
"""Pinned original FireRed route-script partial dossiers; never independent approvals."""
import copy, hashlib, json, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PACKET_BLOB="c998c2ea8c887968e586b1792c5207ecb5286839"
BATCHES=["remaining-p0-eight-firered-routes-204-211-20261030.json","remaining-p0-eight-firered-routes-212-219-20261030.json","remaining-p0-eight-firered-saffron-seafoam-seven-220-227-20261030.json","remaining-p0-eight-firered-sevenisland-tanoby-228-235-20261030.json","remaining-p0-eight-firered-tanoby-trainertower-silph-236-243-20261030.json"]
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def get(path):
 url=f"https://raw.githubusercontent.com/pret/pokefirered/{PIN}/{path}"
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-route-source"}),timeout=45) as resp:return resp.read()
def check(raw,r,p,n):
 s=r["source"];i=p["identity"]
 assert r["packet_index"]==n and p["priority"]=="P0" and p["independently_approved"] is False
 assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"])==(i["repository"],i["pinned_commit"],i["path"],i["git_blob_sha1"])
 assert s["repository"]=="pret/pokefirered" and s["revision"]==PIN
 assert s["url"]==f"https://github.com/pret/pokefirered/blob/{PIN}/{s['path']}"
 assert blob(raw)==s["git_blob_sha1"] and hashlib.sha256(raw).hexdigest()==r["whole_source_sha256_from_packet"]==p["whole_blob_sha256"]
 assert r["machine_dossier_sha256_reconciled_via_original_byte_receipt"]==p["dossier_sha256"]
 assert r["platform_scope"]=="AUTHORED_FIRERED_SCRIPT_SOURCE_ONLY_NOT_EXECUTED" and r["evidence_class"]=="PINNED_AUTHORED_SOURCE_ONLY"
 assert r["analyst_status"]=="PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
 assert r["whole_file_semantic_coverage"] is False and r["independent_reviewer"] is None and r["independent_verdict"]=="NEEDS_REVIEW"
 assert r["license_status"]=="PENDING_INDEPENDENT_ORIGINAL_ASSET_AND_DERIVATIVE_LICENSING"
 assert r["license_evidence"]=={"repository":"pret/pokefirered","file_notice":"NO_LICENSE_NOTICE_IN_SELECTED_SCRIPT_HEADER","license_clearance":"NOT_ESTABLISHED"}
 assert r["source_observations"] and len(r["dependency_edges"])>=4 and len(r["unresolved"])>=4 and len(r["reviewer_questions"])==5
 assert len(r["line_anchors"])>=(6 if p["source_lines"]<8 else 8) and len(r["required_source_tokens"])>=5
 lines=raw.decode("utf-8").splitlines()
 assert len(lines)==p["source_lines"]
 for a in r["line_anchors"]:assert 0<a["line"]<=len(lines) and lines[a["line"]-1]==a["text"]
 for token in r["required_source_tokens"]:assert token.encode() in raw
def reject(raw,r,p,n):
 try:check(raw,r,p,n)
 except (AssertionError,KeyError,TypeError,IndexError,UnicodeDecodeError):return
 raise AssertionError("forged source or approval accepted")
def main():
 packetraw=(BASE/"packet-0200-0299.json").read_bytes()
 assert blob(packetraw)==PACKET_BLOB
 packet=json.loads(packetraw)["packets"]
 receipt=json.loads((BASE/"machine-dossier-byte-reconciliation-0200-0299-20261030.json").read_bytes())
 assert receipt["machine_dossier_byte_checks"]==100 and receipt["phase1_gate"]=="FAIL_INCOMPLETE" and receipt["packet_git_blob_sha1"]==PACKET_BLOB
 seen=set();negatives=0
 for filename in BATCHES:
  d=json.loads((BASE/filename).read_bytes())
  assert d["source_packet_blob_sha1"]==PACKET_BLOB and d["gate"]=="FAIL_INCOMPLETE"
  assert d["independent_p0_approved"]==d["independent_total_approved"]==0
  assert d["new_partial_indices"]==[r["packet_index"] for r in d["records"]]
  for r in d["records"]:
   n=r["packet_index"];assert n in range(204,244) and n not in seen;seen.add(n)
   p=packet[n-200];raw=get(r["source"]["path"]);check(raw,r,p,n)
   changed=raw.replace(r["line_anchors"][0]["text"].encode(),b"XGBA_FORGED",1)
   assert changed!=raw;reject(changed,r,p,n);negatives+=1
   for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","invented"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha256_reconciled_via_original_byte_receipt","0"*64),("whole_source_sha256_from_packet","0"*64),("source_observations",""),("dependency_edges",[]),("unresolved",[]),("evidence_class","STOCK_GAMEPLAY"),("platform_scope","NATIVE_FLASH"),("required_source_tokens",["XGBA_FORGED"]),("line_anchors",[]),("packet_index",n+1),("analyst_status","APPROVED"),("license_evidence",{})):
    bad=copy.deepcopy(r);bad[field]=value;reject(raw,bad,p,n);negatives+=1
   for field,value in (("path","wrong.inc"),("git_blob_sha1","0"*40)):
    bad=copy.deepcopy(r);bad["source"][field]=value;reject(raw,bad,p,n);negatives+=1
   bad=copy.deepcopy(r);bad["line_anchors"][0]["line"]+=1;reject(raw,bad,p,n);negatives+=1
   print("P0_THIRD_ROUTE_SOURCE_OK",n,r["source"]["path"],r["source"]["git_blob_sha1"])
 assert sorted(seen)==list(range(204,244)) and negatives==800,(seen,negatives)
 print(f"P0_THIRD_ROUTE_PASS files={len(seen)} negatives={negatives} approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
