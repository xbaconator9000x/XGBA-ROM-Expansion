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
MAPJSON_BUILD_RULE="mapjson$(EXE): $(SRCS) $(HEADERS)"
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
def source_contract(fr,ps,pm,map_rules,mapjson_make,event_objects,event_source):
 check("AUTO_GEN_TARGETS :=" in fr and "generated: $(AUTO_GEN_TARGETS)" in fr,"root generated target drift")
 check("$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.s" in fr,"original data rule drift")
 check("$(PREPROC) $< charmap.txt | $(CPP) $(INCLUDE_SCANINC_ARGS) - | $(PREPROC) -ie $< charmap.txt | $(AS) $(ASFLAGS) -o $@" in fr,"native recipe drift")
 check("include map_data_rules.mk" in fr,"original map-data rules not included")
 check("AUTO_GEN_TARGETS += $(INCLUDECONSTS_OUTDIR)/map_event_ids.h" in map_rules,
       "map event constants missing from original generated target")
 check(MAP_EVENT_IDS_RULE in map_rules and MAP_EVENT_IDS_RECIPE in map_rules,
       "original map event constants generation rule drift")
 check(MAPJSON_BUILD_RULE in mapjson_make and "$(CXX) $(CXXFLAGS) $(SRCS) -o $@ $(LDFLAGS)" in mapjson_make,
       "original mapjson build rule drift")
 check("SRCS := json11.cpp mapjson.cpp" in mapjson_make and "HEADERS := mapjson.h" in mapjson_make,
       "original mapjson source set drift")
 check('#include "constants/map_event_ids.h"' in event_objects,
       "original event object generated-header dependency drift")
 check('#include "constants/event_objects.h"' in event_source,
       "original event script object-header dependency drift")
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
 event_objects=(fr/"include/constants/event_objects.h").read_text()
 source_contract(make,readme,project,map_rules,mapjson_make,event_objects,event)
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
  (4,MAPJSON_BUILD_RULE,"mapjson$(EXE):"),
  (4,"$(CXX) $(CXXFLAGS) $(SRCS) -o $@ $(LDFLAGS)","false"),
  (5,'#include "constants/map_event_ids.h"',""),
  (6,'#include "constants/event_objects.h"',"")]
 for i,(n,old,new) in enumerate(mutations):
  sources=[make,readme,project,map_rules,mapjson_make,event_objects,event]
  check(old in sources[n],"mutation anchor missing "+str(i))
  sources[n]=sources[n].replace(old,new) if i==2 else sources[n].replace(old,new,1)
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
 probe=fr/"data/maps/XGBAProbe";probe.mkdir(parents=True,exist_ok=True)
 inp=probe/"scripts.pory";inp.write_text("mapscripts XGBAProbe_MapScripts {}\n")
 inc=probe/"scripts.inc";obj=fr/"build/firered/data/event_scripts.o"
 overlay=make.replace("AUTO_GEN_TARGETS :=","AUTO_GEN_TARGETS :=\n"+TARGET,1).replace(
  "generated: $(AUTO_GEN_TARGETS)","SCRIPT := tools/poryscript/poryscript\n"+RULE+"\ngenerated: $(AUTO_GEN_TARGETS)",1)
 check(overlay.count(TARGET)==1 and overlay.count(RULE)==1,"overlay drift")
 (fr/"Makefile").write_text(overlay)
 (fr/"data/event_scripts.s").write_text(event+'\n\t.include "data/maps/XGBAProbe/scripts.inc"\n')
 map_ids=fr/MAP_EVENT_IDS_TARGET
 check(not map_ids.exists(),"generated map event header unexpectedly exists before generation")
 map_jsons=sorted((fr/"data/maps").glob("*/map.json"))
 check(map_jsons,"pinned map JSON inputs missing")
 map_ids_command=["make",*ROOT_MAKE_FLAGS,MAP_EVENT_IDS_TARGET]
 cmd(map_ids_command,cwd=fr)
 check(map_ids.is_file(),"original map event constants target produced no header")
 generated_map_ids=map_ids.read_bytes()
 check(generated_map_ids,"original map event constants output is empty")
 map_input_manifest="\n".join(
  path.relative_to(fr).as_posix()+":"+hashlib.sha256(path.read_bytes()).hexdigest()
  for path in map_jsons).encode()
 map_ids.unlink()
 cmd(map_ids_command,cwd=fr)
 check(map_ids.is_file() and map_ids.read_bytes()==generated_map_ids,
       "absent map event header was not regenerated from pinned map JSON")
 map_ids_absent_regenerated=True
 old_header_stat=map_ids.stat()
 newest_input_ns=max(path.stat().st_mtime_ns for path in map_jsons)
 stale_time_ns=max(1,newest_input_ns-2_000_000_000)
 os.utime(map_ids,ns=(old_header_stat.st_atime_ns,stale_time_ns))
 check(map_ids.stat().st_mtime_ns < newest_input_ns,
       "stale-header control did not make generated header older than its inputs")
 cmd(map_ids_command,cwd=fr)
 check(map_ids.stat().st_mtime_ns > stale_time_ns and map_ids.read_bytes()==generated_map_ids,
       "stale map event header was not regenerated from pinned map JSON")
 map_ids_stale_regenerated=True
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
   "map_event_ids_generated_by_original_root_rule":True,
   "map_event_ids_target":MAP_EVENT_IDS_TARGET,
   "map_event_ids_generation_command":"make NODEP=1 SETUP_PREREQS=0 "+MAP_EVENT_IDS_TARGET,
   "map_event_ids_input_count":len(map_jsons),
   "map_event_ids_input_manifest_sha256":hashlib.sha256(map_input_manifest).hexdigest(),
   "map_event_ids_sha256":hashlib.sha256(generated_map_ids).hexdigest(),
   "mapjson_tool_sha256":hashlib.sha256((fr/"tools/mapjson/mapjson").read_bytes()).hexdigest(),
   "absent_map_event_header_regenerated":map_ids_absent_regenerated,
   "stale_map_event_header_regenerated":map_ids_stale_regenerated,
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
   for k in ("pinned_mapjson_tool_built","map_event_ids_generated_by_original_root_rule",
     "absent_map_event_header_regenerated","stale_map_event_header_regenerated",
     "generated_map_event_ids_consumed_by_original_object"):
    check(d[k] is True,"missing map-event generation witness "+k)
   check(d["map_event_ids_target"]==MAP_EVENT_IDS_TARGET,"map event target drift")
   check(d["map_event_ids_generation_command"]=="make NODEP=1 SETUP_PREREQS=0 "+MAP_EVENT_IDS_TARGET,
         "map event generation command drift")
   check(d["map_event_ids_input_count"]>0,"map event generation inputs missing")
   for k in ("map_event_ids_input_manifest_sha256","map_event_ids_sha256","mapjson_tool_sha256"):
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
   {"pinned_mapjson_tool_built":False},{"map_event_ids_generated_by_original_root_rule":False},
   {"absent_map_event_header_regenerated":False},{"stale_map_event_header_regenerated":False},
   {"generated_map_event_ids_consumed_by_original_object":False},{"map_event_ids_input_count":0},
   {"map_event_ids_input_manifest_sha256":""},{"map_event_ids_sha256":""},
   {"mapjson_tool_sha256":""},{"map_event_ids_target":"wrong"},
   {"map_event_ids_generation_command":"wrong"}]
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
