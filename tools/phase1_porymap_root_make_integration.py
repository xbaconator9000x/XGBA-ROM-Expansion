#!/usr/bin/env python3
"""Execute pinned FireRed ROOT Makefile Poryscript generation and data object."""
import argparse, hashlib, json, re, shutil, subprocess
from pathlib import Path
PINS = {
 "firered": ("ce6406d8c2eaf46d543c8a2606de0c3cb1951982", {
  "Makefile":"8b454dbd18eb0069fa5851d788697190890a5b37",
  "data/event_scripts.s":"88d75946a7300ccf952f4a36c283966c6aebf5c0",
  "tools/preproc/preproc.cpp":"20c2de51b635a5d59f2b4e1ecd93d8fc2748ebe1"}),
 "poryscript": ("c32481161c767b25a3425fa9f1f8729927ff3d55",{
  "README.md":"c77e022eb86e74a41b184daac5953d14c72cacc3"}),
 "porymap": ("26b919d7ff4b54152de010abd5bf344af2ebe116",{
  "src/project.cpp":"d43b0949303433111d4478ad76117c2b3445dd13"})}
TARGET="AUTO_GEN_TARGETS += $(patsubst %.pory,%.inc,$(shell find data/ -type f -name '*.pory'))"
RULE="data/%.inc: data/%.pory; $(SCRIPT) -i $< -o $@ -fc tools/poryscript/font_config.json -cc tools/poryscript/command_config.json"
def check(x,msg):
 if not x: raise RuntimeError(msg)
def cmd(args,cwd=None,ok=True):
 p=subprocess.run(args,cwd=cwd,text=True,capture_output=True)
 if ok: check(p.returncode==0,str(args)+" failed: "+p.stderr[-2000:]+p.stdout[-1000:])
 return p
