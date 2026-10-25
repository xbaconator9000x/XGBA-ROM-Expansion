#!/usr/bin/env python3
"""Phase 1 v5: pinned Porymap/Poryscript -> FireRed ABI obligations and review queue."""
from __future__ import annotations
import collections, copy, csv, gzip, hashlib, io, json, re, subprocess, sys
from pathlib import Path
import phase1_cpu_matrix_review_scheduler as v4
import phase1_additive_review_scheduler as v2

PACKET = Path("semantic-snapshots/curated/crossrepo_authoring_abi_additive_2026-10-26.json")
OUT = Path("audit-output/architecture_semantic_review_queue_additive_v5.csv.gz")
SUMMARY = Path("audit-output/architecture_semantic_review_priority_additive_v5.json")
EVIDENCE = Path("audit-output/crossrepo_authoring_abi_source_evidence.json")
TIER = "A0E_PINNED_CROSSREPO_AUTHORING_ABI_ADDITIVE"
PINS = {"huderlem/porymap":"26b919d7ff4b54152de010abd5bf344af2ebe116","huderlem/poryscript":"c32481161c767b25a3425fa9f1f8729927ff3d55","pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982"}
BLOBS = {
 ("huderlem/porymap","src/core/block.cpp"):"fc4fe774ccd75673c549734055907eb7c79c0fc2",
 ("huderlem/porymap","src/core/blockdata.cpp"):"5fcd4e32b115790f5a86b5cef5726cace8005017",
 ("huderlem/porymap","src/core/maplayout.cpp"):"44616ab6c9c3ea9b04eff011586b7ec29183588f",
 ("huderlem/poryscript","emitter/emitter.go"):"d35843ef29929ead47351646d7a33dd5c692b850",
 ("pret/pokefirered","include/global.fieldmap.h"):"e2828ec0cb1439718e830fbef4366770b3b77b1c",
 ("pret/pokefirered","src/fieldmap.c"):"41567772299000ba5855419e5c39ad9373a34c20",
 ("pret/pokefirered","asm/macros/map.inc"):"83ef472c926ce767c9133ab9bd6922280b38bb2d",
 ("pret/pokefirered","ld_script.ld"):"9a4b45031e93c1e1da8186d8c697332710526048",
}
# Each contract must match within its exact source interval, not elsewhere in a file.
CHECKS = [
 ("PMAP_DEFAULT_MASKS","huderlem/porymap","src/core/block.cpp",8,10,r"BitPacker\(0x3FF\).*?BitPacker\(0xC00\).*?BitPacker\(0xF000\)"),
 ("PMAP_CONFIGURABLE_MASKS","huderlem/porymap","src/core/block.cpp",43,52,r"bitsMetatileId\.pack.*?bitsCollision\.pack.*?bitsElevation\.pack.*?projectConfig\.blockMetatileIdMask.*?projectConfig\.blockCollisionMask.*?projectConfig\.blockElevationMask"),
 ("PMAP_LE16_WRITER","huderlem/porymap","src/core/blockdata.cpp",3,10,r"uint16_t word = block\.rawValue\(\);.*?word & 0xff.*?word >> 8"),
 ("PMAP_RESIZE_ON_DIMENSION_MISMATCH","huderlem/porymap","src/core/maplayout.cpp",576,604,r"this->width \* this->height.*?this->blockdata\.count\(\) != expectedSize.*?this->blockdata\.resize\(expectedSize\)"),
 ("PMAP_ODD_BYTE_DROPPED","huderlem/porymap","src/core/maplayout.cpp",612,626,r"\(i \+ 1\) < data\.length\(\); i \+= 2.*?blockdata\.append\(word\)"),
 ("FIRERED_FIXED_GRID_MASKS","pret/pokefirered","include/global.fieldmap.h",4,11,r"MAPGRID_METATILE_ID_MASK 0x03FF.*?MAPGRID_COLLISION_MASK\s+0x0C00.*?MAPGRID_ELEVATION_MASK\s+0xF000"),
 ("FIRERED_NATIVE_OBJECT_ABI","pret/pokefirered","include/global.fieldmap.h",110,134,r"struct ObjectEventTemplate.*?const u8 \*script;.*?u16 flagId;"),
 ("FIRERED_LAYOUT_16BIT_MAP","pret/pokefirered","src/fieldmap.c",103,127,r"VMap\.Xsize = mapLayout->width \+ MAP_OFFSET_W;.*?VMap\.Xsize \* VMap\.Ysize <= VIRTUAL_MAP_SIZE.*?CpuCopy16\(map, dest, width \* sizeof\(u16\)\)"),
 ("PSCRIPT_MAP_SCRIPT_EMIT","huderlem/poryscript","emitter/emitter.go",112,145,r"map_script %s, %s.*?\\t\.byte 0.*?map_script_2 %s, %s, %s.*?\\t\.2byte 0"),
 ("FIRERED_MAP_SCRIPT_MACROS","pret/pokefirered","asm/macros/map.inc",9,20,r"\.macro map_script type:req, script:req.*?\.byte \\type.*?\.4byte \\script.*?\.macro map_script_2.*?\.2byte \\var.*?\.2byte \\compare.*?\.4byte \\script"),
 ("FIRERED_OBJECT_EVENT_MACRO","pret/pokefirered","asm/macros/map.inc",22,38,r"\.macro object_event .*?\.4byte \\script.*?\.2byte \\event_flag.*?\.space 2"),
 ("FIRERED_LINKER_ROM_32M","pret/pokefirered","ld_script.ld",4,9,r"ROM\s+\(rx\)\s*:\s*ORIGIN = 0x8000000, LENGTH = 32M"),
]
EDGES = {"PMAP_MASKS_TO_FIRERED_GRID":{"producer":{"repository":"huderlem/porymap","path":"src/core/block.cpp","start":8,"end":10},"consumer":{"repository":"pret/pokefirered","path":"include/global.fieldmap.h","start":4,"end":11}},"PMAP_CONFIG_MASKS_ARE_NOT_NATIVE":{"producer":{"repository":"huderlem/porymap","path":"src/core/block.cpp","start":43,"end":52},"consumer":{"repository":"pret/pokefirered","path":"include/global.fieldmap.h","start":4,"end":11}},"PMAP_LE16_SERIALIZATION_TO_MAP_COPY":{"producer":{"repository":"huderlem/porymap","path":"src/core/blockdata.cpp","start":3,"end":10},"consumer":{"repository":"pret/pokefirered","path":"src/fieldmap.c","start":103,"end":127}},"PMAP_LENGTH_RECONCILIATION_IS_LOSSY":{"producer":{"repository":"huderlem/porymap","path":"src/core/maplayout.cpp","start":576,"end":626},"consumer":{"repository":"pret/pokefirered","path":"src/fieldmap.c","start":103,"end":127}},"PSCRIPT_MAP_TABLE_TO_ASSEMBLER_MACROS":{"producer":{"repository":"huderlem/poryscript","path":"emitter/emitter.go","start":112,"end":145},"consumer":{"repository":"pret/pokefirered","path":"asm/macros/map.inc","start":9,"end":20}},"MAP_EVENT_MACRO_TO_NATIVE_OBJECT_ABI":{"producer":{"repository":"pret/pokefirered","path":"asm/macros/map.inc","start":22,"end":38},"consumer":{"repository":"pret/pokefirered","path":"include/global.fieldmap.h","start":110,"end":134}},"LINKED_SCRIPT_POINTERS_REMAIN_ROM_BOUNDED":{"producer":{"repository":"pret/pokefirered","path":"asm/macros/map.inc","start":9,"end":20},"consumer":{"repository":"pret/pokefirered","path":"ld_script.ld","start":4,"end":9}}}
ROOTS = {"huderlem/porymap":Path("upstream/porymap"),"huderlem/poryscript":Path("upstream/poryscript"),"pret/pokefirered":Path("upstream/pokefirered")}

