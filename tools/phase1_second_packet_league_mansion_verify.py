#!/usr/bin/env python3
"""Original FireRed League/Mansion/Tower: partial source only, fail-closed."""
import copy,hashlib,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"docs/phase1-review-readiness"
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
PACKET_SHA="3ddc0b8f66c8f14351a18208fa11e823f73b1d63"
DOC="remaining-p0-ten-firered-league-mansion-20261030.json"
def blob(raw):return hashlib.sha1(b"blob "+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
def get(url):
 req=urllib.request.Request(url,headers={"User-Agent":"xgba-phase1-pinned-partial"})
 with urllib.request.urlopen(req,timeout=45) as f:return f.read()
def validate(raw,r,p,n):
 s,i=r["source"],p["identity"]
 assert r["packet_index"]==n and p["priority"]=="P0" and p["independently_approved"] is False
 assert (s["repository"],s["revision"],s["path"],s["git_blob_sha1"])==(i["repository"],i["pinned_commit"],i["path"],i["git_blob_sha1"])
 assert s["repository"]=="pret/pokefirered" and s["revision"]==PIN
 assert s["url"]==f"https://github.com/pret/pokefirered/blob/{PIN}/{s['path']}"
 assert blob(raw)==s["git_blob_sha1"] and hashlib.sha256(raw).hexdigest()==r["whole_source_sha256_from_packet"]==p["whole_blob_sha256"]
 assert r["machine_dossier_sha256_verified_in_original_bytes"]==p["dossier_sha256"]
 assert r["analyst_status"]=="PARTIAL_SOURCE_GROUNDED_NO_INDEPENDENT_APPROVAL" and r["whole_file_semantic_coverage"] is False
 assert r["independent_reviewer"] is None and r["independent_verdict"]=="NEEDS_REVIEW"
 assert r["license_status"]=="PENDING_INDEPENDENT_ORIGINAL_ASSET_AND_DERIVATIVE_LICENSING"
 assert r["license_evidence"]=={"repository":"pret/pokefirered","file_notice":"NO_LICENSE_NOTICE_IN_SELECTED_SCRIPT_HEADER","license_clearance":"NOT_ESTABLISHED"}
 assert r["platform_scope"]=="AUTHORED_FIRERED_SCRIPT_SOURCE_ONLY_NOT_EXECUTED" and r["evidence_class"]=="PINNED_AUTHORED_SOURCE_ONLY"
 assert r["map_json_static_wiring"] is None and r["source_observations"] and len(r["dependency_edges"])>=4
 assert len(r["unresolved"])>=3 and len(r["reviewer_questions"])==5
 lines=raw.decode("utf-8").splitlines()
 assert len(r["line_anchors"])>=4 and b"MapScripts::" in raw and b"\t.byte 0" in raw
 assert len(set(a["line"] for a in r["line_anchors"]))==len(r["line_anchors"])
 for a in r["line_anchors"]:assert 0<a["line"]<=len(lines) and lines[a["line"]-1]==a["text"]
 assert len(r["required_source_tokens"])>=4
 for token in r["required_source_tokens"]:assert token.encode() in raw
def reject(raw,r,p,n):
 try:validate(raw,r,p,n)
 except (AssertionError,KeyError,IndexError,TypeError,UnicodeDecodeError,ValueError):return
 raise AssertionError("FORGED_SOURCE_OR_APPROVAL_ACCEPTED")
def main():
 raw=(BASE/"packet-0100-0199.json").read_bytes()
 assert blob(raw)==PACKET_SHA
 packets=json.loads(raw)["packets"]
 receipt=json.loads((BASE/"machine-dossier-byte-reconciliation-0000-0199-20261030.json").read_bytes())
 assert receipt["machine_dossier_byte_checks"]==200 and receipt["phase1_gate"]=="FAIL_INCOMPLETE"
 assert receipt["packet_git_blobs"]["docs/phase1-review-readiness/packet-0100-0199.json"]==PACKET_SHA
 d=json.loads((BASE/DOC).read_bytes())
 assert d["new_partial_indices"]==list(range(190,200))
 assert d["prior_second_packet_indices"]==list(range(100,108))+list(range(130,190))
 assert d["source_packet_blob_sha1"]==PACKET_SHA and d["source_packet"]=="docs/phase1-review-readiness/packet-0100-0199.json"
 assert d["other_p0_partial_total"]==178 and d["total_p0_partial"]==207 and d["other_p0_without_partial"]==131
 assert d["curated_p0_partial_total"]==29 and d["gate"]=="FAIL_INCOMPLETE"
 assert d["independent_p0_approved"]==d["independent_total_approved"]==0
 assert len(d["records"])==10
 sources={};negatives=0
 for n,r in zip(range(190,200),d["records"]):
  p=packets[n-100];s=r["source"]
  src=get(f"https://raw.githubusercontent.com/{s['repository']}/{PIN}/{s['path']}")
  validate(src,r,p,n);sources[n]=src
  changed=src.replace(r["line_anchors"][0]["text"].encode(),b"XGBA_FORGED_SOURCE",1)
  assert changed!=src
  reject(changed,r,p,n);negatives+=1
  for field,value in (("independent_verdict","APPROVED"),("independent_reviewer","invented"),("whole_file_semantic_coverage",True),("license_status","CLEARED"),("machine_dossier_sha256_verified_in_original_bytes","0"*64),("whole_source_sha256_from_packet","0"*64),("source_observations",""),("dependency_edges",[]),("unresolved",[]),("evidence_class","STOCK_GAMEPLAY"),("platform_scope","PHYSICAL_FLASH"),("required_source_tokens",["XGBA_NOT_IN_SOURCE"]),("packet_index",n+1)):
   bad=copy.deepcopy(r);bad[field]=value;reject(src,bad,p,n);negatives+=1
  for field,value in (("path","wrong.inc"),("git_blob_sha1","0"*40)):
   bad=copy.deepcopy(r);bad["source"][field]=value;reject(src,bad,p,n);negatives+=1
  bad=copy.deepcopy(r);bad["line_anchors"][0]["line"]+=1;reject(src,bad,p,n);negatives+=1
  bad=copy.deepcopy(r);bad["license_evidence"]["license_clearance"]="CLEARED";reject(src,bad,p,n);negatives+=1
  print("P0_LEAGUE_MANSION_SOURCE_OK",n,s["path"],s["git_blob_sha1"])
 # Authored League scene progression and Mansion switch selectors; static source only.
 assert b"setvar VAR_MAP_SCENE_POKEMON_LEAGUE, 1" in sources[194]
 assert b"map_script_2 VAR_MAP_SCENE_POKEMON_LEAGUE, 1" in sources[190]
 assert b"setvar VAR_MAP_SCENE_POKEMON_LEAGUE, 2" in sources[190]
 assert b"warp MAP_POKEMON_LEAGUE_HALL_OF_FAME" in sources[191]
 assert b"special EnterHallOfFame" in sources[192]
 for n,selector in ((195,0),(196,1),(197,2),(198,3)):
  assert ("setvar VAR_0x8004, "+str(selector)).encode() in sources[n]
  assert b"call PokemonMansion_EventScript_SecretSwitch" in sources[n]
 assert negatives==10*18,negatives
 print(f"P0_LEAGUE_MANSION_PASS files=10 negatives={negatives} source_cross_edges=3 other_p0_partial=178 curated=29 total_partial=207 approved_p0=0/338 approved_total=0/14834 gate=FAIL_INCOMPLETE")
if __name__=="__main__":main()
