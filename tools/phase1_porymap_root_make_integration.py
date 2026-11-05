#!/usr/bin/env python3
"""Execute pinned FireRed ROOT Makefile Poryscript generation and data object."""
import argparse, hashlib, json, os, re, shutil, subprocess, tempfile
from pathlib import Path
PINS = {
 "firered": ("ce6406d8c2eaf46d543c8a2606de0c3cb1951982", {
  "Makefile":"8b454dbd18eb0069fa5851d788697190890a5b37",
  "map_data_rules.mk":"b32b85a91d9460642345ca983c37d165e820741f",
  "data/event_scripts.s":"88d75946a7300ccf952f4a36c283966c6aebf5c0",
  "include/constants/event_objects.h":"9d8c514f9e2d634d40d215bf657f33041c55c28e",
  "tools/mapjson/Makefile":"100e809c6c27e6c04d3b6f2406ff288922d80c13",
  "tools/mapjson/mapjson.cpp":"8d8ec4e4e6e1c011b06f00819abe40bad10d19d5",
  "tools/mapjson/mapjson.h":"6e961a28ec0e2c6a017e7dda2e9d81f07e3e3ceb",
  "tools/mapjson/json11.cpp":"fcacdbeb39c3110e4564f57a8f26b7bb34678a7e",
  "tools/mapjson/json11.h":"c04c4362f9784006c7a45ad04729fab1c77dd1d9",
  "json_data_rules.mk":"eec18467a57cce082a4307b3d667c4c4448b1b3a",
  "tools/jsonproc/Makefile":"653d585679acd560b5965aa42c8f22b4e493aae1",
  "tools/jsonproc/jsonproc.cpp":"68b1c73ba454c9c19c6f307a129e51457c45f030",
  "tools/jsonproc/jsonproc.h":"575fb3756c0351234a5d4f40badf67033c04ed20",
  "tools/jsonproc/inja.hpp":"5b469745fb30a1c92d46929b7c819ec38effc0cf",
  "tools/jsonproc/nlohmann/json.hpp":"33a91164c7979ed8475e51fd107f900af4172306",
  "tools/preproc/preproc.cpp":"20c2de51b635a5d59f2b4e1ecd93d8fc2748ebe1",
  "tools/preproc/Makefile":"606318944c63673ec2488bb2f89712a1cc4e4950"}),
 "poryscript": ("c32481161c767b25a3425fa9f1f8729927ff3d55",{
  "README.md":"c77e022eb86e74a41b184daac5953d14c72cacc3"}),
 "porymap": ("26b919d7ff4b54152de010abd5bf344af2ebe116",{
  "src/project.cpp":"d43b0949303433111d4478ad76117c2b3445dd13"})}
TARGET="AUTO_GEN_TARGETS += $(patsubst %.pory,%.inc,$(shell find data/ -type f -name '*.pory'))"
RULE="data/%.inc: data/%.pory; $(SCRIPT) -i $< -o $@ -fc tools/poryscript/font_config.json -cc tools/poryscript/command_config.json"
ROOT_MAKE_FLAGS=["NODEP=1","SETUP_PREREQS=0"]
MAP_EVENT_IDS_TARGET="include/constants/map_event_ids.h"
MAP_EVENT_IDS_RULE="$(INCLUDECONSTS_OUTDIR)/map_event_ids.h: $(MAP_JSONS)"
MAP_EVENT_IDS_RECIPE="$(MAPJSON) event_constants firered $^ $(INCLUDECONSTS_OUTDIR)/map_event_ids.h"
MAP_GROUPS_TARGET="include/constants/map_groups.h"
MAP_GROUPS_RULE="$(MAPS_OUTDIR)/connections.inc $(MAPS_OUTDIR)/groups.inc $(MAPS_OUTDIR)/events.inc $(MAPS_OUTDIR)/headers.inc $(INCLUDECONSTS_OUTDIR)/map_groups.h: $(MAPS_DIR)/map_groups.json"
MAP_GROUPS_RECIPE="$(MAPJSON) groups firered $< $(MAPS_OUTDIR) $(INCLUDECONSTS_OUTDIR)"
LAYOUTS_TARGET="include/constants/layouts.h"
LAYOUTS_RULE="$(LAYOUTS_OUTDIR)/layouts.inc $(LAYOUTS_OUTDIR)/layouts_table.inc $(INCLUDECONSTS_OUTDIR)/layouts.h: $(LAYOUTS_DIR)/layouts.json"
LAYOUTS_RECIPE="$(MAPJSON) layouts firered $< $(LAYOUTS_OUTDIR) $(INCLUDECONSTS_OUTDIR)"
GENERATED_HEADER_TARGETS=[MAP_GROUPS_TARGET,LAYOUTS_TARGET,MAP_EVENT_IDS_TARGET]
MAPJSON_BUILD_RULE="mapjson$(EXE): $(SRCS) $(HEADERS)"
JSONPROC_BUILD_RULE="jsonproc$(EXE): $(SRCS) $(HEADERS)"
def check(x,msg):
 if not x: raise RuntimeError(msg)
