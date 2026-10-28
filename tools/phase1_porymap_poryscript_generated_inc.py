#!/usr/bin/env python3
"""Source-pinned Porymap -> Poryscript -> FireRed generated include contract."""
import argparse, hashlib, json, subprocess
from pathlib import Path

PINS = {
 "porymap": ("26b919d7ff4b54152de010abd5bf344af2ebe116", {"src/project.cpp":"d43b0949303433111d4478ad76117c2b3445dd13"}),
 "poryscript": ("c32481161c767b25a3425fa9f1f8729927ff3d55", {"README.md":"c77e022eb86e74a41b184daac5953d14c72cacc3"}),
 "firered": ("ce6406d8c2eaf46d543c8a2606de0c3cb1951982", {
  "Makefile":"8b454dbd18eb0069fa5851d788697190890a5b37",
  "config.mk":"c07d31fc083fa341cca29c340e560ed107d5364a",
  "make_tools.mk":"d7b9315ad7beb37116793d8f805160679d3b4001",
  "graphics_file_rules.mk":"39b952cd45b6a34eb98318a76aa531fcafff134d",
  "tileset_rules.mk":"a868248cf07750504eec7d87c772e089c60aa211",
  "map_data_rules.mk":"b32b85a91d9460642345ca983c37d165e820741f",
  "spritesheet_rules.mk":"50cfd49796bbf5036119f5e2116ae9932d6a1216",
  "json_data_rules.mk":"eec18467a57cce082a4307b3d667c4c4448b1b3a",
  "audio_rules.mk":"6b4e4afda840dbce45892a6b01c5e114deb1fd12",
 })}
RULES=("config.mk","make_tools.mk","graphics_file_rules.mk","tileset_rules.mk","map_data_rules.mk","spritesheet_rules.mk","json_data_rules.mk","audio_rules.mk")
def require(ok,why):
 if not ok: raise ValueError(why)
def extract(src,name,result="QString"):
 needle=result+" Project::"+name+"("
 require(src.count(needle)==1,"function changed: "+name)
 i=src.index(needle); j=src.find("\n}\n",i)
 require(j>i,"function not closed: "+name)
 return src[i:j+2]
def check(pm,ps,fr):
 save=extract(pm,"saveMap","bool")
 ext=extract(pm,"getScriptFileExtension")
 defaults=extract(pm,"getScriptDefaultString")
 files=extract(pm,"findScriptsFiles","QStringList")
 require('return ".pory";' in ext and 'return ".inc";' in ext,"Porymap extensions changed")
 require('saveTextFile(fullPath + "/scripts" + this->getScriptFileExtension(projectConfig.usePoryScript), text);' in save,"script creation changed")
 require('scripts.inc' in save and 'text.inc' in save and 'appendTextFile(root + "/"' in save,"event script include changed")
 require('mapscripts %1_MapScripts {}' in defaults,"default Poryscript syntax changed")
 require('filters.append(s + getScriptFileExtension(true));' in files,"Porymap .pory search changed")
 require('./poryscript -i data/scripts/myscript.pory -o data/scripts/myscript.inc' in ps,"Poryscript CLI command changed")
 require('AUTO_GEN_TARGETS += $(patsubst %.pory,%.inc,$(shell find data/ -type f -name' in ps,"documented Makefile target changed")
 require('data/%.inc: data/%.pory; $(SCRIPT) -i $< -o $@' in ps,"documented generation rule changed")
 make=fr["Makefile"]
 require("AUTO_GEN_TARGETS :=" in make and "generated: $(AUTO_GEN_TARGETS)" in make,"FireRed target changed")
 for path in RULES:
  require("include "+path in make,"FireRed include changed: "+path)
 for path,content in fr.items():
  require("poryscript" not in content.lower() and ".pory" not in content.lower(),"FireRed Poryscript integration present: "+path)
