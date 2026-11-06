#!/usr/bin/env python3
"""Original pinned mGBA Qt TS/Wii partial source and static build-loader checks; never approval."""
import copy
import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
PIN="fd9dc5c2cbf234365068855851107e762fc6211b"
PACKET_BLOB="3ddc0b8f66c8f14351a18208fa11e823f73b1d63"
LICENSE_BLOB="14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e"
EXPECTED=[108,109,110,111,128]
LANGS={108:"de_DE",109:"en",110:"es",111:"fr_FR"}
def blob(raw):
 return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
def get(path):
 url=f"https://raw.githubusercontent.com/mgba-emu/mgba/{PIN}/{path}"
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-pinned-qt-wii"}),timeout=45) as r:
  return r.read()
def check(raw,r,p,n):
 s=r["source"];i=p["identity"]
 assert r["packet_index"]==n and p["priority"]=="P0" and p["independently_approved"] is False
 assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"])==(i["repository"],i["pinned_commit"],i["path"],i["git_blob_sha1"])
 assert s["repository"]=="mgba-emu/mgba" and s["revision"]==PIN
 assert s["url"]==f"https://github.com/mgba-emu/mgba/blob/{PIN}/{s['path']}"
 assert blob(raw)==s["git_blob_sha1"]
 assert hashlib.sha256(raw).hexdigest()==r["whole_source_sha256_from_packet"]==p["whole_blob_sha256"]
 assert r["machine_dossier_sha256_verified_in_original_bytes"]==p["dossier_sha256"]
 assert r["analyst_status"]=="PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL"
 assert r["whole_file_semantic_coverage"] is False and r["independent_reviewer"] is None and r["independent_verdict"]=="NEEDS_REVIEW"
 assert r["license_status"].startswith("PENDING_INDEPENDENT_") and r["license_evidence"]["license_clearance"]=="NOT_ESTABLISHED"
 assert r["license_evidence"]["root_license_blob_sha1"]==LICENSE_BLOB
 assert r["source_observations"] and len(r["dependency_edges"])>=4 and len(r["unresolved"])>=4 and len(r["reviewer_questions"])==5
 assert len(r["line_anchors"])>=10 and len(r["required_source_tokens"])>=5
 lines=raw.decode("utf-8").splitlines()
 assert len(lines)==p["source_lines"]
 for a in r["line_anchors"]:
  assert isinstance(a["line"],int) and 0<a["line"]<=len(lines) and lines[a["line"]-1]==a["text"]
 for token in r["required_source_tokens"]:
  assert token.encode() in raw
 if n in LANGS:
  assert r["platform_scope"]=="QT_LINGUIST_TRANSLATION_ASSET_SOURCE_ONLY_NOT_COMPILED"
  assert r["evidence_class"]=="PINNED_TRANSLATION_ASSET_SOURCE_ONLY"
  assert r["license_evidence"]["file_notice"]=="NO_FILE_LEVEL_LICENSE_HEADER_IN_TS_XML"
  root=ET.fromstring(raw)
  assert root.tag=="TS" and root.attrib.get("version")=="2.1" and root.attrib.get("language")==LANGS[n]
  assert len(root.findall("context"))>10 and len(root.findall(".//message"))>100
  assert lines[0].startswith('<?xml version="1.0"')
 else:
  assert n==128 and r["platform_scope"]=="WII_HOST_FRONTEND_SOURCE_ONLY_NOT_COMPILED"
  assert r["evidence_class"]=="PINNED_WII_FRONTEND_SOURCE_ONLY"
  assert r["license_evidence"]["file_notice"]=="MPL_2_0_SOURCE_HEADER_LINES_1_TO_5"
  assert b"Mozilla Public" in raw[:240] and b"#include <wiiuse/wpad.h>" in raw
def reject(raw,r,p,n):
 try:check(raw,r,p,n)
 except (AssertionError,KeyError,TypeError,IndexError,UnicodeDecodeError,ET.ParseError):return
 raise AssertionError("forged source, license or approval accepted")
def check_closure(d,cm,main):
 assert d["schema"]=="xgba.phase1.mgba_qt_translation_static_build_loader.v1"
 assert d["pin"]==PIN and d["evidence_class"]=="PINNED_BUILD_RULE_AND_LOADER_SOURCE_ONLY"
 assert d["compiled_qm_verified"] is d["resource_bundle_verified"] is d["native_qt_locale_runtime_verified"] is d["independent_approved"] is False
 assert d["licensing_clearance"]=="PENDING_INDEPENDENT" and len(d["limitations"])>=4
 assert len(d["edges"])==4 and [e["status"] for e in d["edges"]]==["STATIC_SOURCE_RULE_ONLY","STATIC_BUILD_RULE_ONLY","STATIC_BUILD_RULE_ONLY","STATIC_LOADER_SOURCE_ONLY"]
 for name,raw in (("build_source",cm),("consumer_source",main)):
  s=d[name];assert blob(raw)==s["git_blob_sha1"] and len(s["line_anchors"])>=5
  lines=raw.decode("utf-8").splitlines()
  for a in s["line_anchors"]:
   assert lines[a["line"]-1]==a["text"]
 assert b"qt_add_translation(" in cm and b"qt5_add_translation(" in cm and b"qt_add_resources(" in cm and b"qt5_add_resources(" in cm
 assert b"langTranslator.load(locale, binaryName" in main and b"application.installTranslator(&langTranslator)" in main
