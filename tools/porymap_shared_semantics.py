#!/usr/bin/env python3
"""Map inheritance: verified source-level branch semantics of pinned Porymap.

A map may inherit typed events independently from scripts. Adding local events
breaks the no-local-events inheritance predicate. This tool proves the exact
read/write branches at pinned source bytes; it does not emulate Qt execution.
"""
from pathlib import Path
import hashlib,json,re,subprocess,sys
ROOT=Path("upstream/porymap")
OUT=Path("porymap-compiler-evidence")
PIN="26b919d7ff4b54152de010abd5bf344af2ebe116"
BLOBS={
 "include/core/map.h":"47d52b08e4a403e88c80c0d436f563460721e65d",
 "src/core/map.cpp":"47b279919bd4afcc76b88f9eeecd459b3452989f",
 "src/project.cpp":"d43b0949303433111d4478ad76117c2b3445dd13",
 "src/mainwindow.cpp":"08ce1a7a599ef825967717b69626984cdc6d772b"}
PATTERNS={
 "INHERIT_EVENTS_REQUIRES_NO_LOCAL_EVENTS":("include/core/map.h",r"isInheritingEvents\(\)\s+const\s+\{\s*return\s*!m_sharedEventsMap\.isEmpty\(\)\s*&&\s*!hasEvents\(\)\s*;\s*\}"),
 "INHERIT_SCRIPTS_INDEPENDENT":("include/core/map.h",r"isInheritingScripts\(\)\s+const\s+\{\s*return\s*!m_sharedScriptsMap\.isEmpty\(\)\s*;\s*\}"),
 "READ_EVENT_LINK":("src/project.cpp",r'map->setSharedEventsMap\(ParseUtil::jsonToQString\(mapObj\.take\("shared_events_map"\)\)\)'),
 "READ_SCRIPT_LINK":("src/project.cpp",r'map->setSharedScriptsMap\(ParseUtil::jsonToQString\(mapObj\.take\("shared_scripts_map"\)\)\)'),
 "SAVE_EVENT_LINK_CONDITION":("src/project.cpp",r'if\s*\(map->isInheritingEvents\(\)\)\s*\{\s*mapObj\["shared_events_map"\]\s*=\s*map->sharedEventsMap\(\)'),
 "SAVE_SCRIPT_LINK_CONDITION":("src/project.cpp",r'if\s*\(map->isInheritingScripts\(\)\)\s*\{\s*mapObj\["shared_scripts_map"\]\s*=\s*map->sharedScriptsMap\(\)'),
 "LOCAL_TYPED_EVENTS_ONLY_WHEN_NOT_INHERITING":("src/project.cpp",r'if\s*\(!map->isInheritingEvents\(\)\)\s*\{\s*auto buildEventsJson\s*=.*?buildEventsJson\(Event::Group::Object.*?buildEventsJson\(Event::Group::Warp.*?buildEventsJson\(Event::Group::Coord.*?buildEventsJson\(Event::Group::Bg'),
 "SCRIPT_CHANGE_INVALIDATES_WATCHER":("src/core/map.cpp",r'void Map::setSharedScriptsMap\(.*?m_sharedScriptsMap\s*=\s*sharedScriptsMap;\s*invalidateScripts\(\);'),
 "SCRIPT_SOURCE_USES_SHARED_NAME":("src/core/map.cpp",r'!m_sharedScriptsMap\.isEmpty\(\)\s*\?\s*m_sharedScriptsMap\s*:\s*m_name'),
 "LOCAL_EVENT_INHERITANCE_UI_WARNING":("src/mainwindow.cpp",r'Adding any events will separate it from that map\.'),
 "EVENT_GROUPS_LOADED_SEPARATELY":("src/project.cpp",r'Event::groupToJsonKey\(Event::Group::Object\).*?Event::groupToJsonKey\(Event::Group::Warp\).*?Event::groupToJsonKey\(Event::Group::Coord\).*?Event::groupToJsonKey\(Event::Group::Bg\)'),
 "EXTRA_MAP_FIELDS_PRESERVED":("src/project.cpp",r'OrderedJson::append\(&mapObj, map->customAttributes\(\)\)')
}
def blob(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Pinned Porymap SHA mismatch")
 sources={}
 for file,sha in BLOBS.items():
  data=(ROOT/file).read_bytes()
  if blob(data)!=sha:raise RuntimeError("Changed pinned file "+file)
  sources[file]=data.decode("utf-8","surrogateescape")
 evidence=[]
 for name,(file,regex) in PATTERNS.items():
  m=re.search(regex,sources[file],flags=re.S)
  if not m:raise RuntimeError("Missing source semantic contract "+name+" in "+file)
  line=sources[file].count("\n",0,m.start())+1
  endline=sources[file].count("\n",0,m.end())+1
  evidence.append({"contract":name,"source_path":file,"source_git_blob_sha":BLOBS[file],
    "line_start":line,"line_end":endline,"source_match_sha256":hashlib.sha256(
       m.group(0).encode("utf-8","surrogateescape")).hexdigest(),
    "source_code_observed":True,"runtime_confirmed":False})
 OUT.mkdir(parents=True,exist_ok=True)
 result={"source_contracts_passed":len(evidence),"source_commit":PIN,"source_files_verified":len(sources),
  "two_independent_inheritance_links":True,"local_events_change_inheritance_predicate":True,
  "script_label_source_sharing_independent_of_event_sharing":True,
  "unknown_top_level_map_attributes_preserved_on_save":True,
  "source_evidence":evidence,
  "semantic_file_signoffs":0,"phase1_complete":False,
  "limitations":["This is a pinned source branch proof; no actual GUI, JSON round-trip, or arbitrary ROM reverse conversion executed.",
    "Source can contain additional consumer paths beyond the checked load/save control flow.",
    "Importers must preserve unrecognized custom event attributes and shared-map references."]}
 (OUT/"porymap_shared_map_semantics.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"contracts_passed":len(evidence),"source_blobs_verified":len(sources),"phase1_complete":False}))
if __name__=="__main__":main()
