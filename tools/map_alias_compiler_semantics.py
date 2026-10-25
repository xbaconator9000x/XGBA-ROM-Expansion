#!/usr/bin/env python3
"""Verify all 425 FireRed compiled MapHeader pointers preserve independent
shared event/script aliases, without inventing authoring source from ROM bytes.
Runs against real pinned mapjson-generated header.inc files.
"""
from pathlib import Path
import csv,gzip,hashlib,json,re,subprocess
ROOT=Path("upstream/pokefirered")
GEN=Path("map-generated/maps")
OUT=Path("map-evidence")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
COLS=("source_map","map_source_sha","source_map_id","reference_kind",
 "declared_shared_map","source_symbol","expected_compiled_target_symbol",
 "generated_header_sha256","pointer_directive_line","observed_pointer_line",
 "target_source_sha","resolution")
def blob(d):return hashlib.sha1(f"blob {len(d)}\0".encode()+d).hexdigest()
def verify_four_shared_alias_fixtures():
 """Positive-path compiler proof: independent event and script references.

 The pinned game maps happen to have no shared pointer fields. Compile synthetic
 in-memory-derived fixtures with the *original* mapjson tool without altering
 any tracked upstream files.
 """
 exe=ROOT/"tools/mapjson/mapjson"
 if not exe.is_file():raise RuntimeError("Native mapjson compiler required")
 source=ROOT/"data/maps/CeladonCity/map.json"
 data=json.loads(source.read_text())
 fixtures=[]
 for event_shared in (False,True):
  for script_shared in (False,True):
   label=f"events_{int(event_shared)}_scripts_{int(script_shared)}"
   base=Path("map-generated")/"shared-alias-fixtures"/label
   target=base/"generated";target.mkdir(parents=True,exist_ok=True)
   model=dict(data)
   model.pop("shared_events_map",None)
   model.pop("shared_scripts_map",None)
   if event_shared:model["shared_events_map"]="Route1"
   if script_shared:model["shared_scripts_map"]="PalletTown"
   inp=base/"map.json";inp.write_text(json.dumps(model,indent=2)+"\n",encoding="utf-8")
   cmd=[str(exe),"map","firered",str(inp),str(ROOT/"data/layouts/layouts.json"),str(target)]
   run=subprocess.run(cmd,capture_output=True,text=True,timeout=40)
   if run.returncode:raise RuntimeError("Native fixture compilation failed "+label+": "+run.stderr[-1200:])
   header=(target/"header.inc").read_text()
   events=(target/"events.inc").read_text()
   script_target="PalletTown" if script_shared else "CeladonCity"
   event_target="Route1" if event_shared else "CeladonCity"
   expected=[
     "\t.4byte "+event_target+"_MapEvents",
     "\t.4byte "+script_target+"_MapScripts"]
   for needle in expected:
    if needle not in header:raise RuntimeError("Wrong synthetic MapHeader pointer "+label+" "+needle)
   if event_shared and events.strip():
    raise RuntimeError("Shared-event fixture unexpectedly generated local event payload: "+label)
   if not event_shared and not events.strip():
    raise RuntimeError("Local-event fixture unexpectedly omitted event payload: "+label)
   fixtures.append({"fixture":label,"event_target":event_target,
    "script_target":script_target,"native_compiler_executed":True,
    "generated_header_sha256":hashlib.sha256(header.encode()).hexdigest(),
    "generated_events_empty":not bool(events.strip()),"pointer_semantics_verified":True})
 return fixtures

