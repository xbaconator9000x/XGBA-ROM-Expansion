#!/usr/bin/env python3
"""Inspect a real mGBA CMake compilation database and linked symbols.

This captures actual translation units, defines, include paths, source hashes,
linker symbol names and feature flags from a pinned host build. It is NOT an
emulation/runtime test and does not resolve every source-to-function call site.
"""
import collections,hashlib,json,os,re,shlex,subprocess,sys
from pathlib import Path
ROOT=Path("upstream/mgba")
BUILD=Path("build-mgba")
OUT=Path("compiler-evidence")
PIN="fd9dc5c2cbf234365068855851107e762fc6211b"
ABI=["GBALoadROM","GBALoad8","GBALoad16","GBALoad32","GBADMAUpdate",
     "GBASerialize","GBADeserialize","GBAMatrixSerialize","GBAMatrixDeserialize",
     "ARMSetActiveRegion","GBAMemoryInit","GBAMemoryDeinit"]
def gitsha(b):return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def main():
 OUT.mkdir(exist_ok=True)
 commit=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if commit!=PIN:raise RuntimeError("mGBA pinned commit mismatch")
 comp=json.loads((BUILD/"compile_commands.json").read_text())
 entries=[];errors=[];bylanguage=collections.Counter();byfeature=collections.Counter()
 for c in comp:
  f=Path(c["file"])
  if not f.is_absolute():f=Path(c["directory"])/f
  f=f.resolve()
  cmd=c.get("arguments") or shlex.split(c.get("command",""))
  defines=[x for x in cmd if x.startswith("-D")]
  includes=[x for x in cmd if x.startswith(("-I","-isystem"))]
  bylanguage[f.suffix]+=1
  for d in defines:
   if any(v in d for v in ("ENABLE_","USE_","BUILD_","GBA_","MGBA_")):
    byfeature[d]+=1
  if f.is_relative_to(ROOT.resolve()):
   path=f.relative_to(ROOT.resolve()).as_posix()
   obj=subprocess.check_output(["git","-C",str(ROOT),"ls-files","-s","--",path],text=True).strip()
   if not obj:errors.append({"source":path,"reason":"Compiled file not Git tracked"})
   else:
    sha=obj.split()[1]
    data=f.read_bytes()
    if gitsha(data)!=sha:errors.append({"source":path,"reason":"Compiler source differs from pinned Git blob"})
  else:path="GENERATED_OR_EXTERNAL/"+f.name
  entries.append({"source":path,"language":f.suffix,"compiler":cmd[0] if cmd else None,
     "define_tokens":defines,"include_paths":includes,"command_sha256":hashlib.sha256("\0".join(cmd).encode()).hexdigest()})
 if len(entries)<30:raise RuntimeError(f"Unexpectedly few translation units: {len(entries)}")
 lib_candidates=list(BUILD.rglob("*.a"))+list(BUILD.rglob("*.so"))
 nm_cmd=["nm","-A","--defined-only"]
 available=collections.defaultdict(list)
 for lib in lib_candidates:
  try:result=subprocess.run(nm_cmd+[str(lib)],capture_output=True,text=True,timeout=45)
  except (OSError,subprocess.TimeoutExpired):continue
  if result.returncode!=0:continue
  for line in result.stdout.splitlines():
   parts=line.rsplit(maxsplit=2)
   if len(parts)<3:continue
   name=parts[-1]
   if name in ABI and len(available[name])<20:
    available[name].append(line[:350])
 summary={"repository":"mgba-emu/mgba","commit":PIN,
    "compilation_units":len(entries),"languages":dict(bylanguage),
    "pinned_source_compile_mismatches":errors[:70],
    "target_symbols_found":{name:available.get(name,[]) for name in ABI},
    "feature_token_counts":dict(byfeature),
    "libraries_inspected":len(lib_candidates),
    "build_compilation_and_symbol_analysis":len(lib_candidates)>0,
    "runtime_execution_tested":False,
    "semantic_mapping_complete":False,
    "limitations":["mGBA build-only proof; no BIOS or GBA test ROM executed.",
     "Feature defines vary by generated build configuration.",
     "GNU nm cannot prove flow edges without link-time relocation/disassembly analysis.",
     "A host mGBA build does not validate a patched XGBA emulator."]}
 (OUT/"compiler_binding_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 with (OUT/"translation_unit_features.jsonl").open("w") as h:
  for e in entries:h.write(json.dumps(e,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("feature_token_counts","target_symbols_found")},indent=2))
 if errors:raise RuntimeError("Failed pinned compile-source provenance checks")
 if not lib_candidates:raise RuntimeError("No linked mGBA libraries produced")
if __name__=="__main__":main()
