#!/usr/bin/env python3
"""Fail-closed v4 semantic review queue; additive CPU/Matrix header candidates."""
from __future__ import annotations
import collections, copy, csv, gzip, hashlib, io, json, sys
from pathlib import Path
import phase1_crosspacket_review_scheduler as v3
import phase1_additive_review_scheduler as v2
import verify_mgba_cpu_matrix_abi_additive as cpu

TARGET=Path("audit-output/architecture_semantic_review_queue_additive_v4.csv.gz")
SUMMARY=Path("audit-output/architecture_semantic_review_priority_additive_v4.json")
TIER="A0D_PINNED_MGBA_CPU_MATRIX_ABI_ADDITIVE"

def reject(msg):raise ValueError(msg)

def validate(rows,original,base,gate,doc,previous):
 cpu.validate_snapshot(doc,original,base,gate)
 if (previous.get("decision")!="FAIL_INCOMPLETE"
     or previous.get("total_candidates_pending")!=33
     or previous.get("independent_whole_file_approvals")!=0
     or previous.get("output_queue_sha256")!=hashlib.sha256(v3.TARGET.read_bytes()).hexdigest()
     or previous.get("source_queue_sha256")!=hashlib.sha256(v2.SOURCE.read_bytes()).hexdigest()):
  reject("v3 queue evidence, source provenance or gate drift")
 if len(rows)!=14834 or len(original)!=14834:reject("Source rows truncated")
 index={(r["repo"],r["path"]):r for r in rows}
 source={(r["repo"],r["path"]):r for r in original}
 if len(index)!=14834 or set(index)!=set(source):reject("Source identity missing/duplicated")
 counts=collections.Counter(r["architecture_review_tier"] for r in rows)
 if (counts[v2.ORIGINAL_TIER]!=29 or counts[v2.EXTRA_TIER]!=2
     or counts[v3.EEPROM_TIER]!=2 or counts["A3_P0_GAMEPLAY_SCRIPT_FIXTURE"]!=163):
  reject("Previously curated assignments drifted")
 new={c["path"]:c for c in doc["candidates"]}
 for key,row in index.items():
  old=source[key]
  if (row["blob_sha"]!=old["blob_sha"] or row["priority"]!=old["priority"]
      or row["machine_review_status"]!=old["machine_review_status"]
      or row["source_queue_priority_preserved"]!=old["priority"]
      or row["source_queue_machine_review_status_preserved"]!=old["machine_review_status"]):
   reject("Original source identity/priority/status drift: "+str(key))
  if row["architecture_review_tier"]==TIER:reject("v4 tier already present")
  if key[0]=="mgba-emu/mgba" and key[1] in new:
   if row["curated_candidate_registry"]:reject("v4 source double-assigned")
   if row["blob_sha"]!=new[key[1]]["git_blob_sha1"]:reject("v4 source blob drift")
 if len({("mgba-emu/mgba",p) for p in new} & set(index))!=4:
  reject("Missing additive source")
 return new

def negative_controls(rows,original,base,gate,doc,previous):
 cases=[
  ("gate-approval",lambda r,o,b,g,d,s:g.update(approved_semantic_dispositions=1)),
  ("packet-approval",lambda r,o,b,g,d,s:d.update(independent_whole_file_approvals=1)),
  ("v3-digest",lambda r,o,b,g,d,s:s.update(output_queue_sha256="0"*64)),
  ("v3-false-approval",lambda r,o,b,g,d,s:s.update(independent_whole_file_approvals=1)),
  ("new-source-hash",lambda r,o,b,g,d,s:next(x for x in r if x["repo"]=="mgba-emu/mgba" and x["path"]=="include/mgba/internal/arm/arm.h").update(blob_sha="0"*40)),
  ("source-status",lambda r,o,b,g,d,s:r[0].update(machine_review_status="APPROVED")),
  ("prior-tier",lambda r,o,b,g,d,s:next(x for x in r if x["repo"]=="mgba-emu/mgba" and x["path"]=="src/gba/savedata.c").update(architecture_review_tier="A5_P2_QUEUE")),
  ("double-assigned",lambda r,o,b,g,d,s:next(x for x in r if x["repo"]=="mgba-emu/mgba" and x["path"]=="include/mgba/internal/gba/memory.h").update(curated_candidate_registry="FORGED")),
  ("edge-drift",lambda r,o,b,g,d,s:d["cross_source_contracts"][0].update(producer="src/arm/arm.c:1-2")),
  ("original-false-signoff",lambda r,o,b,g,d,s:b["candidate_files"][0].update(independent_whole_file_signoff=True)),
 ]
 for label,change in cases:
  args=copy.deepcopy((rows,original,base,gate,doc,previous))
  change(*args)
  try:validate(*args)
  except ValueError:continue
  raise AssertionError("Fail-open v4 review control: "+label)
 return len(cases)

