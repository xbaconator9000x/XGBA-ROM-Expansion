#!/usr/bin/env python3
"""Build the pinned FireRed map compiler and audit every map's typed semantics.

Runs the *original native mapjson tool* over every pinned map.json, map group,
layout and event constant. Verifies generated assembler macro event counts,
layout binary geometry, IDs, typed warp targets, scripts and source blob hashes.
This proves authoring-source -> generated typed map data, NOT round-trip
decoding of a flattened arbitrary .gba ROM.
"""
from __future__ import annotations
import collections,csv,hashlib,json,re,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path("upstream/pokefirered").resolve()
OUT=Path("map-evidence").resolve()
GEN=Path("map-generated").resolve()
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
TYPES=("object_events","warp_events","coord_events","bg_events")
MACROS={
 "object_events":{"object":"object_event","clone":"clone_event"},
 "warp_events":{"warp":"warp_def"},
 "coord_events":{"trigger":"coord_event","weather":"coord_weather_event"},
 "bg_events":{"sign":"bg_sign_event","hidden_item":"bg_hidden_item_event","secret_base":"bg_secret_base_event"}}
EVENT_COLS=["map_name","map_id","map_git_blob_sha","map_group","layout_id",
            "category","index","event_type","x","y","elevation",
            "script","dest_map","dest_warp_id","dest_map_exists",
            "source_event_json_sha256","within_layout_bounds"]
EDGE_COLS=["source_map","source_map_id","edge_kind","target_map",
           "target_map_id","target_exists","source_reference"]
