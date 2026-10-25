#!/usr/bin/env python3
"""Prove FireRed clone-event target identities and classify out-of-bounds clones.

Pinned authoring maps can legitimately place clone references just outside their
layout. This is not a corruption signal. Prove identity by referenced map ID and
local event constant, not a same-map coordinate heuristic.
"""
import collections,csv,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered")
OUT=Path("map-evidence")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
HEAD=["source_map","source_id","source_map_sha","clone_slot","clone_x","clone_y",
      "source_layout","source_layout_width","source_layout_height","outside_layout",
      "target_map_id","target_map_name","target_map_sha","target_local_id",
      "resolved_target_slot","target_local_constant","resolution"]
def gitsha(b):return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def canonical(path):
 p=ROOT/path
 content=p.read_bytes()
 sha=subprocess.check_output(["git","-C",str(ROOT),"ls-files","-s","--",str(path)],text=True).split()[1]
 if gitsha(content)!=sha:raise RuntimeError("Source hash changed: "+str(path))
 return content,sha
def main():
 sha=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if sha!=PIN:raise RuntimeError("Wrong FireRed source commit")
 grouped=json.loads(canonical(Path("data/maps/map_groups.json"))[0])
 layout_doc=json.loads(canonical(Path("data/layouts/layouts.json"))[0])
 layouts={r["id"]:r for r in layout_doc["layouts"] if isinstance(r,dict) and r.get("id")}
 names=[n for group in grouped["group_order"] for n in grouped[group]]
 if len(names)!=425:raise RuntimeError("Wrong pinned map count")
 maps={}
 for name in names:
  p=Path("data/maps")/name/"map.json"
  b,sha=canonical(p)
  obj=json.loads(b)
  if obj.get("name")!=name:raise RuntimeError("Map name mismatch "+name)
  if obj["id"] in maps:raise RuntimeError("Duplicate map ID: "+obj["id"])
  maps[obj["id"]]={"name":name,"data":obj,"sha":sha}
 rows=[];issues=[];bykind=collections.Counter();outmaps=[]
 for mid,r in maps.items():
  doc=r["data"]
  layout=layouts.get(doc.get("layout"))
  if not layout:raise RuntimeError("Source map lacks declared layout: "+r["name"])
  width,height=layout["width"],layout["height"]
  for i,obj in enumerate(doc["object_events"],1):
   x,y=obj["x"],obj["y"]
   if not isinstance(x,int) or not isinstance(y,int):raise RuntimeError("Non-integer map coordinate")
   outside=not(0<=x<width and 0<=y<height)
   kind=obj.get("type","object")
   if kind!="clone":
    if outside:issues.append({"map":r["name"],"event_slot":i,"reason":"NORMAL_OBJECT_OUTSIDE_LAYOUT"})
    bykind["normal"]+=1
    continue
   bykind["clones"]+=1
   targetid=obj.get("target_map");localid=obj.get("target_local_id")
   trg=maps.get(targetid)
   targetslot=None;targetconst=None
   resolution="UNRESOLVED"
   if not trg:
    issues.append({"map":r["name"],"slot":i,"reason":"UNKNOWN_CLONE_TARGET_MAP","target":targetid})
   else:
    objects=trg["data"]["object_events"]
    matches=[(j,o) for j,o in enumerate(objects,1) if o.get("local_id")==localid]
    if isinstance(localid,int) and 1<=localid<=len(objects):
     matches=[(localid,objects[localid-1])]
    if len(matches)==1:
     targetslot=matches[0][0];targetconst=matches[0][1].get("local_id")
     resolution="PINNED_MAP_LOCAL_ID_RESOLVED"
     if matches[0][1].get("type")=="clone":
      issues.append({"map":r["name"],"slot":i,"reason":"CLONE_TARGET_IS_CLONE","target":targetid})
    else:
     issues.append({"map":r["name"],"slot":i,"reason":"CLONE_TARGET_LOCAL_ID_NOT_UNIQUELY_RESOLVED","target":targetid,"local_id":localid})
   row={"source_map":r["name"],"source_id":mid,"source_map_sha":r["sha"],
     "clone_slot":i,"clone_x":x,"clone_y":y,"source_layout":doc["layout"],
     "source_layout_width":width,"source_layout_height":height,"outside_layout":outside,
     "target_map_id":targetid,"target_map_name":trg["name"] if trg else "",
     "target_map_sha":trg["sha"] if trg else "","target_local_id":localid,
     "resolved_target_slot":targetslot,"target_local_constant":targetconst,"resolution":resolution}
   rows.append(row)
   if outside:outmaps.append(row);bykind["offmap_clone"]+=1
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/"clone_crossmap_semantics.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=HEAD);w.writeheader();w.writerows(rows)
 result={"pinned_commit":PIN,"maps_verified":len(maps),"clone_events":len(rows),
  "clones_outside_local_layout":len(outmaps),"all_outside_events_are_clones":not any(
    x["reason"]=="NORMAL_OBJECT_OUTSIDE_LAYOUT" for x in issues),
  "resolved_clone_local_ids":sum(x["resolution"]=="PINNED_MAP_LOCAL_ID_RESOLVED" for x in rows),
  "unresolved_target_issues":issues,"out_of_bounds_clone_examples":
    [{"source_map":r["source_map"],"x":r["clone_x"],"y":r["clone_y"],
      "target_map":r["target_map_id"],"target_local_id":r["target_local_id"]} for r in outmaps],
  "semantic_scope":"SOURCE_MAP_LOCAL_ID_TARGETS_VERIFIED_NOT_COMPILED_OBJECT_MOTION",
  "source_files_independently_approved":0,"phase1_complete":False}
 (OUT/"clone_crossmap_semantics_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in result.items() if k not in ("unresolved_target_issues","out_of_bounds_clone_examples")},indent=2))
 # Recovered compiler map proof showed precisely nine out-of-bounds clones.
 if len(outmaps)!=9:raise RuntimeError("Unexpected out-of-bounds clone count: "+str(len(outmaps)))
 if issues:raise RuntimeError("Unresolved clone identities: "+str(issues[:10]))
if __name__=="__main__":main()