def main():
 v3.main()
 with gzip.open(v3.TARGET,"rt",encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
 with gzip.open(v2.SOURCE,"rt",encoding="utf-8",newline="") as f:original=list(csv.DictReader(f))
 base=json.loads(v2.BASE.read_text(encoding="utf-8"))
 gate=json.loads(v2.GATE.read_text(encoding="utf-8"))
 doc=json.loads(cpu.REGISTRY.read_text(encoding="utf-8"))
 previous=json.loads(v3.SUMMARY.read_text(encoding="utf-8"))
 new=validate(rows,original,base,gate,doc,previous)
 checks=negative_controls(rows,original,base,gate,doc,previous)
 output=[]
 for row in rows:
  item=dict(row)
  if item["repo"]=="mgba-emu/mgba" and item["path"] in new:
   item.update({"architecture_review_tier":TIER,
    "architecture_review_reason":"Pinned CPU prefetch / Matrix ABI header; independent whole-file review pending",
    "curated_semantic_roles":",".join(new[item["path"]]["semantic_roles"]),
    "curated_candidate_registry":str(cpu.REGISTRY)})
  output.append(item)
 rank={v2.ORIGINAL_TIER:0,v2.EXTRA_TIER:1,v3.EEPROM_TIER:2,TIER:3,
  "A1_ARCHITECTURE_CRITICAL_P0":4,"A2_OTHER_P0":5,
  "A3_P0_GAMEPLAY_SCRIPT_FIXTURE":6,"A4_P1_QUEUE":7,
  "A5_P2_QUEUE":8,"A6_P3_QUEUE":9}
 counts=collections.Counter(r["architecture_review_tier"] for r in output)
 if (len(output)!=14834 or counts[TIER]!=4 or counts[v2.ORIGINAL_TIER]!=29
     or counts[v2.EXTRA_TIER]!=2 or counts[v3.EEPROM_TIER]!=2
     or counts["A3_P0_GAMEPLAY_SCRIPT_FIXTURE"]!=163
     or collections.Counter(r["priority"] for r in output)["P0"]!=338
     or any(r["architecture_review_tier"] not in rank for r in output)):
  reject("v4 queue changed original source records or candidate tiers")
 output.sort(key=lambda r:(rank[r["architecture_review_tier"]],r["repo"],r["path"]))
 TARGET.parent.mkdir(parents=True,exist_ok=True)
 with TARGET.open("wb") as file:
  with gzip.GzipFile(filename="",mode="wb",fileobj=file,mtime=0) as zipped:
   with io.TextIOWrapper(zipped,encoding="utf-8",newline="") as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(output)
 result={
  "schema":"xgba.phase1.architecture_review_additive.v4",
  "source_queue_sha256":hashlib.sha256(v2.SOURCE.read_bytes()).hexdigest(),
  "original_registry_sha256":hashlib.sha256(v2.BASE.read_bytes()).hexdigest(),
  "timing_registry_sha256":hashlib.sha256(v2.ADDITIVE.read_bytes()).hexdigest(),
  "eeprom_registry_sha256":hashlib.sha256(v3.EEPROM_REGISTRY.read_bytes()).hexdigest(),
  "cpu_matrix_registry_sha256":hashlib.sha256(cpu.REGISTRY.read_bytes()).hexdigest(),
  "stage3_queue_sha256":hashlib.sha256(v3.TARGET.read_bytes()).hexdigest(),
  "output_queue_sha256":hashlib.sha256(TARGET.read_bytes()).hexdigest(),
  "source_files_preserved":14834,"original_P0_preserved":338,
  "original_P0_gameplay_scripts_preserved":163,
  "original_curated_pending":29,"timing_candidates_pending":2,
  "eeprom_candidates_pending":2,"cpu_matrix_candidates_pending":4,
  "total_candidates_pending":37,"tier_counts":dict(sorted(counts.items())),
  "additional_negative_controls_passed":checks,
  "independent_whole_file_approvals":0,"phase1_mapping_complete":False,
  "decision":"FAIL_INCOMPLETE",
  "limitations":["Source-anchored candidates, not independent whole-file approvals",
   "No compiled ABI, CPU/DMA interleaving, emulator or editor certification",
   "No Phase 2 implementation or original source census modification"]}
 SUMMARY.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
 print("Phase 1 v4: 14,834 source rows; 29+2+2+4=37 pending; 338 P0; %d negative controls; 0 approvals; FAIL_INCOMPLETE" % checks)

if __name__=="__main__":
 try:main()
 except Exception as error:
  print("Phase 1 v4 queue FAILED:",error,file=sys.stderr);sys.exit(2)
