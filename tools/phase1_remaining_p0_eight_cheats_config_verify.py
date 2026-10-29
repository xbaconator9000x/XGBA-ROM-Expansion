#!/usr/bin/env python3
"""Exact pinned source analyst evidence for 8 disjoint P0 files; NO independent approvals."""
import copy,hashlib,json,urllib.request
from pathlib import Path
from phase1_remaining_p0_eight_verify import git_blob,verify
ROOT=Path(__file__).resolve().parents[1]
SPEC=ROOT/"docs/phase1-review-readiness/remaining-p0-eight-cheats-config-20261029.json"
EXPECTED=[44,81,86,87,88,89,90,91]
MGBAPIN="fd9dc5c2cbf234365068855851107e762fc6211b"
PORYPIN="26b919d7ff4b54152de010abd5bf344af2ebe116"
LICENSES={
 "mgba-emu/mgba":("LICENSE","14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e",b"Mozilla Public License Version 2.0"),
 "huderlem/porymap":("LICENSE.md","65c5ca88a67c30becee01c5a8816d964b03862f9",b"GNU LESSER GENERAL PUBLIC LICENSE")
}
SCOPES={"44":"PORYMAP_QT_CONFIG_SOURCE_NOT_GUI_RUNTIME","81":"GAME_BOY_GBX_TEST_ONLY_NOT_GBA_FLASH","86":"GBA_UNLICENSED_MULTICART_SOURCE_NOT_STOCK_FIRERED","87":"GBA_VFAME_BOOTLEG_SOURCE_NOT_STOCK_FIRERED","88":"GBA_CHEAT_HOST_SOURCE_NOT_STOCK_GAMEPLAY","89":"GBA_CODEBREAKER_HOST_SOURCE_NOT_STOCK_GAMEPLAY","90":"GBA_GAMESHARK_HOST_SOURCE_NOT_STOCK_GAMEPLAY","91":"GBA_PARV3_HOST_SOURCE_NOT_STOCK_GAMEPLAY"}
def read_url(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-p0-source-review"}),timeout=45) as r:return r.read()
def verify_extended(raw,rec,packet):
 verify(raw,rec,packet)
 assert hashlib.sha256(raw).hexdigest()==rec["whole_source_sha256_from_machine_packet_unverified"]==packet["whole_blob_sha256"]
 assert rec["platform_scope"]==SCOPES[str(rec["packet_index"])]
 assert rec["evidence_class"]=="PINNED_SOURCE_ONLY"
 assert len(rec["reviewer_questions"])==5
 assert len(rec["dependency_edges"])>=2 and len(rec["unresolved"])>=2
 assert rec["license_status"]=="PENDING_INDEPENDENT_FILE_SCOPE_AND_DEPENDENCY_RECONCILIATION"
 repo=rec["source"]["repository"]; lic=rec["license_evidence"]; path,sha,notice=LICENSES[repo]
 assert lic["repository"]==repo and lic["revision"]==rec["source"]["revision"]
 assert lic["license_path"]==path and lic["license_git_blob_sha1"]==sha
 assert notice.decode() in lic["observed_repository_license"]
 if repo=="mgba-emu/mgba":
  assert b"Mozilla Public License" in raw and lic["file_notice"]=="Mozilla Public License, v. 2.0."
 else:
  assert lic["file_notice"]=="NOT_PRESENT_IN_SCOPED_SOURCE_HEADER"
def reject(raw,rec,packet):
 try:verify_extended(raw,rec,packet)
 except (AssertionError,KeyError,IndexError,TypeError,UnicodeDecodeError):return
 raise AssertionError("forged evidence accepted")
def main():
 p=json.loads(SPEC.read_text())
 assert p["schema"]=="xgba.phase1.remaining_p0_partial_analyst_batch.v11"
 assert p["new_partial_indices"]==EXPECTED and p["remaining_p0_partial_total"]==94
 assert len(p["previous_partial_indices"])==86 and not(set(EXPECTED)&set(p["previous_partial_indices"]))
 assert len(set(p["previous_partial_indices"]))==86
 assert len(p["records"])==p["partial_source_inspected"]==8
 assert p["curated_29_source_inspected"]==29 and p["gate"]=="FAIL_INCOMPLETE"
 assert p["independent_p0_approved"]==p["independent_total_approved"]==0
 packet_bytes=(ROOT/p["source_packet"]).read_bytes()
 assert git_blob(packet_bytes)==p["source_packet_blob_sha1"]
 packets=json.loads(packet_bytes)["packets"]
 for repo,(path,sha,notice) in LICENSES.items():
  pin=MGBAPIN if repo=="mgba-emu/mgba" else PORYPIN
  raw=read_url(f"https://raw.githubusercontent.com/{repo}/{pin}/{path}")
  assert git_blob(raw)==sha and notice in raw
 negatives=0
 for rec in p["records"]:
  i=rec["packet_index"];assert i in EXPECTED
  src=rec["source"]
  assert src["revision"]==(MGBAPIN if src["repository"]=="mgba-emu/mgba" else PORYPIN)
  raw=read_url("https://raw.githubusercontent.com/{}/{}/{}".format(src["repository"],src["revision"],src["path"]))
  verify_extended(raw,rec,packets[i])
  mutated=raw.replace(rec["line_anchors"][0]["text"].encode(),b"XGBA_NEGATIVE_SOURCE",1)
  assert mutated!=raw;reject(mutated,rec,packets[i]);negatives+=1
  for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","fabricated"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha1","fabricated"),("machine_dossier_sha256_unverified","0"*64),("responsibilities",""),("dependency_edges",[]),("unresolved",[]),("platform_scope","FIRERED_STOCK_GAMEPLAY_PROVEN"),("evidence_class","NATIVE_RUNTIME_PROVEN"),("whole_source_sha256_from_machine_packet_unverified","0"*64)):
   bad=copy.deepcopy(rec);bad[field]=value;reject(raw,bad,packets[i]);negatives+=1
  for field,value in (("path","wrong.c"),("git_blob_sha1","0"*40)):
   bad=copy.deepcopy(rec);bad["source"][field]=value;reject(raw,bad,packets[i]);negatives+=1
  for field,value in (("line",rec["line_anchors"][0]["line"]+1),("text","forged source anchor")):
   bad=copy.deepcopy(rec);bad["line_anchors"][0][field]=value;reject(raw,bad,packets[i]);negatives+=1
  bad=copy.deepcopy(rec);bad["license_evidence"]["license_git_blob_sha1"]="0"*40
  reject(raw,bad,packets[i]);negatives+=1
  print("P0_CHEATS_CONFIG_SOURCE_OK",i,src["path"],src["git_blob_sha1"])
 assert negatives==144
 print("P0_CHEATS_CONFIG_PASS files=8 negatives=144 curated=29 remaining_p0_partial=94 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