def cmd(args,cwd=None,ok=True):
 p=subprocess.run(args,cwd=cwd,text=True,capture_output=True)
 if ok: check(p.returncode==0,str(args)+" failed: "+p.stderr[-2000:]+p.stdout[-1000:])
 return p
def reject_tool_build_failure(fr):
 marker="PHASE1_INJECTED_PREPROC_BUILD_FAILURE"
 with tempfile.TemporaryDirectory(prefix="phase1-preproc-failure-") as temp:
  compiler=Path(temp)/"failing-cxx"
  compiler.write_text("#!/bin/sh\necho "+marker+" >&2\nexit 73\n")
  compiler.chmod(0o755)
  try:
   cmd(["make","-B","-C",str(fr/"tools/preproc"),"CXX="+str(compiler)])
  except RuntimeError as error:
   check(marker in str(error),"tool build failure diagnostic missing")
   return True
  raise RuntimeError("pinned original preproc build failure was accepted")
def source_contract(fr,ps,pm,map_rules,mapjson_make,json_rules,jsonproc_make,
                    jsonproc_source,event_objects,event_source):
 check("AUTO_GEN_TARGETS :=" in fr and "generated: $(AUTO_GEN_TARGETS)" in fr,"root generated target drift")
 check("$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.s" in fr,"original data rule drift")
 check("$(PREPROC) $< charmap.txt | $(CPP) $(INCLUDE_SCANINC_ARGS) - | $(PREPROC) -ie $< charmap.txt | $(AS) $(ASFLAGS) -o $@" in fr,"native recipe drift")
 check("include map_data_rules.mk" in fr,"original map-data rules not included")
 check("AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/map_event_ids.h" in map_rules,
       "map event constants missing from original generated target")
 check(MAP_EVENT_IDS_RULE in map_rules and MAP_EVENT_IDS_RECIPE in map_rules,
       "original map event constants generation rule drift")
 check("AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/map_groups.h" in map_rules and
       MAP_GROUPS_RULE in map_rules and MAP_GROUPS_RECIPE in map_rules,
       "original map groups generation rule drift")
 check("AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/layouts.h" in map_rules and
       LAYOUTS_RULE in map_rules and LAYOUTS_RECIPE in map_rules,
       "original layouts generation rule drift")
 check(MAPJSON_BUILD_RULE in mapjson_make and "$(CXX) $(CXXFLAGS) $(SRCS) -o $@ $(LDFLAGS)" in mapjson_make,
       "original mapjson build rule drift")
 check("SRCS := json11.cpp mapjson.cpp" in mapjson_make and "HEADERS := mapjson.h" in mapjson_make,
       "original mapjson source set drift")
 check("include json_data_rules.mk" in fr and
       "AUTO_GEN_TARGETS += $(DATA_SRC_SUBDIR)/wild_encounters.h" in json_rules and
       "$(JSONPROC) $^ $@" in json_rules,
       "original jsonproc generated-target dependency drift")
 check(JSONPROC_BUILD_RULE in jsonproc_make and
       "$(CXX) $(CXXFLAGS) $(INCLUDES) $(SRCS) -o $@ $(LDFLAGS)" in jsonproc_make and
       "SRCS := jsonproc.cpp" in jsonproc_make,
       "original jsonproc build rule drift")
 check("#include <inja.hpp>" in jsonproc_source,
       "original jsonproc template dependency drift")
 check('#include "constants/map_event_ids.h"' in event_objects,
       "original event object generated-header dependency drift")
 check('#include "constants/event_objects.h"' in event_source,
       "original event script object-header dependency drift")
 check('#include "constants/layouts.h"' in event_source,
       "original event script layouts-header dependency drift")
 check(TARGET in ps and RULE in ps,"Poryscript documented recipe drift")
 check('return QString("mapscripts %1_MapScripts {}\\n").arg(mapName);' in pm and 'return ".pory";' in pm,"Porymap authoring drift")
