#!/usr/bin/env python3
"""Compiler-backed, pinned Porymap Qt/C++ model and map-editing ABI inventory.

Uses actual qmake/g++ compilation database intercepted by bear. Reports source
and macro identity, compiled translation units and selected Qt symbols. This
does not prove editor runtime roundtrip or every file's semantic disposition.
"""
import collections,hashlib,json,os,re,shlex,subprocess
from pathlib import Path
ROOT=Path("upstream/porymap").resolve();OUT=Path("porymap-compiler-evidence")
PIN="26b919d7ff4b54152de010abd5bf344af2ebe116"
REQUIRED_NAMES=["Project::loadMap","Project::loadMapData","Project::loadLayout",
                "Layout::setMetatileId","Layout::renderCollision",
                "Project::saveMap"]
def sha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def main():
 OUT.mkdir(exist_ok=True)
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Unpinned Porymap")
 command_file=ROOT/"compile_commands.json"
 if not command_file.is_file():raise RuntimeError("Missing intercepted qmake compilation commands")
 comp=json.loads(command_file.read_text())
 if len(comp)<25:raise RuntimeError("Too few Porymap C++ translation units")
 seen=set();errors=[];definitions=collections.Counter();language=collections.Counter();compiler_commands=[]
 for row in comp:
  file=Path(row["file"])
  cwd=Path(row["directory"])
  if not file.is_absolute():file=cwd/file
  file=file.resolve()
  if not file.is_relative_to(ROOT):continue
  path=file.relative_to(ROOT).as_posix()
  if path in seen:continue
  seen.add(path)
  obj=subprocess.check_output(["git","-C",str(ROOT),"ls-files","-s","--",path],text=True).strip()
  if not obj:
   errors.append({"path":path,"issue":"COMPILED_SOURCE_NOT_TRACKED"})
   continue
  expected=obj.split()[1];data=file.read_bytes()
  if sha(data)!=expected:
   source=subprocess.check_output(["git","-C",str(ROOT),"cat-file","blob",expected])
   if sha(source)!=expected:errors.append({"path":path,"issue":"SOURCE_CHANGED_FROM_PINNED_GIT"})
  args=row.get("arguments") or shlex.split(row.get("command",""))
  language[file.suffix]+=1
  for token in args:
   if token.startswith("-D"):definitions[token[:180]]+=1
  compiler_commands.append({"path":path,"git_blob_sha":expected,
    "command_hash_sha256":hashlib.sha256("\0".join(args).encode()).hexdigest(),
    "defines":[t for t in args if t.startswith("-D")],
    "includes":[t for t in args if t.startswith("-I")]})
 exe=ROOT/"porymap"
 if not exe.is_file():raise RuntimeError("Expected built Porymap ELF executable")
 nm=subprocess.run(["nm","-C","--defined-only",str(exe)],capture_output=True,text=True)
 if nm.returncode:raise RuntimeError("Porymap nm failed: "+nm.stderr[-1000:])
 important={}
 for symbol in REQUIRED_NAMES:
  observed=[line[:300] for line in nm.stdout.splitlines() if symbol+"(" in line]
  important[symbol]=observed[:12]
 if not any(important.values()):raise RuntimeError("Compiled map editor symbol table empty")
 if errors:raise RuntimeError("Unverifiable pinned Porymap source units: "+str(errors[:8]))
 (OUT/"translation_unit_abi_inventory.jsonl").write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in compiler_commands))
 report={"pinned_porymap_commit":PIN,"compiled_cpp_translation_units":len(seen),
  "language_units":dict(language),"pinned_source_errors":errors,
  "qmake_defines":dict(definitions),"binary_sha256":hashlib.sha256(exe.read_bytes()).hexdigest(),
  "named_map_editor_symbol_sites":important,
  "porymap_qt_source_compiled":True,"editor_roundtrip_tested":False,
  "independent_file_semantic_signoffs":0,"phase1_mapping_complete":False,
  "limitations":["Only selected Qt build flags and host environment proven.",
    "Qt metaobject compilation and runtime object ownership need independent analysis.",
    "Host app compilation is not an arbitrary-ROM import or plugin compatibility test."]}
 (OUT/"porymap_compiled_semantics.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k not in ("named_map_editor_symbol_sites","qmake_defines","limitations")},indent=2))
if __name__=="__main__":main()