def reject_closure(d,cm,main):
 try:check_closure(d,cm,main)
 except (AssertionError,KeyError,TypeError,IndexError):return
 raise AssertionError("forged static compiled/runtime closure accepted")
def main():
 packet_raw=(BASE/"packet-0100-0199.json").read_bytes()
 packet=json.loads(packet_raw)["packets"]
 receipt=json.loads((BASE/"machine-dossier-byte-reconciliation-0000-0199-20261030.json").read_bytes())
 assert blob(packet_raw)==PACKET_BLOB and receipt["machine_dossier_byte_checks"]==200 and receipt["phase1_gate"]=="FAIL_INCOMPLETE"
 assert receipt["packet_git_blobs"]["docs/phase1-review-readiness/packet-0100-0199.json"]==PACKET_BLOB
 d=json.loads((BASE/"remaining-p0-five-qt-wii-20261030.json").read_bytes())
 assert d["schema"]=="xgba.phase1.second_packet_qt_wii_partial.v1" and d["source_packet_blob_sha1"]==PACKET_BLOB
 assert d["new_partial_indices"]==EXPECTED and len(d["records"])==5
 assert d["other_p0_partial_total"]==183 and d["total_p0_partial"]==212 and d["other_p0_without_partial"]==126
 assert d["curated_p0_partial_total"]==29 and d["gate"]=="FAIL_INCOMPLETE" and d["independent_p0_approved"]==d["independent_total_approved"]==0
 assert set(d["prior_second_packet_indices"])==set(range(100,108))|set(range(130,200))
 assert blob(get("LICENSE"))==LICENSE_BLOB
 negatives=0
 for r,n in zip(d["records"],EXPECTED):
  p=packet[n-100]
  raw=get(r["source"]["path"])
  check(raw,r,p,n)
  changed=raw.replace(r["line_anchors"][0]["text"].encode(),b"XGBA_FORGED_SOURCE",1)
  assert changed!=raw
  reject(changed,r,p,n);negatives+=1
  for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","fabricated"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha256_verified_in_original_bytes","0"*64),("whole_source_sha256_from_packet","0"*64),("source_observations",""),("dependency_edges",[]),("unresolved",[]),("evidence_class","STOCK_GAMEPLAY"),("platform_scope","NATIVE_GBA_FLASH"),("packet_index",n+1),("required_source_tokens",["XGBA_NOT_IN_SOURCE"]),("line_anchors",[])):
   bad=copy.deepcopy(r);bad[field]=value;reject(raw,bad,p,n);negatives+=1
  for field,value in (("path","wrong.ts"),("git_blob_sha1","0"*40)):
   bad=copy.deepcopy(r);bad["source"][field]=value;reject(raw,bad,p,n);negatives+=1
  bad=copy.deepcopy(r);bad["license_evidence"]["license_clearance"]="CLEARED";reject(raw,bad,p,n);negatives+=1
  bad=copy.deepcopy(r);bad["line_anchors"][0]["line"]+=1;reject(raw,bad,p,n);negatives+=1
  print("P0_QT_WII_SOURCE_OK",n,r["source"]["path"],r["source"]["git_blob_sha1"])
 assert negatives==95,negatives
 c=json.loads((BASE/"qt-translation-static-build-loader-20261030.json").read_bytes())
 cm=get(c["build_source"]["path"]);ui=get(c["consumer_source"]["path"])
 check_closure(c,cm,ui)
 closure_negatives=0
 for field,value in (("compiled_qm_verified",True),("resource_bundle_verified",True),("native_qt_locale_runtime_verified",True),("independent_approved",True),("licensing_clearance","CLEARED"),("edges",[])):
  bad=copy.deepcopy(c);bad[field]=value;reject_closure(bad,cm,ui);closure_negatives+=1
 for field in ("build_source","consumer_source"):
  bad=copy.deepcopy(c);bad[field]["git_blob_sha1"]="0"*40;reject_closure(bad,cm,ui);closure_negatives+=1
 assert closure_negatives==8
 print("P0_QT_WII_PASS files=5 negatives=95 static_closure_negatives=8 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