def sha1_blob(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def sha256(data):return hashlib.sha256(data).hexdigest()
def gittracked(path):
 return subprocess.check_output(["git","-C",str(ROOT),"ls-files","-s","--",str(path)],text=True).strip().split()[1]
def readtracked(path):
 p=ROOT/path
 data=p.read_bytes()
 if sha1_blob(data)!=gittracked(path):
  raise RuntimeError("Changed source blob: "+str(path))
 return data
def run(*args):
 r=subprocess.run(args,capture_output=True,text=True,timeout=50)
 if r.returncode:
  raise RuntimeError("Native mapjson failed: "+str(args[:6])+"\n"+r.stderr[-1800:])
 return r
def macro_count(text,macro):
 return len(re.findall(r"(?m)^\s*"+re.escape(macro)+r"\s+",text))
def main():
 OUT.mkdir(exist_ok=True)
 for d in [GEN/"maps",GEN/"layouts",GEN/"includes"]:
  d.mkdir(parents=True,exist_ok=True)
 commit=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if commit!=PIN:raise RuntimeError("FireRed pinned commit mismatch")
 groups=json.loads(readtracked(Path("data/maps/map_groups.json")))
 layouts=json.loads(readtracked(Path("data/layouts/layouts.json")))
 group_order=groups["group_order"]
 names=[(group,name) for group in group_order for name in groups[group]]
 if len(names)!=425 or len(group_order)!=43:raise RuntimeError("Expected pinned 425 maps and 43 groups")
 layouts_by_id={x["id"]:x for x in layouts["layouts"] if isinstance(x,dict) and x.get("id")}
 if len(layouts["layouts"])!=383 or len(layouts_by_id)!=365:
  raise RuntimeError("Expected pinned 383 layout slots incl 18 blank")
 layout_provenance={}
 layout_issues=[];verified_layout_bytes=0
 for lid,entry in layouts_by_id.items():
  width,height=int(entry["width"]),int(entry["height"])
  for typ,col,row in (("map","width","height"),("border","border_width","border_height")):
   key="blockdata_filepath" if typ=="map" else "border_filepath"
   path=Path(entry[key])
   data=readtracked(path)
   expected=int(entry[col])*int(entry[row])*2
   # Width x height u16 metatile blocks, or border_width x border_height
   state="DIMENSIONS_MATCH_RAW_U16" if len(data)==expected else "SIZE_OR_LAYOUT_MISMATCH_REQUIRES_REVIEW"
   if state!="DIMENSIONS_MATCH_RAW_U16":
    layout_issues.append({"layout":lid,"path":str(path),"bytes":len(data),"expected":expected})
   layout_provenance[str(path)]={"git_blob_sha":gittracked(path),"bytes":len(data),
      "layout_id":lid,"block_kind":typ,"expected_bytes":expected,"status":state}
   verified_layout_bytes+=len(data)
 exe=ROOT/"tools/mapjson/mapjson"
 if not exe.is_file():raise RuntimeError("Native mapjson binary absent: build tools/mapjson before audit")
 run(str(exe),"layouts","firered",str(ROOT/"data/layouts/layouts.json"),str(GEN/"layouts"),str(GEN/"includes"))
 run(str(exe),"groups","firered",str(ROOT/"data/maps/map_groups.json"),str(GEN/"maps"),str(GEN/"includes"))
 mapdata={};maphash={};idname={}
 for group,name in names:
  rel=Path("data/maps")/name/"map.json"
  raw=readtracked(rel)
  j=json.loads(raw);mapdata[name]=j;maphash[name]=gittracked(rel)
  if j["name"]!=name:raise RuntimeError("Map JSON name disagrees with group: "+name)
  ident=j["id"]
  if ident in idname:raise RuntimeError("Duplicate map ID "+ident)
  idname[ident]=name
  if j["layout"] not in layouts_by_id:raise RuntimeError("Unknown layout for "+name)
 scene_counts=collections.Counter();macro_mismatches=[];out_of_bounds=[];unresolved_warps=[]
 generated_hashes={};edges=[];event_records=[]
 with (OUT/"map_event_semantics.csv").open("w",newline="",encoding="utf-8") as f:
  events=csv.DictWriter(f,fieldnames=EVENT_COLS);events.writeheader()
  for idx,(group,name) in enumerate(names,1):
   j=mapdata[name];lid=j["layout"];layout=layouts_by_id[lid]
   outdir=GEN/"maps"/name
   outdir.mkdir(parents=True,exist_ok=True)
   run(str(exe),"map","firered",str(ROOT/"data/maps"/name/"map.json"),
       str(ROOT/"data/layouts/layouts.json"),str(outdir))
   outputs={}
   for suffix in ("header.inc","events.inc","connections.inc"):
    path=outdir/suffix
    if not path.exists():raise RuntimeError(f"Generated map output absent {name}/{suffix}")
    raw=path.read_bytes()
    generated_hashes[f"maps/{name}/{suffix}"]=sha256(raw)
    outputs[suffix]=raw.decode("utf-8","replace")
   shared="shared_events_map" in j
   for category in TYPES:
    members=j.get(category,[])
    for event_idx,event in enumerate(members):
     kind=event.get("type","object" if category=="object_events" else "warp")
     if kind not in MACROS[category]:
      raise RuntimeError(f"Unexpected typed event {name}/{category}/{kind}")
     scene_counts[category]+=1
     dest=event.get("dest_map") or event.get("target_map") or ""
     target=idname.get(dest,"")
     if dest and not target:
      unresolved_warps.append({"map":name,"event":category,"dest_map":dest,"index":event_idx})
     x,y=event.get("x"),event.get("y")
     bounds=bool(isinstance(x,int) and isinstance(y,int) and 0<=x<int(layout["width"]) and 0<=y<int(layout["height"]))
     if not bounds:out_of_bounds.append({"map":name,"category":category,"index":event_idx,"x":x,"y":y})
     events.writerow({"map_name":name,"map_id":j["id"],"map_git_blob_sha":maphash[name],
      "map_group":group,"layout_id":lid,"category":category,"index":event_idx,
      "event_type":kind,"x":x,"y":y,"elevation":event.get("elevation",""),
      "script":event.get("script",""),"dest_map":dest,
      "dest_warp_id":event.get("dest_warp_id",""),"dest_map_exists":bool(target),
      "source_event_json_sha256":sha256(json.dumps(event,sort_keys=True,separators=(",",":")).encode()),
      "within_layout_bounds":bounds})
     if dest:
      edges.append({"source_map":name,"source_map_id":j["id"],"edge_kind":category,
       "target_map":target,"target_map_id":dest,"target_exists":bool(target),
       "source_reference":f"{category}[{event_idx}]"})
   if not shared:
    for category in TYPES:
     group_expected=collections.Counter(
      MACROS[category][e.get("type","object" if category=="object_events" else "warp")]
      for e in j.get(category,[]))
     for macro,expected in group_expected.items():
      observed=macro_count(outputs["events.inc"],macro)
      if observed!=expected:macro_mismatches.append((name,category,macro,expected,observed))
   elif outputs["events.inc"].strip():
    macro_mismatches.append((name,"shared","nonempty_generated_events","",outputs["events.inc"][:80]))
   actual_connections=macro_count(outputs["connections.inc"],"connection")
   expected_connections=len(j.get("connections",[]))
   if actual_connections!=expected_connections:
    # A source map can set connections_no_include; still generated connections
    # itself should match its JSON list.
    macro_mismatches.append((name,"connections","connection",expected_connections,actual_connections))
   for i,conn in enumerate(j.get("connections",[])):
    dest=conn["map"];target=idname.get(dest,"")
    edges.append({"source_map":name,"source_map_id":j["id"],"edge_kind":"connection",
      "target_map":target,"target_map_id":dest,"target_exists":bool(target),
      "source_reference":f"connections[{i}]"})
   for extra in ("shared_scripts_map","shared_events_map"):
    dest=j.get(extra)
    if dest:
     edges.append({"source_map":name,"source_map_id":j["id"],"edge_kind":extra,
       "target_map":dest,"target_map_id":mapdata[dest]["id"] if dest in mapdata else "",
       "target_exists":dest in mapdata,"source_reference":extra})
   if idx%50==0:
    (OUT/f"checkpoint_{idx:03d}.json").write_text(json.dumps({
      "compiled_maps":idx,"typed_events":sum(scene_counts.values()),
      "source_semantic_signoffs":0,"compiler_parse_status":"IN_PROGRESS"})+"\n")
 with (OUT/"map_references.csv").open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=EDGE_COLS);w.writeheader();w.writerows(edges)
 paths=[str(ROOT/"data/maps"/name/"map.json") for _,name in names]
 run(str(exe),"event_constants","firered",*paths,str(GEN/"includes"/"map_event_ids.h"))
 for root in [GEN/"layouts",GEN/"maps",GEN/"includes"]:
  for p in root.rglob("*.inc"):
   rel=p.relative_to(GEN).as_posix()
   if rel not in generated_hashes:generated_hashes[rel]=sha256(p.read_bytes())
 for p in (GEN/"includes").glob("*.h"):
  generated_hashes[p.relative_to(GEN).as_posix()]=sha256(p.read_bytes())
 with tarfile.open(OUT/"compiled_map_includes.tar.gz","w:gz") as t:
  t.add(GEN,arcname="generated-map-includes")
 summary={
  "pinned_revision":PIN,"groups":len(group_order),"maps_compiled_successfully":len(names),
  "layout_slots":len(layouts["layouts"]),"nonempty_layouts":len(layouts_by_id),
  "layout_binary_bytes_verified":verified_layout_bytes,
  "layout_binary_mismatches":layout_issues[:60],
  "typed_event_counts":dict(scene_counts),"all_typed_events":sum(scene_counts.values()),
  "map_to_map_edges":len(edges),"unknown_target_map_references":len(unresolved_warps),
  "unknown_target_samples":unresolved_warps[:35],
  "events_outside_layout_bounds":len(out_of_bounds),
  "out_of_bounds_samples":out_of_bounds[:40],
  "generated_event_macro_count_errors":macro_mismatches[:60],
  "generated_output_files":len(generated_hashes),
  "compiler_executed":"pinned tools/mapjson native C++11 compiler",
  "semantic_semantics_verified":"source JSON -> actual generated typed map and layout assembler",
  "arbitrary_binary_ROM_import_decoding_tested":False,
  "file_semantic_signoffs":0,"phase1_mapping_complete":False}
 (OUT/"map_semantics_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 (OUT/"generated_map_file_hashes.json").write_text(json.dumps(generated_hashes,indent=2,sort_keys=True)+"\n")
 (OUT/"layout_binary_verification.json").write_text(json.dumps(layout_provenance,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("out_of_bounds_samples","unknown_target_samples","layout_binary_mismatches","generated_event_macro_count_errors")},indent=2))
 if macro_mismatches:raise RuntimeError("Generated assembler event counts differ: "+str(macro_mismatches[:5]))
 if layout_issues:raise RuntimeError("Pinned source layout binary geometry mismatches: "+str(layout_issues[:5]))
if __name__=="__main__":main()