def fail(message):
 raise ValueError(message)

def sha256(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()

def gitblob(raw):
 return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def validate_packet(doc):
 if (doc.get("schema")!="xgba.phase1.crossrepo_authoring_abi_additive.v1"
     or doc.get("pinned_revisions")!=PINS
     or doc.get("original_curated_count_preserved")!=29
     or doc.get("previous_candidates_pending")!=37
     or doc.get("additional_source_files")!=1
     or doc.get("independent_whole_file_approvals")!=0
     or doc.get("phase1_mapping_complete") is not False):
  fail("Packet provenance, review status or schema drift")
 c=doc.get("candidate",{})
 if (c.get("repository")!="pret/pokefirered" or c.get("path")!="asm/macros/map.inc"
     or c.get("git_blob_sha1")!=BLOBS[("pret/pokefirered","asm/macros/map.inc")]
     or c.get("source_lines")!=[1,160] or c.get("independent_signoff") is not False
     or not isinstance(c.get("semantic_roles"),list) or len(c["semantic_roles"])<2
     or not isinstance(c.get("unresolved"),list) or len(c["unresolved"])<2):
  fail("Candidate identity, obligations or signoff drift")
 edges=doc.get("cross_source_contracts")
 if not isinstance(edges,list) or len(edges)!=len(EDGES):fail("Missing dependency")
 seen=set()
 for edge in edges:
  key=edge.get("id")
  if key not in EDGES or key in seen:fail("Unknown or duplicate edge")
  for side in ("producer","consumer"):
   if edge.get(side)!=EDGES[key][side]:fail("Changed source dependency endpoint")
   end=edge[side]
   if (end["repository"],end["path"]) not in BLOBS or not any(
      repo==end["repository"] and path==end["path"]
      and max(start,end["start"])<=min(stop,end["end"])
      for _,repo,path,start,stop,_ in CHECKS):
    fail("Dependency has no bounded source expression")
  if (edge.get("proof_level")!="PINNED_SOURCE_INTERPRETATION_ONLY"
      or not isinstance(edge.get("meaning"),str) or len(edge["meaning"])<50):
   fail("Dependency missing interpretation or claims approval")
  seen.add(key)
 return True

def validate_queue(rows,original,base,gate,previous,doc):
 validate_packet(doc)
 if (len(rows)!=14834 or len(original)!=14834
     or len({(r["repo"],r["path"]) for r in rows})!=14834
     or len({(r["repo"],r["path"]) for r in original})!=14834
     or collections.Counter(r["priority"] for r in rows)["P0"]!=338
     or previous.get("decision")!="FAIL_INCOMPLETE"
     or previous.get("total_candidates_pending")!=37
     or previous.get("independent_whole_file_approvals")!=0
     or previous.get("output_queue_sha256")!=sha256(v4.TARGET)
     or previous.get("source_queue_sha256")!=sha256(v2.SOURCE)
     or base.get("candidate_file_count")!=29
     or base.get("independent_review_approvals")!=0
     or any(c.get("independent_whole_file_signoff") is not False for c in base["candidate_files"])
     or gate.get("decision")!="FAIL_INCOMPLETE"
     or gate.get("approved_semantic_dispositions")!=0):
  fail("Original census, v4 provenance or fail-closed gate drift")
 index={(r["repo"],r["path"]):r for r in rows}
 original_index={(r["repo"],r["path"]):r for r in original}
 if set(index)!=set(original_index):fail("Source inventory drift")
 for key,row in index.items():
  old=original_index[key]
  if any(row[field]!=old[field] for field in ("repo","path","blob_sha","priority","machine_review_status")):
   fail("Source identity, priority or review status drift")
  if row["source_queue_priority_preserved"]!=old["priority"] or row["source_queue_machine_review_status_preserved"]!=old["machine_review_status"]:
   fail("Source provenance drift")
 for key,sha in BLOBS.items():
  if key not in index or index[key]["blob_sha"]!=sha:fail("Pinned source queue hash drift: "+str(key))
 key=("pret/pokefirered","asm/macros/map.inc")
 if index[key]["curated_candidate_registry"] or any((c["repository"],c["source_path"])==key for c in base["candidate_files"]):
  fail("Candidate double-assigned")
 counts=collections.Counter(r["architecture_review_tier"] for r in rows)
 if (counts[v2.ORIGINAL_TIER]!=29 or counts[v2.EXTRA_TIER]!=2
     or counts["A0C_PINNED_MGBA_EEPROM_SAVESTATE_ADDITIVE"]!=2
     or counts[v4.TIER]!=4 or counts["A3_P0_GAMEPLAY_SCRIPT_FIXTURE"]!=163):
  fail("Earlier candidate tiers drift")
 return key

def negative_controls(doc,rows,original,base,gate,previous):
 cases=[
  ("packet-approval",lambda d,r,o,b,g,p:d.update(independent_whole_file_approvals=1)),
  ("packet-completion",lambda d,r,o,b,g,p:d.update(phase1_mapping_complete=True)),
  ("candidate-signoff",lambda d,r,o,b,g,p:d["candidate"].update(independent_signoff=True)),
  ("source-hash",lambda d,r,o,b,g,p:d["candidate"].update(git_blob_sha1="0"*40)),
  ("edge-endpoint",lambda d,r,o,b,g,p:d["cross_source_contracts"][0]["producer"].update(start=1,end=2)),
  ("false-proof",lambda d,r,o,b,g,p:d["cross_source_contracts"][0].update(proof_level="APPROVED")),
  ("v4-digest",lambda d,r,o,b,g,p:p.update(output_queue_sha256="0"*64)),
  ("original-signoff",lambda d,r,o,b,g,p:b["candidate_files"][0].update(independent_whole_file_signoff=True)),
  ("source-status",lambda d,r,o,b,g,p:r[0].update(machine_review_status="APPROVED")),
  ("double-assignment",lambda d,r,o,b,g,p:next(x for x in r if x["repo"]=="pret/pokefirered" and x["path"]=="asm/macros/map.inc").update(curated_candidate_registry="FORGED")),
 ]
 for name,mutation in cases:
  args=copy.deepcopy((doc,rows,original,base,gate,previous))
  mutation(*args)
  try:validate_queue(args[1],args[2],args[3],args[4],args[5],args[0])
  except ValueError:continue
  raise AssertionError("Fail-open v5 control: "+name)
 return len(cases)

def verify_sources():
 sources={}
 for repo,root in ROOTS.items():
  actual=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()
  if actual!=PINS[repo]:fail("Upstream checkout not at exact pinned revision: "+repo)
 for (repo,path),expected in BLOBS.items():
  raw=(ROOTS[repo]/path).read_bytes()
  if gitblob(raw)!=expected:fail("Git blob mismatch: "+repo+"/"+path)
  sources[(repo,path)]=raw.decode("utf-8")
 evidence=[]
 for ident,repo,path,start,end,pattern in CHECKS:
  lines=sources[(repo,path)].splitlines(keepends=True)
  if end>len(lines) or not re.search(pattern,"".join(lines[start-1:end]),re.S):
   fail("Missing bounded source contract: "+ident)
  evidence.append({"contract_id":ident,"repository":repo,"path":path,"lines":[start,end],
                   "git_blob_sha1":BLOBS[(repo,path)]})
 return evidence

def main():
 doc=json.loads(PACKET.read_text())
 validate_packet(doc)
 source_evidence=verify_sources()
 v4.main()
 with gzip.open(v4.TARGET,"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
 with gzip.open(v2.SOURCE,"rt",encoding="utf-8",newline="") as f:original=list(csv.DictReader(f))
 base=json.loads(v2.BASE.read_text())
 gate=json.loads(v2.GATE.read_text())
 previous=json.loads(v4.SUMMARY.read_text())
 key=validate_queue(rows,original,base,gate,previous,doc)
 negative=negative_controls(doc,rows,original,base,gate,previous)
 for row in rows:
  if (row["repo"],row["path"])==key:
   row.update(architecture_review_tier=TIER,
              architecture_review_reason="Pinned Poryscript/Porymap to FireRed map assembler ABI; independent review pending",
              curated_semantic_roles=",".join(doc["candidate"]["semantic_roles"]),
              curated_candidate_registry=str(PACKET))
  if row["architecture_review_tier"]==TIER and (row["repo"],row["path"])!=key:
   fail("Unexpected new tier assignment")
 rank={v2.ORIGINAL_TIER:0,v2.EXTRA_TIER:1,
       "A0C_PINNED_MGBA_EEPROM_SAVESTATE_ADDITIVE":2,v4.TIER:3,TIER:4,
       "A1_ARCHITECTURE_CRITICAL_P0":5,"A2_OTHER_P0":6,
       "A3_P0_GAMEPLAY_SCRIPT_FIXTURE":7,"A4_P1_QUEUE":8,
       "A5_P2_QUEUE":9,"A6_P3_QUEUE":10}
 counts=collections.Counter(r["architecture_review_tier"] for r in rows)
 if (counts[TIER]!=1 or len(rows)!=14834 or
     any(r["architecture_review_tier"] not in rank for r in rows)):
  fail("v5 tier or census mismatch")
 rows.sort(key=lambda r:(rank[r["architecture_review_tier"]],r["repo"],r["path"]))
 OUT.parent.mkdir(parents=True,exist_ok=True)
 with OUT.open("wb") as f:
  with gzip.GzipFile(filename="",mode="wb",fileobj=f,mtime=0) as g:
   with io.TextIOWrapper(g,encoding="utf-8",newline="") as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(rows)
 result={"schema":"xgba.phase1.architecture_review_additive.v5",
         "source_queue_sha256":sha256(v2.SOURCE),
         "stage4_queue_sha256":sha256(v4.TARGET),
         "source_packet_sha256":sha256(PACKET),
         "output_queue_sha256":sha256(OUT),
         "source_files_preserved":14834,"original_P0_preserved":338,
         "original_curated_pending":29,"previous_additive_pending":8,
         "authoring_abi_additive_pending":1,"total_candidates_pending":38,
         "source_contracts_verified":len(source_evidence),
         "cross_source_dependencies":len(doc["cross_source_contracts"]),
         "additional_negative_controls_passed":negative,
         "tier_counts":dict(sorted(counts.items())),
         "independent_whole_file_approvals":0,"phase1_mapping_complete":False,
         "decision":"FAIL_INCOMPLETE",
         "limitations":["Source contract checks are not independent whole-file reviews",
                        "No compiled ABI or editor round-trip certification",
                        "No Phase 2 implementation or mutation of original source queue"]}
 SUMMARY.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 EVIDENCE.write_text(json.dumps({"schema":"xgba.phase1.crossrepo_authoring_abi_source.v1",
   "pinned_revisions":PINS,"verified_blobs":len(BLOBS),
   "verified_source_contracts":source_evidence,
   "cross_source_contracts":doc["cross_source_contracts"],
   "independent_whole_file_approvals":0,"decision":"FAIL_INCOMPLETE"},indent=2,sort_keys=True)+"\n")
 print("Phase 1 v5: 8 pinned blobs; %d expressions; %d edges; %d negative controls; 14,834 rows; 38 pending; 0 approved; FAIL_INCOMPLETE" % (len(source_evidence),len(EDGES),negative))

if __name__=="__main__":
 try:main()
 except Exception as error:
  print("Phase 1 v5 FAILED:",error,file=sys.stderr);sys.exit(2)