def source_contract(fr,ps,pm):
 check("AUTO_GEN_TARGETS :=" in fr and "generated: $(AUTO_GEN_TARGETS)" in fr,"root generated target drift")
 check("$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.s" in fr,"original data rule drift")
 check("$(PREPROC) $< charmap.txt | $(CPP) $(INCLUDE_SCANINC_ARGS) - | $(PREPROC) -ie $< charmap.txt | $(AS) $(ASFLAGS) -o $@" in fr,"native recipe drift")
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
 source_contract(make,readme,project)
 mutations=[(0,"AUTO_GEN_TARGETS :=","AUTO_GEN_TARGETS ="),
  (0,"generated: $(AUTO_GEN_TARGETS)","generated:"),
  (0,"$(PREPROC) -ie $< charmap.txt","cat"),
  (0,"$(DATA_ASM_BUILDDIR)/%.o: $(DATA_ASM_SUBDIR)/%.s","missing:"),
  (1,TARGET,"AUTO_GEN_TARGETS += wrong"),
  (1,RULE,RULE.replace("-o $@","-x $@")),
  (2,'return ".pory";','return ".inc";'),
  (2,"mapscripts %1_MapScripts {}","script %1_MapScripts {}")]
 for i,(n,old,new) in enumerate(mutations):
  sources=[make,readme,project]
  check(old in sources[n],"mutation anchor missing "+str(i))
  sources[n]=sources[n].replace(old,new,1)
  try: source_contract(*sources)
  except RuntimeError: continue
  raise RuntimeError("source mutation escaped "+str(i))
 cli=fr/"tools/poryscript/poryscript";cli.parent.mkdir(parents=True,exist_ok=True)
 cmd(["go","build","-o",str(cli),"."],cwd=ps)
 for name in ("font_config.json","command_config.json"):
  shutil.copyfile(ps/name,cli.parent/name)
 cmd(["make","-C",str(fr/"tools/preproc"),"-j2"])
 probe=fr/"data/maps/XGBAProbe";probe.mkdir(parents=True,exist_ok=True)
 inp=probe/"scripts.pory";inp.write_text("mapscripts XGBAProbe_MapScripts {}\n")
 inc=probe/"scripts.inc";obj=fr/"build/firered/data/event_scripts.o"
 overlay=make.replace("AUTO_GEN_TARGETS :=","AUTO_GEN_TARGETS :=\n"+TARGET,1).replace(
  "generated: $(AUTO_GEN_TARGETS)","SCRIPT := tools/poryscript/poryscript\n"+RULE+"\ngenerated: $(AUTO_GEN_TARGETS)",1)
 check(overlay.count(TARGET)==1 and overlay.count(RULE)==1,"overlay drift")
 (fr/"Makefile").write_text(overlay)
 (fr/"data/event_scripts.s").write_text(event+'\n\t.include "data/maps/XGBAProbe/scripts.inc"\n')
 try:
  database=cmd(["make","-qp","NODEP=1"],cwd=fr,ok=False)
  check(database.returncode in (0,1),"root make database parse failed: "+database.stderr[-1500:])
  check(any(line.startswith("generated:") and "data/maps/XGBAProbe/scripts.inc" in line for line in database.stdout.splitlines()),"root generated target omits Poryscript output")
  cmd(["make","NODEP=1","data/maps/XGBAProbe/scripts.inc"],cwd=fr)
  check(inc.is_file() and b"XGBAProbe_MapScripts" in inc.read_bytes(),"root generated output missing")
  generated=inc.read_bytes()
  cmd(["make","NODEP=1","build/firered/data/event_scripts.o"],cwd=fr)
  check(obj.is_file(),"root event object absent")
  symbols=cmd(["arm-none-eabi-nm",str(obj)]).stdout
  check(len(re.findall(r"\bXGBAProbe_MapScripts\b",symbols))==1,"original event object symbol missing")
  nochange=cmd(["make","-n","NODEP=1","data/maps/XGBAProbe/scripts.inc"],cwd=fr).stdout
  check("poryscript -i" not in nochange,"unchanged input regenerated")
  (fr/"Makefile").write_text(overlay.replace(RULE+"\n","",1));inc.unlink()
  check(cmd(["make","NODEP=1","data/maps/XGBAProbe/scripts.inc"],cwd=fr,ok=False).returncode!=0,"missing rule accepted")
  (fr/"Makefile").write_text(overlay);inp.write_text("mapscripts Broken {\n")
  check(cmd(["make","NODEP=1","data/maps/XGBAProbe/scripts.inc"],cwd=fr,ok=False).returncode!=0,"malformed source accepted")
  inp.write_text("mapscripts XGBAProbe_MapScripts {}\n")
  cmd(["make","NODEP=1","data/maps/XGBAProbe/scripts.inc"],cwd=fr)
  check(inc.read_bytes()==generated,"recovery changed generated bytes")
  evidence={"class":"PINNED_FIRERED_ROOT_MAKE_PORYSCRIPT_EVENT_OBJECT",
   "upstream_pins":{k:v[0] for k,v in PINS.items()},
   "source_blobs":{k:v[1] for k,v in PINS.items()},
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
   check(d["source_mutations_rejected"]==8,"source negative drift")
   for k in ("root_generated_target_discovered","original_root_event_object_compiled",
    "original_event_source_preserved_with_one_test_include","generated_symbol_linkable_object",
    "unchanged_skips_generation","missing_rule_rejected","malformed_input_rejected","recovery_byte_identical"):
    check(d[k] is True,"missing witness "+k)
   for k in ("full_rom_linked","mgba_runtime_executed","porymap_gui_executed"):
    check(d[k] is False,"scope overclaim "+k)
   check(d["independent_approvals"]==0 and d["phase1_gate"]=="FAIL_INCOMPLETE","false approval")
   check(len(d["event_object_sha256"])==64,"object identity missing")
  verify(evidence)
  negatives=[{"source_mutations_rejected":7},{"root_generated_target_discovered":False},
   {"original_root_event_object_compiled":False},{"original_event_source_preserved_with_one_test_include":False},
   {"generated_symbol_linkable_object":False},{"unchanged_skips_generation":False},
   {"missing_rule_rejected":False},{"malformed_input_rejected":False},
   {"recovery_byte_identical":False},{"full_rom_linked":True},{"mgba_runtime_executed":True},
   {"porymap_gui_executed":True},{"independent_approvals":1},{"phase1_gate":"PASS"},
   {"event_object_sha256":""}]
  for i,change in enumerate(negatives):
   try: verify({**evidence,**change})
   except RuntimeError: continue
   raise RuntimeError("evidence mutation escaped "+str(i))
  evidence["evidence_mutations_rejected"]=len(negatives)
  a.output.parent.mkdir(parents=True,exist_ok=True)
  a.output.write_text(json.dumps(evidence,indent=2,sort_keys=True)+"\n")
  print(json.dumps(evidence,sort_keys=True))
 finally:
  (fr/"Makefile").write_text(make)
  (fr/"data/event_scripts.s").write_text(event)
if __name__=="__main__": main()
