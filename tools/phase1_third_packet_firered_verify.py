#!/usr/bin/env python3
"""Fail-closed pinned original FireRed third-packet 200..203 source and map wiring partials."""
import copy,hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PACKET_BLOB="c998c2ea8c887968e586b1792c5207ecb5286839"
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def get(path):
 url=f"https://raw.githubusercontent.com/pret/pokefirered/{PIN}/{path}"
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-third-script"}),timeout=45) as r:return r.read()
def check(raw,mapraw,r,p,n):
 s=r["source"];i=p["identity"];w=r["map_json_static_wiring"]
 assert r["packet_index"]==n and p["priority"]=="P0" and p["independently_approved"] is False
 assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"])==(i["repository"],i["pinned_commit"],i["path"],i["git_blob_sha1"])
 assert s["repository"]=="pret/pokefirered" and s["revision"]==PIN
 assert s["url"]==f"https://github.com/pret/pokefirered/blob/{PIN}/{s['path']}"
 assert blob(raw)==s["git_blob_sha1"] and hashlib.sha256(raw).hexdigest()==r["whole_source_sha256_from_packet"]==p["whole_blob_sha256"]
 assert r["machine_dossier_sha256_reconciled_via_original_byte_receipt"]==p["dossier_sha256"]
 assert r["platform_scope"]=="AUTHORED_FIRERED_SCRIPT_SOURCE_ONLY_NOT_EXECUTED"
 assert r["evidence_class"]=="PINNED_AUTHORED_SOURCE_ONLY"
 assert r["analyst_status"]=="PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
 assert r["whole_file_semantic_coverage"] is False and r["independent_reviewer"] is None and r["independent_verdict"]=="NEEDS_REVIEW"
 assert r["license_status"]=="PENDING_INDEPENDENT_ORIGINAL_ASSET_AND_DERIVATIVE_LICENSING"
 assert r["license_evidence"]=={"repository":"pret/pokefirered","file_notice":"NO_LICENSE_NOTICE_IN_SELECTED_SCRIPT_HEADER","license_clearance":"NOT_ESTABLISHED"}
 assert r["source_observations"] and len(r["dependency_edges"])>=4 and len(r["unresolved"])>=4 and len(r["reviewer_questions"])==5
 assert len(r["line_anchors"])>=8 and len(r["required_source_tokens"])>=5
 lines=raw.decode("utf-8").splitlines()
 assert len(lines)==p["source_lines"]
 for a in r["line_anchors"]:assert 0<a["line"]<=len(lines) and lines[a["line"]-1]==a["text"]
 for token in r["required_source_tokens"]:assert token.encode() in raw
 assert blob(mapraw)==w["git_blob_sha1"] and w["path"]==s["path"].replace("scripts.inc","map.json")
 m=json.loads(mapraw)
 scripts=[v.get("script") for v in m["object_events"]]
 assert len(scripts)==w["object_event_count"] and len(w["required_event_scripts"])>=2
 for label in w["required_event_scripts"]:
  assert label in scripts and label.encode() in raw
def reject(raw,mapraw,r,p,n):
 try:check(raw,mapraw,r,p,n)
 except (AssertionError,KeyError,TypeError,IndexError,UnicodeDecodeError):return
 raise AssertionError("forged source/map or approval accepted")
def main():
 raw_packet=(BASE/"packet-0200-0299.json").read_bytes()
 packet=json.loads(raw_packet)["packets"]
 receipt=json.loads((BASE/"machine-dossier-byte-reconciliation-0200-0299-20261030.json").read_bytes())
 assert blob(raw_packet)==PACKET_BLOB
 assert receipt["machine_dossier_byte_checks"]==100 and receipt["phase1_gate"]=="FAIL_INCOMPLETE" and receipt["packet_git_blob_sha1"]==PACKET_BLOB
 d=json.loads((BASE/"remaining-p0-four-firered-powerplant-rocket-20261030.json").read_bytes())
 assert d["schema"]=="xgba.phase1.third_packet_firered_200_203_partial.v1"
 assert d["source_packet_blob_sha1"]==PACKET_BLOB and d["new_partial_indices"]==[200,201,202,203] and len(d["records"])==4
 assert d["other_p0_partial_total"]==187 and d["total_p0_partial"]==216 and d["other_p0_without_partial"]==122
 assert d["curated_p0_partial_total"]==29 and d["gate"]=="FAIL_INCOMPLETE" and d["independent_p0_approved"]==d["independent_total_approved"]==0
 negatives=0
 for n,r in zip(range(200,204),d["records"]):
  p=packet[n-200];s=r["source"];w=r["map_json_static_wiring"]
  raw=get(s["path"]);mapraw=get(w["path"]);check(raw,mapraw,r,p,n)
  changed=raw.replace(r["line_anchors"][0]["text"].encode(),b"XGBA_FORGED",1)
  assert changed!=raw;reject(changed,mapraw,r,p,n);negatives+=1
  for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","invented"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha256_reconciled_via_original_byte_receipt","0"*64),("whole_source_sha256_from_packet","0"*64),("source_observations",""),("dependency_edges",[]),("unresolved",[]),("evidence_class","STOCK_GAMEPLAY"),("platform_scope","NATIVE_FLASH"),("required_source_tokens",["XGBA_FORGED"]),("line_anchors",[]),("packet_index",n+1)):
   bad=copy.deepcopy(r);bad[field]=value;reject(raw,mapraw,bad,p,n);negatives+=1
  for field,value in (("path","wrong.inc"),("git_blob_sha1","0"*40)):
   bad=copy.deepcopy(r);bad["source"][field]=value;reject(raw,mapraw,bad,p,n);negatives+=1
  bad=copy.deepcopy(r);bad["map_json_static_wiring"]["git_blob_sha1"]="0"*40;reject(raw,mapraw,bad,p,n);negatives+=1
  bad=copy.deepcopy(r);bad["line_anchors"][0]["line"]+=1;reject(raw,mapraw,bad,p,n);negatives+=1
  print("P0_THIRD_FIRERED_SOURCE_OK",n,s["path"],s["git_blob_sha1"],"map",w["git_blob_sha1"])
 assert negatives==76,negatives
 print("P0_THIRD_FIRERED_PASS files=4 map_wiring=4 negatives=76 other_p0_partial=187 total_partial=216 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
