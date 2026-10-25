#!/usr/bin/env python3
"""Conservative XGBA upstream-update delta and candidate impact report.

Compares immutable Git blob SHA/version/mode, not guessed source offsets. For
changed source, traces *possible* reverse dependencies from pinned evidence,
never auto-adapts a compiled ABI or assumes matching file names mean safety.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,json,subprocess
from pathlib import Path
PINS={
"pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
"mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b",
"huderlem/porymap":"26b919d7ff4b54152de010abd5bf344af2ebe116",
"huderlem/poryscript":"c32481161c767b25a3425fa9f1f8729927ff3d55",
"pret/agbcc":"da598c1d918402c42c0c0d7128ba14567f3175e9"}
SENSITIVE={
("mgba-emu/mgba","src/gba/memory.c"),("mgba-emu/mgba","src/gba/serialize.c"),
("mgba-emu/mgba","src/gba/dma.c"),("mgba-emu/mgba","src/arm/arm.c"),
("mgba-emu/mgba","src/gba/cart/matrix.c"),
("pret/pokefirered","src/script.c"),("pret/pokefirered","src/scrcmd.c"),
("pret/pokefirered","src/battle_script_commands.c"),
("pret/pokefirered","src/battle_util.c"),("pret/pokefirered","src/load_save.c"),
("pret/pokefirered","src/fieldmap.c"),("pret/pokefirered","ld_script.ld"),
("pret/pokefirered","ld_script_modern.ld"),("pret/pokefirered","Makefile"),
("pret/pokefirered","data/script_cmd_table.inc"),
("pret/pokefirered","graphics_file_rules.mk"),
("huderlem/porymap","src/project.cpp"),("huderlem/porymap","src/core/map.cpp"),
("huderlem/porymap","src/core/maplayout.cpp"),
("huderlem/porymap","include/core/map.h"),
("huderlem/poryscript","emitter/emitter.go"),
("pret/agbcc","gcc_arm/config/arm/t-arm-elf")}
# Verified contracts added after the initial sensitivity list. An upstream change
# to any listed file requires re-validation of this contract; a matching basename
# elsewhere does not authorize automatic relocation or adaptation.
CONTRACT_SOURCE_FILES={
 ("pret/pokefirered","src/save.c"):("native_flash_rotation","sidecar_consistency"),
 ("pret/pokefirered","include/save.h"):("native_flash_sector_geometry","sidecar_consistency"),
 ("pret/pokefirered","src/m4a.c"):("audio_song_table_and_live_header","resource_staging"),
 ("pret/pokefirered","src/decompress.c"):("graphics_decompression_scratch","resource_staging"),
 ("pret/pokefirered","src/sprite.c"):("obj_vram_tile_and_palette_allocation","resource_staging"),
 ("pret/pokefirered","src/graphics.c"):("inlined_asset_tables","resource_staging"),
 ("pret/pokefirered","src/battle_util.c"):("battle_bytecode_dispatch","script_operand_abi"),
 ("pret/pokefirered","src/overworld.c"):("cross_map_clone_runtime","map_editor_roundtrip"),
 ("pret/pokefirered","src/event_object_movement.c"):("cross_map_clone_runtime","map_editor_roundtrip"),
 ("pret/pokefirered","tools/mapjson/mapjson.cpp"):("mapjson_native_compiler","map_editor_roundtrip"),
 ("pret/pokefirered","asm/macros/map.inc"):("map_binary_event_abi","map_editor_roundtrip"),
 ("pret/pokefirered","asm/macros/event.inc"):("field_script_macro_abi","script_operand_abi"),
 ("pret/pokefirered","data/script_cmd_table.inc"):("field_script_opcode_registry","script_operand_abi"),
 ("pret/pokefirered","data/maps/map_groups.json"):("map_group_numbering","map_editor_roundtrip"),
 ("pret/pokefirered","data/layouts/layouts.json"):("map_layout_pointer_mapping","map_editor_roundtrip"),
 ("pret/pokefirered","graphics_file_rules.mk"):("generated_graphics_converter","resource_staging"),
 ("pret/pokefirered","src/battle_script_commands.c"):("battle_bytecode_dispatch","script_operand_abi"),
 ("mgba-emu/mgba","src/gba/savedata.c"):("emulated_native_savedata","sidecar_consistency"),
 ("mgba-emu/mgba","include/mgba/internal/gba/memory.h"):("gba_address_space","rom_dma_fetch"),
 ("mgba-emu/mgba","src/gba/memory.c"):("rom_window_and_eeprom","rom_dma_fetch"),
 ("mgba-emu/mgba","src/gba/dma.c"):("rom_dma_fetch","eeprom_priority"),
 ("mgba-emu/mgba","src/gba/serialize.c"):("savestate_binding","sidecar_consistency"),
 ("mgba-emu/mgba","src/arm/arm.c"):("direct_cpu_prefetch","rom_dma_fetch"),
 ("mgba-emu/mgba","src/gba/cart/matrix.c"):("matrix_cart_arbitration","rom_dma_fetch"),
 ("huderlem/porymap","src/core/maplayout.cpp"):("map_tile_collision_elevation","map_editor_roundtrip"),
 ("huderlem/porymap","src/project.cpp"):("json_event_types_and_layout","map_editor_roundtrip"),
 ("huderlem/poryscript","emitter/emitter.go"):("script_assembler_encoding","script_operand_abi"),
 ("pret/agbcc","gcc/Makefile"):("legacy_agbcc_codegen","compiler_variant_binary_abi"),
 ("pret/agbcc","gcc_arm/config/arm/t-arm-elf"):("arm_thumb_multilib","compiler_variant_binary_abi"),
}
SENSITIVE.update(CONTRACT_SOURCE_FILES)

def affected_contracts(changed):
 hits=collections.defaultdict(set)
 for repo,path in changed:
  for contract in CONTRACT_SOURCE_FILES.get((repo,path),()):
   hits[contract].add(repo+"/"+path)
 return {name:sorted(paths) for name,paths in sorted(hits.items())}

def readrows(path):
 with gzip.open(path,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def git_current(root,repo):
 checkout=root/repo.split("/")[-1]
 commit=subprocess.check_output(["git","-C",str(checkout),"rev-parse","HEAD"],text=True).strip()
 tree=subprocess.check_output(["git","-C",str(checkout),"ls-tree","-r","-z","HEAD"])
 entries={}
 for e in tree.split(b"\0"):
  if not e:continue
  attrs,p=e.split(b"\t",1)
  mode,kind,sha=attrs.decode().split()
  if kind=="blob":entries[p.decode("utf-8","surrogateescape")]={"mode":mode,"blob_sha":sha}
 return commit,entries
def classify(repo,old,new):
 oldkeys=set(old);newkeys=set(new)
 modified=sorted(x for x in oldkeys&newkeys if old[x]["blob_sha"]!=new[x]["blob_sha"] or old[x]["mode"]!=new[x]["mode"])
 removed=sorted(oldkeys-newkeys);added=sorted(newkeys-oldkeys)
 unchanged=len(oldkeys&newkeys)-len(modified)
 removed_sha=collections.defaultdict(list);added_sha=collections.defaultdict(list)
 for p in removed:removed_sha[old[p]["blob_sha"]].append(p)
 for p in added:added_sha[new[p]["blob_sha"]].append(p)
 possible_renames=[]
 for h in removed_sha:
  if h in added_sha:
   possible_renames.append({"blob_sha":h,"old_paths":removed_sha[h],"new_paths":added_sha[h],
      "status":"IDENTICAL_BLOB_PATH_MOVE_CANDIDATE_NOT_APPROVED_RENAME"})
 return {"unchanged":unchanged,"modified":modified,"deleted":removed,"added":added,"possible_renames":possible_renames}
def impact(reverse,start,max_candidates=1000):
 seen=set(start);stack=list(start)
 while stack and len(seen)<max_candidates:
  current=stack.pop()
  for pred in reverse.get(current,()):
   if pred not in seen:
    seen.add(pred);stack.append(pred)
 return sorted(seen-set(start)),bool(stack)
def selftest():
 o={"a.c":{"blob_sha":"1","mode":"100644"},"b.c":{"blob_sha":"2","mode":"100644"}}
 n={"a.c":{"blob_sha":"3","mode":"100644"},"c.c":{"blob_sha":"2","mode":"100644"}}
 d=classify("r",o,n)
 assert d["modified"]==["a.c"] and d["deleted"]==["b.c"] and d["added"]==["c.c"]
 assert d["possible_renames"]==[{"blob_sha":"2","old_paths":["b.c"],"new_paths":["c.c"],"status":"IDENTICAL_BLOB_PATH_MOVE_CANDIDATE_NOT_APPROVED_RENAME"}]
 got,truncated=impact({("r","b.c"):{("r","a.c")}},[("r","b.c")])
 assert got==[("r","a.c")] and not truncated
 assert ("pret/pokefirered","src/save.c") in SENSITIVE
 assert "native_flash_rotation" in affected_contracts([("pret/pokefirered","src/save.c")])
 assert affected_contracts([("pret/pokefirered","src/noncritical.c")])=={}
 print("Update-delta self-test passed")
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--baseline",type=Path,default=Path("audit-output"))
 p.add_argument("--root",type=Path,default=Path("upstream"))
 p.add_argument("--out",type=Path,default=Path("audit-output"))
 a=p.parse_args();a.out.mkdir(exist_ok=True,parents=True)
 manifest=list(readrows(a.baseline/"tracked_file_manifest.csv.gz"))
 if len(manifest)!=14834:raise RuntimeError("Expected pinned 14,834 baseline manifest")
 byrepo=collections.defaultdict(dict)
 for r in manifest:
  if r["repo"] not in PINS or r["revision"]!=PINS[r["repo"]]:
   raise RuntimeError("Incorrect pinned baseline: "+str((r["repo"],r["path"])))
  byrepo[r["repo"]][r["path"]]={"blob_sha":r["blob_sha"],"mode":r["mode"]}
 reverse=collections.defaultdict(set)
 for r in readrows(a.baseline/"unified_candidate_dependency_edges.csv.gz"):
  reverse[(r["repo"],r["target_path"])].add((r["repo"],r["source_path"]))
 repos={};changed_source=[];aggregate=collections.Counter()
 for repo,old in sorted(byrepo.items()):
  revision,new=git_current(a.root,repo)
  if len(new)<10:raise RuntimeError("Suspiciously sparse repository "+repo)
  d=classify(repo,old,new)
  affected=d["modified"]+d["deleted"]+d["added"]
  for key in ("modified","deleted","added"):aggregate[key]+=len(d[key])
  aggregate["unchanged"]+=d["unchanged"]
  changed_source.extend((repo,p) for p in affected)
  repos[repo]={"baseline_commit":PINS[repo],"target_commit":revision,
    "tracked_previous":len(old),"tracked_current":len(new),
    "same_commit":revision==PINS[repo],
    "changes":d}
 impacted,truncated=impact(reverse,changed_source)
 direct_sensitive=sorted((repo,path) for repo,path in changed_source if (repo,path) in SENSITIVE)
 indirect_sensitive=sorted((repo,path) for repo,path in impacted if (repo,path) in SENSITIVE)
 release_gate=("STOP_AND_REVALIDATE_SEMANTIC_ABI" if direct_sensitive or indirect_sensitive
    else "SOURCE_DRIFT_NEEDS_REVIEW" if changed_source
    else "SAME_PINNED_SOURCES_BASELINE")
 report={"from_commits":PINS,"source_changes":dict(aggregate),
   "direct_critical_contract_changes":[{"repo":r,"path":p} for r,p in direct_sensitive],
   "candidate_indirect_critical_impacts":[{"repo":r,"path":p} for r,p in indirect_sensitive],
   "direct_contract_revalidations":affected_contracts(changed_source),
   "indirect_candidate_contract_revalidations":affected_contracts(impacted),
  "reverse_candidate_impact_files":len(impacted),"candidate_impact_truncated":truncated,
   "release_gate":release_gate,"repositories":repos,
   "automatically_compatible":False,
   "versioned_abi_review_approved":False,"phase1_mapping_complete":False,
   "limitations":["This is candidate reverse-reachability, not compile/link proof.",
     "Deleted/moved paths can invalidate IDs even if a different file has identical bytes.",
     "Generated assets, build flags and embedded table offsets need rebuilt evidence for every changed compiler configuration.",
     "A zero-diff report proves source revision equality, not full Phase 1 semantic completion."]}
 (a.out/"source_update_delta_semantic_impact.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k not in ("repositories","limitations","from_commits")},indent=2))
 if not changed_source and not all(v["same_commit"] for v in repos.values()):
  raise RuntimeError("Changed commit without file difference: investigate revision semantics")
if __name__=="__main__":
 import sys
 if "--self-test" in sys.argv:selftest()
 else:main()
