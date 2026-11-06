#!/usr/bin/env python3
"""Verify eight original FireRed Sevii map-script partials; fail closed."""
import copy,hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
SPEC=BASE/"remaining-p0-eight-firered-sevii-20261030.json"
PACKET=BASE/"packet-0100-0199.json"
RECEIPT=BASE/"machine-dossier-byte-reconciliation-0000-0199-20261030.json"
EXPECTED=list(range(142,150))
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def read(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-sevii"}),timeout=45) as response:return response.read()
def check(raw,r,p):
 s=r["source"];i=p["identity"];n=r["packet_index"]
 assert n in EXPECTED and p["priority"]=="P0" and p["independently_approved"] is False
 assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"])==(i["repository"],i["pinned_commit"],i["path"],i["git_blob_sha1"])
 assert s["repository"]=="pret/pokefirered" and s["revision"]==PIN
 assert s["url"]==f"https://github.com/pret/pokefirered/blob/{PIN}/{s['path']}"
 assert blob(raw)==s["git_blob_sha1"]
 assert hashlib.sha256(raw).hexdigest()==r["whole_source_sha256_from_packet"]==p["whole_blob_sha256"]
 assert r["machine_dossier_sha256_verified_in_original_bytes"]==p["dossier_sha256"]
 assert r["platform_scope"]=="AUTHORED_FIRERED_SCRIPT_SOURCE_ONLY_NOT_EXECUTED"
 assert r["evidence_class"]=="PINNED_AUTHORED_SOURCE_ONLY" and r["analyst_status"]=="PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
 assert r["whole_file_semantic_coverage"] is False and r["independent_reviewer"] is None and r["independent_verdict"]=="NEEDS_REVIEW"
 assert r["license_status"]=="PENDING_INDEPENDENT_ORIGINAL_ASSET_AND_DERIVATIVE_LICENSING"
 assert r["license_evidence"]=={"repository":"pret/pokefirered","file_notice":"NO_LICENSE_NOTICE_IN_SELECTED_SCRIPT_HEADER","license_clearance":"NOT_ESTABLISHED"}
 assert r["source_observations"] and len(r["dependency_edges"])>=4 and len(r["unresolved"])>=3 and len(r["reviewer_questions"])==5
 lines=raw.decode("utf-8").splitlines()
 assert len(r["line_anchors"])>=4 and b"MapScripts::" in raw and b"\t.byte 0" in raw
 for a in r["line_anchors"]:assert a["line"]>0 and lines[a["line"]-1]==a["text"]
 assert len(r["required_source_tokens"])>=4
 for q in r["required_source_tokens"]:assert q.encode() in raw
def reject(raw,r,p):
 try:check(raw,r,p)
 except (AssertionError,KeyError,IndexError,TypeError,UnicodeDecodeError):return
 raise AssertionError("forged source evidence or approval accepted")
def main():
 d=json.loads(SPEC.read_bytes());p=json.loads(PACKET.read_bytes());rc=json.loads(RECEIPT.read_bytes())
 assert d["schema"]=="xgba.phase1.second_packet_firered_sevii_partial.v1"
 assert blob(PACKET.read_bytes())==d["source_packet_blob_sha1"]=="3ddc0b8f66c8f14351a18208fa11e823f73b1d63"
 assert rc["machine_dossier_byte_checks"]==200 and rc["phase1_gate"]=="FAIL_INCOMPLETE"
 assert rc["packet_git_blobs"][d["source_packet"]]==d["source_packet_blob_sha1"]
 assert d["new_partial_indices"]==EXPECTED and not set(EXPECTED)&set(d["prior_second_packet_indices"])
 assert d["other_p0_partial_total"]==128 and d["total_p0_partial"]==157 and d["other_p0_without_partial"]==181
 assert d["curated_p0_partial_total"]==29 and d["independent_p0_approved"]==d["independent_total_approved"]==0 and d["gate"]=="FAIL_INCOMPLETE"
 assert [r["packet_index"] for r in d["records"]]==EXPECTED
 negatives=0
 for r in d["records"]:
  n=r["packet_index"];s=r["source"];raw=read(f"https://raw.githubusercontent.com/{s['repository']}/{PIN}/{s['path']}")
  packet=p["packets"][n-100];check(raw,r,packet)
  changed=raw.replace(r["line_anchors"][0]["text"].encode(),b"XGBA_FORGED_SOURCE",1)
  assert changed!=raw;reject(changed,r,packet);negatives+=1
  for field,value in [("independent_verdict","APPROVED"),("independent_reviewer","invented"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha256_verified_in_original_bytes","0"*64),("whole_source_sha256_from_packet","0"*64),("source_observations",""),("dependency_edges",[]),("unresolved",[]),("evidence_class","STOCK_GAMEPLAY")]:
   bad=copy.deepcopy(r);bad[field]=value;reject(raw,bad,packet);negatives+=1
  for field,value in [("path","wrong.inc"),("git_blob_sha1","0"*40)]:
   bad=copy.deepcopy(r);bad["source"][field]=value;reject(raw,bad,packet);negatives+=1
  bad=copy.deepcopy(r);bad["line_anchors"][0]["line"]+=1;reject(raw,bad,packet);negatives+=1
  bad=copy.deepcopy(r);bad["license_evidence"]["license_clearance"]="CLEARED";reject(raw,bad,packet);negatives+=1
  print("P0_SECOND_PACKET_SOURCE_OK",n,s["path"],s["git_blob_sha1"])
 assert negatives==120,negatives
 print("P0_SECOND_PACKET_SEVII_PASS files=8 negatives=120 other_p0_partial=128 curated=29 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