def controls(pm,ps,fr):
 changes=[
  ("pm",'return ".pory";','return ".inc";'),
  ("pm",'scripts.inc','scripts.pory'),
  ("pm",'mapscripts %1_MapScripts {}','script %1_MapScripts {}'),
  ("pm",'filters.append(s + getScriptFileExtension(true));','filters.append(s + getScriptFileExtension(false));'),
  ("ps",'./poryscript -i data/scripts/myscript.pory -o data/scripts/myscript.inc','./poryscript -i data/scripts/myscript.pory -x data/scripts/myscript.inc'),
  ("ps",'data/%.inc: data/%.pory; $(SCRIPT)','data/%.inc: data/%.s; $(SCRIPT)'),
  ("fr",'AUTO_GEN_TARGETS :=','AUTO_GEN_TARGETS := $(patsubst %.pory,%.inc,$(shell find data/ -name "*.pory"))'),
  ("rule",'',''),
 ]
 for idx,(kind,old,new) in enumerate(changes):
  a,b,c=pm,ps,dict(fr)
  if kind=="pm":
   require(old in a,"missing Porymap mutation"); a=a.replace(old,new,1)
  elif kind=="ps":
   require(old in b,"missing Poryscript mutation"); b=b.replace(old,new,1)
  elif kind=="fr":
   require(old in c["Makefile"],"missing Makefile mutation"); c["Makefile"]=c["Makefile"].replace(old,new,1)
  else: c["map_data_rules.mk"]+="\n# poryscript .pory rule\n"
  try: check(a,b,c)
  except ValueError: continue
  raise ValueError("source mutation escaped "+str(idx))
 return len(changes)
def main():
 ap=argparse.ArgumentParser()
 for name in PINS: ap.add_argument("--"+name,type=Path,required=True)
 ap.add_argument("--output",type=Path,required=True); args=ap.parse_args()
 source={}
 for name,(pin,blobs) in PINS.items():
  root=getattr(args,name)
  def git(*cmd): return subprocess.check_output(["git","-C",str(root),*cmd],text=True).strip()
  require(git("rev-parse","HEAD")==pin,"upstream commit drift "+name)
  source[name]={}
  for path,blob in blobs.items():
   require(git("hash-object",path)==blob,"upstream blob drift "+name+"/"+path)
   source[name][path]=(root/path).read_text()
 pm=source["porymap"]["src/project.cpp"]; ps=source["poryscript"]["README.md"]; fr=source["firered"]
 check(pm,ps,fr); n=controls(pm,ps,fr)
 evidence={"class":"PINNED_PORYMAP_PORYSCRIPT_FIRERED_GENERATED_INCLUDE_DEPENDENCY",
  "pins":{k:v[0] for k,v in PINS.items()},
  "source_git_blobs":{k:v[1] for k,v in PINS.items()},
  "source_sha256":{k:{p:hashlib.sha256(s.encode()).hexdigest() for p,s in src.items()} for k,src in source.items()},
  "porymap_creates_pory_but_includes_inc":True,
  "poryscript_documents_generated_inc_make_rule":True,
  "stock_firered_root_and_included_rules_contain_poryscript":False,
  "stock_firered_with_new_pory_full_build_executed":False,
  "native_editor_generated_include_executed":False,
  "source_mutations_rejected":n,"independent_approvals":0,"gate":"FAIL_INCOMPLETE"}
 def validate(d):
  require(d["source_mutations_rejected"]==8,"source controls missing")
  require(d["porymap_creates_pory_but_includes_inc"] and d["poryscript_documents_generated_inc_make_rule"],"generation contract changed")
  require(d["stock_firered_root_and_included_rules_contain_poryscript"] is False,"stock integration overclaimed")
  require(d["stock_firered_with_new_pory_full_build_executed"] is False and d["native_editor_generated_include_executed"] is False,"runtime overclaimed")
  require(d["independent_approvals"]==0 and d["gate"]=="FAIL_INCOMPLETE","gate overclaimed")
 validate(evidence)
 negatives=[{"source_mutations_rejected":7},{"porymap_creates_pory_but_includes_inc":False},
  {"poryscript_documents_generated_inc_make_rule":False},
  {"stock_firered_root_and_included_rules_contain_poryscript":True},
  {"stock_firered_with_new_pory_full_build_executed":True},
  {"native_editor_generated_include_executed":True},
  {"independent_approvals":1},{"gate":"PASS"}]
 for i,change in enumerate(negatives):
  try: validate({**evidence,**change})
  except ValueError: continue
  raise ValueError("evidence mutation escaped "+str(i))
 evidence["evidence_mutations_rejected"]=len(negatives)
 args.output.parent.mkdir(parents=True,exist_ok=True)
 args.output.write_text(json.dumps(evidence,sort_keys=True,indent=2)+"\n")
 print(json.dumps(evidence,sort_keys=True))
if __name__=="__main__": main()
