#!/usr/bin/env python3
"""Verify four original mGBA Python/Qt P0 partial analyst records, fail closed."""
import copy
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
SPEC=BASE/"remaining-p0-four-python-qt-20261030.json"
PACKET=BASE/"packet-0100-0199.json"
RECEIPT=BASE/"machine-dossier-byte-reconciliation-0000-0199-20261030.json"
PIN="fd9dc5c2cbf234365068855851107e762fc6211b"
LICENSE="14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e"
EXPECTED=[101,102,104,105]
SCOPES={
101:"PYTHON_CFFI_CORE_WRAPPER_NOT_NATIVE_GAMEPLAY",
102:"PYTHON_GBA_MEMORY_VIEW_NOT_FLASH_PERSISTENCE",
104:"QT_REGISTER_VIEWER_HOST_UI_NOT_PHYSICAL_GBA_IO",
105:"QT_DESIGNER_OVERRIDE_UI_DECLARATION_NOT_RUNTIME_SAVE",
}
def git_blob(raw):
 return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()
def read(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-source-analyst"}),timeout=45) as r:return r.read()
def check(raw,r,p):
 s=r["source"]; ident=p["identity"]; n=r["packet_index"]
 assert n in EXPECTED and p["priority"]=="P0" and p["independently_approved"] is False
 assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"])==(ident["repository"],ident["pinned_commit"],ident["path"],ident["git_blob_sha1"])
 assert s["repository"]=="mgba-emu/mgba" and s["revision"]==PIN
 assert s["url"]==f"https://github.com/mgba-emu/mgba/blob/{PIN}/{s['path']}"
 assert git_blob(raw)==s["git_blob_sha1"]
 assert hashlib.sha256(raw).hexdigest()==r["whole_source_sha256_from_packet"]==p["whole_blob_sha256"]
 assert r["machine_dossier_sha256_verified_in_original_bytes"]==p["dossier_sha256"]
 assert r["evidence_class"]=="PINNED_SOURCE_ONLY" and r["platform_scope"]==SCOPES[n]
 assert r["analyst_status"]=="PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
 assert r["whole_file_semantic_coverage"] is False
 assert r["independent_reviewer"] is None and r["independent_verdict"]=="NEEDS_REVIEW"
 assert r["license_status"]=="PENDING_INDEPENDENT_FILE_SCOPE_AND_DEPENDENCY_RECONCILIATION"
 assert r["responsibilities"] and len(r["dependency_edges"])>=3 and len(r["unresolved"])>=3 and len(r["reviewer_questions"])==5
 lic=r["license_evidence"]
 assert (lic["repository"],lic["revision"],lic["license_path"],lic["license_git_blob_sha1"])==("mgba-emu/mgba",PIN,"LICENSE",LICENSE)
 assert lic["file_notice"]==("NO_FILE_LEVEL_NOTICE_IN_XML" if n==105 else "MPL-2.0_NOTICE_PRESENT")
 assert (b"Mozilla Public" not in raw[:250] if n==105 else b"Mozilla Public" in raw[:350])
 lines=raw.decode("utf-8").splitlines()
 assert len(r["line_anchors"])>=8
 for a in r["line_anchors"]:
  assert a["line"]>0 and lines[a["line"]-1]==a["text"]
def reject(raw,r,p):
 try:check(raw,r,p)
 except (AssertionError,KeyError,TypeError,IndexError,UnicodeDecodeError):return
 raise AssertionError("forged source, licensing, or independent approval accepted")
def main():
 d=json.loads(SPEC.read_bytes());p=json.loads(PACKET.read_bytes());receipt=json.loads(RECEIPT.read_bytes())
 assert d["schema"]=="xgba.phase1.remaining_p0_second_packet_partial_analyst.v2"
 assert d["source_packet_blob_sha1"]==git_blob(PACKET.read_bytes())=="3ddc0b8f66c8f14351a18208fa11e823f73b1d63"
 assert d["new_partial_indices"]==EXPECTED and d["previous_second_packet_indices"]==[100,103,106,107]
 assert d["other_p0_partial_total"]==108 and d["curated_p0_partial_total"]==29 and d["total_p0_partial"]==137 and d["other_p0_without_partial"]==201
 assert d["gate"]=="FAIL_INCOMPLETE" and d["independent_p0_approved"]==d["independent_total_approved"]==0
 assert receipt["machine_dossier_byte_checks"]==200 and receipt["phase1_gate"]=="FAIL_INCOMPLETE"
 assert receipt["packet_git_blobs"][d["source_packet"]]==d["source_packet_blob_sha1"]
 assert len(d["records"])==4 and [r["packet_index"] for r in d["records"]]==EXPECTED
 lic=read(f"https://raw.githubusercontent.com/mgba-emu/mgba/{PIN}/LICENSE")
 assert git_blob(lic)==LICENSE and b"Mozilla Public License Version 2.0" in lic
 negatives=0
 for r in d["records"]:
  n=r["packet_index"];s=r["source"];raw=read(f"https://raw.githubusercontent.com/{s['repository']}/{PIN}/{s['path']}")
  packet=p["packets"][n-100];check(raw,r,packet)
  changed=raw.replace(r["line_anchors"][0]["text"].encode(),b"XGBA_FORGED_SOURCE",1)
  assert changed!=raw;reject(changed,r,packet);negatives+=1
  for field,value in [("independent_verdict","APPROVED"),("independent_reviewer","invented"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha256_verified_in_original_bytes","0"*64),("whole_source_sha256_from_packet","0"*64),("responsibilities",""),("dependency_edges",[]),("unresolved",[]),("platform_scope","STOCK_GAMEPLAY"),("evidence_class","NATIVE_RUNTIME")]:
   bad=copy.deepcopy(r);bad[field]=value;reject(raw,bad,packet);negatives+=1
  for field,value in [("git_blob_sha1","0"*40),("path","wrong.c")]:
   bad=copy.deepcopy(r);bad["source"][field]=value;reject(raw,bad,packet);negatives+=1
  bad=copy.deepcopy(r);bad["license_evidence"]["license_git_blob_sha1"]="0"*40;reject(raw,bad,packet);negatives+=1
  bad=copy.deepcopy(r);bad["line_anchors"][0]["line"]+=1;reject(raw,bad,packet);negatives+=1
  print("P0_PYTHON_QT_SOURCE_OK",n,s["path"],s["git_blob_sha1"])
 assert negatives==64,negatives
 print("P0_PYTHON_QT_PASS files=4 negatives=64 other_p0_partial=108 curated=29 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