def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Source commit changed")
 groups_path=Path("data/maps/map_groups.json")
 gs=json.loads((ROOT/groups_path).read_text())
 names=[n for group in gs["group_order"] for n in gs[group]]
 if len(names)!=425:raise RuntimeError("Expected 425 mapped maps")
 manifests={}
 for name in names:
  p=Path("data/maps")/name/"map.json"
  d=(ROOT/p).read_bytes()
  expected=subprocess.check_output(["git","-C",str(ROOT),"ls-files","-s","--",str(p)],text=True).split()[1]
  if blob(d)!=expected:raise RuntimeError("Pinned authoring source mismatch "+name)
  doc=json.loads(d)
  if doc["name"]!=name:raise RuntimeError("Expected name mismatch "+name)
  manifests[name]=(expected,doc)
 counts={"map_headers":0,"event_shared_headers":0,"script_shared_headers":0,
         "event_local_headers":0,"script_local_headers":0,"alias_target_errors":0}
 errors=[];out=[]
 for name,(sha,doc) in manifests.items():
  gen=GEN/name/"header.inc"
  if not gen.is_file():raise RuntimeError("Missing compiled MapHeader "+name)
  data=gen.read_bytes();text=data.decode("utf-8","surrogateescape")
  lines=text.splitlines()
  marker=re.search(r"(?m)^"+re.escape(name)+r":\s*$",text)
  if not marker:raise RuntimeError("Missing compiled map header label "+name)
  after=text[marker.end():].splitlines()
  pointers=[]
  for n,s in enumerate(lines,1):
   if n <= text.count("\n",0,marker.start())+1:continue
   m=re.match(r"\s*\.4byte\s+([A-Za-z_]\w*)\s*(?:@.*)?$",s)
   if m:pointers.append((m.group(1),n,s.strip()))
   if len(pointers)==4:break
  # Map header sequence is layout, events, scripts, connections.
  if len(pointers)<4:raise RuntimeError("Not four MapHeader pointer fields "+name)
  if not pointers[0][0].endswith("_Layout"):
   # Layout symbols may use variant names; layout identity separately compiled.
   pass
  for typ,index,source_field,postfix in (("events",1,"shared_events_map","_MapEvents"),
                                        ("scripts",2,"shared_scripts_map","_MapScripts")):
   shared=doc.get(source_field)
   target=shared if shared else name
   if target not in manifests:
    errors.append({"source_map":name,"field":source_field,"target":target,"reason":"MISSING_AUTHORING_TARGET"})
    counts["alias_target_errors"]+=1;continue
   target_sha=manifests[target][0]
   expected=target+postfix
   observed=pointers[index][0]
   if observed!=expected:
    errors.append({"source_map":name,"field":source_field,"target":target,
      "expected":expected,"observed":observed,"reason":"COMPILED_POINTER_ALIAS_MISMATCH"})
    counts["alias_target_errors"]+=1
   out.append({"source_map":name,"map_source_sha":sha,"source_map_id":doc["id"],
     "reference_kind":typ,"declared_shared_map":shared or "",
     "source_symbol":name,"expected_compiled_target_symbol":expected,
     "generated_header_sha256":hashlib.sha256(data).hexdigest(),
     "pointer_directive_line":pointers[index][1],
     "observed_pointer_line":pointers[index][2],
     "target_source_sha":target_sha,
     "resolution":"NATIVE_MAPJSON_POINTER_ALIAS_COMPILED" if observed==expected else "MISMATCH"})
   counts[typ[:-1]+"_shared_headers" if shared else typ[:-1]+"_local_headers"]+=1
  counts["map_headers"]+=1
 OUT.mkdir(exist_ok=True)
 with gzip.open(OUT/"map_compiled_shared_pointer_aliases.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=COLS);w.writeheader();w.writerows(out)
 fixtures=verify_four_shared_alias_fixtures()
  summary={"pinned_source_commit":PIN,
   "map_header_pointer_checks":len(out),"map_header_files":counts["map_headers"],
   "positive_shared_pointer_compiler_fixtures":fixtures,
   "shared_event_pointers":counts["event_shared_headers"],
   "shared_script_pointers":counts["script_shared_headers"],
   "own_event_pointers":counts["event_local_headers"],
   "own_script_pointers":counts["script_local_headers"],
   "compiler_pointer_alias_errors":errors,"compiler_executed":True,
   "authoring_roundtrip_reverse_from_binary":False,
   "compiled_pointer_memory_address_equality_tested":False,
   "phase1_semantic_mapping_complete":False,"whole_file_signoffs":0,
   "compatibility_rule":"Never flatten shared_events_map and shared_scripts_map into one shared-map relationship.",
   "limitations":["Assembler symbol identities are verified; final linked ROM pointer addresses are not compared.",
    "Original authored alias names can be lost when reconstructing compiled ROMs."]}
 (OUT/"map_compiled_shared_pointer_aliases_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("compiler_pointer_alias_errors","limitations")},indent=2))
 if counts["map_headers"]!=425 or len(out)!=850 or errors:
  raise RuntimeError("Compiled MapHeader alias mismatch: "+str(errors[:5]))
if __name__=="__main__":main()