def main():
 p=argparse.ArgumentParser()
 for name in PINS: p.add_argument("--"+name,type=Path,required=True)
 p.add_argument("--output",type=Path,required=True)
 a=p.parse_args()
 roots={name:getattr(a,name).resolve() for name in PINS}
 for name,(sha,blobs) in PINS.items():
  root=roots[name]
  check(cmd(["git","-C",str(root),"rev-parse","HEAD"]).stdout.strip()==sha,"upstream revision drift "+name)
  for path,blob in blobs.items():
   check(cmd(["git","-C",str(root),"hash-object",path]).stdout.strip()==blob,"blob drift "+name+"/"+path)
 fr=roots["firered"];ps=roots["poryscript"];pm=roots["porymap"]
 make=(fr/"Makefile").read_text();event=(fr/"data/event_scripts.s").read_text()
 readme=(ps/"README.md").read_text();project=(pm/"src/project.cpp").read_text()
 map_rules=(fr/"map_data_rules.mk").read_text()
 mapjson_make=(fr/"tools/mapjson/Makefile").read_text()
 json_rules=(fr/"json_data_rules.mk").read_text()
 jsonproc_make=(fr/"tools/jsonproc/Makefile").read_text()
 jsonproc_source=(fr/"tools/jsonproc/jsonproc.cpp").read_text()
 event_objects=(fr/"include/constants/event_objects.h").read_text()
 source_contract(make,readme,project,map_rules,mapjson_make,json_rules,jsonproc_make,
                 jsonproc_source,event_objects,event)
 mutations=[(0,"AUTO_GEN_TARGETS :=","AUTO_GEN_TARGETS ="),
  (0,"generated: $(AUTO_GEN_TARGETS)","generated:"),
  (0,"$(PREPROC) -ie $< charmap.txt","cat"),
  (0,"$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.s","missing:"),
  (1,TARGET,"AUTO_GEN_TARGETS += wrong"),
  (1,RULE,RULE.replace("-o $@","-x $@")),
  (2,'return ".pory";','return ".inc";'),
  (2,"mapscripts %1_MapScripts {}","script %1_MapScripts {}"),
  (3,"AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/map_event_ids.h","AUTO_GEN_TARGETS +="),
  (3,MAP_EVENT_IDS_RULE,MAP_EVENT_IDS_RULE.replace("$(MAP_JSONS)","")),
  (3,MAP_EVENT_IDS_RECIPE,MAP_EVENT_IDS_RECIPE.replace("event_constants","wrong_mode")),
  (3,"AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/map_groups.h","AUTO_GEN_TARGETS +="),
  (3,MAP_GROUPS_RULE,MAP_GROUPS_RULE.replace("$(MAPS_DIR)/map_groups.json","")),
  (3,MAP_GROUPS_RECIPE,MAP_GROUPS_RECIPE.replace("groups firered","wrong_mode firered")),
  (3,"AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/layouts.h","AUTO_GEN_TARGETS +="),
  (3,LAYOUTS_RULE,LAYOUTS_RULE.replace("$(LAYOUTS_DIR)/layouts.json","")),
  (3,LAYOUTS_RECIPE,LAYOUTS_RECIPE.replace("layouts firered","wrong_mode firered")),
  (4,MAPJSON_BUILD_RULE,"mapjson$(EXE):"),
  (4,"$(CXX) $(CXXFLAGS) $(SRCS) -o $@ $(LDFLAGS)","false"),
  (5,"AUTO_GEN_TARGETS += $(DATA_SRC_SUBDIR)/wild_encounters.h","AUTO_GEN_TARGETS +="),
  (5,"$(JSONPROC) $^ $@","false"),
  (6,JSONPROC_BUILD_RULE,"jsonproc$(EXE):"),
  (6,"$(CXX) $(CXXFLAGS) $(INCLUDES) $(SRCS) -o $@ $(LDFLAGS)","false"),
  (7,"#include <inja.hpp>",""),
  (8,'#include "constants/map_event_ids.h"',""),
  (9,'#include "constants/event_objects.h"',""),
  (9,'#include "constants/layouts.h',"")]
 for i,(n,old,new) in enumerate(mutations):
  sources=[make,readme,project,map_rules,mapjson_make,json_rules,jsonproc_make,
           jsonproc_source,event_objects,event]
  check(old in sources[n],"mutation anchor missing "+str(i))
  sources[n]=sources[n].replace(old,new)
  try: source_contract(*sources)
  except RuntimeError: continue
  raise RuntimeError("source mutation escaped "+str(i))
 cli=fr/"tools/poryscript/poryscript";cli.parent.mkdir(parents=True,exist_ok=True)
 cmd(["go","build","-o",str(cli),"."],cwd=ps)
 for name in ("font_config.json","command_config.json"):
  shutil.copyfile(ps/name,cli.parent/name)
 injected_failure_rejected=reject_tool_build_failure(fr)
 cmd(["make","-C",str(fr/"tools/preproc"),"-j2"])
 cmd(["make","-C",str(fr/"tools/mapjson"),"-j2"])
 cmd(["make","-C",str(fr/"tools/jsonproc"),"-j2"])
 probe=fr/"data/maps/XGBAProbe";probe.mkdir(parents=True,exist_ok=True)
 inp=probe/"scripts.pory";inp.write_text("mapscripts XGBAProbe_MapScripts {}\n")
 inc=probe/"scripts.inc";obj=fr/"build/firered/data/event_scripts.o"
 overlay=make.replace("AUTO_GEN_TARGETS :=","AUTO_GEN_TARGETS :=\n"+TARGET,1).replace(
  "generated: $(AUTO_GEN_TARGETS)","SCRIPT := tools/poryscript/poryscript\n"+RULE+"\ngenerated: $(AUTO_GEN_TARGETS)",1)
 check(overlay.count(TARGET)==1 and overlay.count(RULE)==1,"overlay drift")
 (fr/"Makefile").write_text(overlay)
 (fr/"data/event_scripts.s").write_text(event+'\n\t.include "data/maps/XGBAProbe/scripts.inc"\n')
 map_jsons=sorted((fr/"data/maps").glob("*/map.json"))
 check(map_jsons,"pinned map JSON inputs missing")
 header_inputs={
  MAP_GROUPS_TARGET:[fr/"data/maps/map_groups.json"],
  LAYOUTS_TARGET:[fr/"data/layouts/layouts.json"],
  MAP_EVENT_IDS_TARGET:map_jsons}
 for target,inputs in header_inputs.items():
  check(all(path.is_file() for path in inputs),"generated-header inputs missing "+target)
 generated_command=["make",*ROOT_MAKE_FLAGS,"generated"]
 for target in GENERATED_HEADER_TARGETS:
  check(not (fr/target).exists(),"generated header unexpectedly exists before generation "+target)
 cmd(generated_command,cwd=fr)
 generated_headers={target:(fr/target).read_bytes() for target in GENERATED_HEADER_TARGETS}
 check(all(generated_headers.values()),"original generated target produced an empty header")
 for target in GENERATED_HEADER_TARGETS:
  (fr/target).unlink()
 cmd(generated_command,cwd=fr)
 absent_headers_regenerated=all(
  (fr/target).is_file() and (fr/target).read_bytes()==generated_headers[target]
  for target in GENERATED_HEADER_TARGETS)
 check(absent_headers_regenerated,"absent generated header was not regenerated by original target")
 stale_times={}
 for target,inputs in header_inputs.items():
  header=fr/target
  newest_input_ns=max(path.stat().st_mtime_ns for path in inputs)
  stale_time_ns=max(1,newest_input_ns-2_000_000_000)
  os.utime(header,ns=(header.stat().st_atime_ns,stale_time_ns))
  check(header.stat().st_mtime_ns < newest_input_ns,
        "stale-header control did not make generated header older than inputs "+target)
  stale_times[target]=stale_time_ns
 cmd(generated_command,cwd=fr)
 stale_headers_regenerated=all(
  (fr/target).stat().st_mtime_ns > stale_times[target] and
  (fr/target).read_bytes()==generated_headers[target]
  for target in GENERATED_HEADER_TARGETS)
 check(stale_headers_regenerated,"stale generated header was not regenerated by original target")
 header_provenance={}
 for target,inputs in header_inputs.items():
  input_manifest="\n".join(
   path.relative_to(fr).as_posix()+":"+hashlib.sha256(path.read_bytes()).hexdigest()
   for path in inputs).encode()
  header_provenance[target]={
   "sha256":hashlib.sha256(generated_headers[target]).hexdigest(),
   "input_count":len(inputs),
   "input_manifest_sha256":hashlib.sha256(input_manifest).hexdigest()}
 try:
  database=cmd(["make","-qp",*ROOT_MAKE_FLAGS],cwd=fr,ok=False)
  database_output=database.stdout+database.stderr
  check(database.returncode in (0,1),
        "root make database parse failed (exit %d):\n%s"%
        (database.returncode,database_output))
  check(any(line.startswith("generated:") and "data/maps/XGBAProbe/scripts.inc" in line for line in database.stdout.splitlines()),"root generated target omits Poryscript output")
  cmd(["make",*ROOT_MAKE_FLAGS,"data/maps/XGBAProbe/scripts.inc"],cwd=fr)
  check(inc.is_file() and b"XGBAProbe_MapScripts" in inc.read_bytes(),"root generated output missing")
  generated=inc.read_bytes()
  cmd(["make",*ROOT_MAKE_FLAGS,"build/firered/data/event_scripts.o"],cwd=fr)
  check(obj.is_file(),"root event object absent")
  symbols=cmd(["arm-none-eabi-nm",str(obj)]).stdout
  check(len(re.findall(r"\bXGBAProbe_MapScripts\b",symbols))==1,"original event object symbol missing")
  nochange=cmd(["make","-n",*ROOT_MAKE_FLAGS,"data/maps/XGBAProbe/scripts.inc"],cwd=fr).stdout
  check("poryscript -i" not in nochange,"unchanged input regenerated")
  (fr/"Makefile").write_text(overlay.replace(RULE+"\n","",1));inc.unlink()
  check(cmd(["make",*ROOT_MAKE_FLAGS,"data/maps/XGBAProbe/scripts.inc"],cwd=fr,ok=False).returncode!=0,"missing rule accepted")
  (fr/"Makefile").write_text(overlay);inp.write_text("mapscripts Broken {\n")
  check(cmd(["make",*ROOT_MAKE_FLAGS,"data/maps/XGBAProbe/scripts.inc"],cwd=fr,ok=False).returncode!=0,"malformed source accepted")
  inp.write_text("mapscripts XGBAProbe_MapScripts {}\n")
  cmd(["make",*ROOT_MAKE_FLAGS,"data/maps/XGBAProbe/scripts.inc"],cwd=fr)
  check(inc.read_bytes()==generated,"recovery changed generated bytes")
  evidence={"class":"PINNED_FIRERED_ROOT_MAKE_PORYSCRIPT_EVENT_OBJECT",
   "upstream_pins":{k:v[0] for k,v in PINS.items()},
   "source_blobs":{k:v[1] for k,v in PINS.items()},
   "incidental_root_tool_build_disabled_for_test_targets":True,
   "original_preproc_build_failure_rejected":injected_failure_rejected,
   "pinned_mapjson_tool_built":True,
   "pinned_jsonproc_tool_built":True,
   "map_event_ids_generated_by_original_root_rule":True,
   "root_generated_target_executed":True,
   "generated_headers_command":"make NODEP=1 SETUP_PREREQS=0 generated",
   "generated_header_targets":GENERATED_HEADER_TARGETS,
   "generated_header_provenance":header_provenance,
   "absent_generated_headers_regenerated":absent_headers_regenerated,
   "stale_generated_headers_regenerated":stale_headers_regenerated,
   "map_event_ids_target":MAP_EVENT_IDS_TARGET,
   "map_event_ids_input_count":header_provenance[MAP_EVENT_IDS_TARGET]["input_count"],
   "map_event_ids_input_manifest_sha256":header_provenance[MAP_EVENT_IDS_TARGET]["input_manifest_sha256"],
   "map_event_ids_sha256":header_provenance[MAP_EVENT_IDS_TARGET]["sha256"],
   "mapjson_tool_sha256":hashlib.sha256((fr/"tools/mapjson/mapjson").read_bytes()).hexdigest(),
   "jsonproc_tool_sha256":hashlib.sha256((fr/"tools/jsonproc/jsonproc").read_bytes()).hexdigest(),
   "absent_map_event_header_regenerated":absent_headers_regenerated,
   "stale_map_event_header_regenerated":stale_headers_regenerated,
   "generated_map_event_ids_consumed_by_original_object":True,
   "root_generated_target_discovered":True,"original_root_event_object_compiled":True,
   "original_event_source_preserved_with_one_test_include":True,
   "generated_symbol_linkable_object":True,"unchanged_skips_generation":True,
   "missing_rule_rejected":True,"malformed_input_rejected":True,"recovery_byte_identical":True,
   "generated_sha256":hashlib.sha256(generated).hexdigest(),
   "event_object_sha256":hashlib.sha256(obj.read_bytes()).hexdigest(),
   "source_mutations_rejected":len(mutations),
   "full_rom_linked":False,"mgba_runtime_executed":False,"porymap_gui_executed":False,
   "independent_approvals":0,"phase1_gate":"FAIL_INCOMPLETE"}
  def verify(d):
   check(d["source_mutations_rejected"]==len(mutations),"source negative drift")
   check(d["incidental_root_tool_build_disabled_for_test_targets"] is True,
         "unrelated root tool bootstrap was not disabled")
   check(d["original_preproc_build_failure_rejected"] is True,
         "original required-tool failure was not rejected")
   for k in ("pinned_mapjson_tool_built","pinned_jsonproc_tool_built",
     "map_event_ids_generated_by_original_root_rule",
     "root_generated_target_executed","absent_generated_headers_regenerated",
     "stale_generated_headers_regenerated","absent_map_event_header_regenerated",
     "stale_map_event_header_regenerated",
     "generated_map_event_ids_consumed_by_original_object"):
    check(d[k] is True,"missing map-event generation witness "+k)
   check(d["map_event_ids_target"]==MAP_EVENT_IDS_TARGET,"map event target drift")
   check(d["generated_headers_command"]=="make NODEP=1 SETUP_PREREQS=0 generated",
         "root generated target command drift")
   check(d["generated_header_targets"]==GENERATED_HEADER_TARGETS,
         "root generated-header target list drift")
   check(set(d["generated_header_provenance"])==set(GENERATED_HEADER_TARGETS),
         "generated-header provenance set drift")
   check(d["generated_header_provenance"]==header_provenance,
         "generated-header evidence differs from observed outputs")
   for target,entry in d["generated_header_provenance"].items():
    check(set(entry)=={"sha256","input_count","input_manifest_sha256"},
          "generated-header provenance fields drift "+target)
    check(entry["input_count"]>0,"generated-header inputs missing "+target)
    if target!=MAP_EVENT_IDS_TARGET:
     check(entry["input_count"]==1,"generated-header input count drift "+target)
    for key in ("sha256","input_manifest_sha256"):
     check(re.fullmatch(r"[0-9a-f]{64}",entry[key]) is not None,
           "generated-header provenance missing "+target+"/"+key)
   map_event_provenance=d["generated_header_provenance"][MAP_EVENT_IDS_TARGET]
   check(d["map_event_ids_input_count"]==map_event_provenance["input_count"] and
         d["map_event_ids_input_manifest_sha256"]==map_event_provenance["input_manifest_sha256"] and
         d["map_event_ids_sha256"]==map_event_provenance["sha256"],
         "map-event provenance aliases disagree")
   check(d["map_event_ids_input_count"]>0,"map event generation inputs missing")
   for k in ("map_event_ids_input_manifest_sha256","map_event_ids_sha256",
             "mapjson_tool_sha256","jsonproc_tool_sha256"):
    check(re.fullmatch(r"[0-9a-f]{64}",d[k]) is not None,"map event provenance missing "+k)
   check(d["evidence_mutations_rejected"]==len(negatives)+1,"evidence negative drift")
   for k in ("root_generated_target_discovered","original_root_event_object_compiled",
    "original_event_source_preserved_with_one_test_include","generated_symbol_linkable_object",
    "unchanged_skips_generation","missing_rule_rejected","malformed_input_rejected","recovery_byte_identical"):
    check(d[k] is True,"missing witness "+k)
   for k in ("full_rom_linked","mgba_runtime_executed","porymap_gui_executed"):
    check(d[k] is False,"scope overclaim "+k)
   check(d["independent_approvals"]==0 and d["phase1_gate"]=="FAIL_INCOMPLETE","false approval")
   check(len(d["event_object_sha256"])==64,"object identity missing")
  negatives=[{"source_mutations_rejected":len(mutations)-1},{"root_generated_target_discovered":False},
   {"original_root_event_object_compiled":False},{"original_event_source_preserved_with_one_test_include":False},
   {"generated_symbol_linkable_object":False},{"unchanged_skips_generation":False},
   {"missing_rule_rejected":False},{"malformed_input_rejected":False},
   {"recovery_byte_identical":False},{"full_rom_linked":True},{"mgba_runtime_executed":True},
   {"porymap_gui_executed":True},{"independent_approvals":1},{"phase1_gate":"PASS"},
   {"event_object_sha256":""},{"original_preproc_build_failure_rejected":False},
   {"root_generated_target_executed":False},{"absent_generated_headers_regenerated":False},
   {"stale_generated_headers_regenerated":False},{"generated_header_provenance":{}},
   {"pinned_mapjson_tool_built":False},{"map_event_ids_generated_by_original_root_rule":False},
   {"pinned_jsonproc_tool_built":False},{"jsonproc_tool_sha256":""},
   {"absent_map_event_header_regenerated":False},{"stale_map_event_header_regenerated":False},
   {"generated_map_event_ids_consumed_by_original_object":False},{"map_event_ids_input_count":0},
   {"map_event_ids_input_manifest_sha256":""},{"map_event_ids_sha256":""},
   {"mapjson_tool_sha256":""},{"map_event_ids_target":"wrong"},
   {"generated_headers_command":"wrong"},{"generated_header_targets":[]}]
  for target in GENERATED_HEADER_TARGETS:
   for key,bad in (("sha256",""),("input_count",0),("input_manifest_sha256","")):
    entry=dict(header_provenance[target]);entry[key]=bad
    negatives.append({"generated_header_provenance":{
     **header_provenance,target:entry}})
   entry=dict(header_provenance[target])
   digest=entry["sha256"]
   entry["sha256"]=("0" if digest[0]!="0" else "1")+digest[1:]
   negatives.append({"generated_header_provenance":{
    **header_provenance,target:entry}})
  evidence["evidence_mutations_rejected"]=len(negatives)+1
  verify(evidence)
  for i,change in enumerate(negatives+[{"evidence_mutations_rejected":len(negatives)}]):
   try: verify({**evidence,**change})
   except RuntimeError: continue
   raise RuntimeError("evidence mutation escaped "+str(i))
  a.output.parent.mkdir(parents=True,exist_ok=True)
  a.output.write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n")
  print(json.dumps(evidence,sort_keys=True))
 finally:
  (fr/"Makefile").write_text(make)
  (fr/"data/event_scripts.s").write_text(event)
if __name__=="__main__": main()
