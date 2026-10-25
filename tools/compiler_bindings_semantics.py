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
    "native_boundary_probe_is_separate_post_summary_step":True,
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
 # Run the separately versioned native boundary probe only in the dedicated
 # pinned mGBA compiled-semantics CI workflow. It uses synthetic cartridge
 # bytes and leaves the emulator source tree untouched. Keep logs even on error.
 if os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_WORKFLOW") == "Phase 1 compiled mGBA source semantics":
  runner=Path("tests/run_pinned_mgba_boundary.sh")
  if not runner.is_file():raise RuntimeError("Pinned native Matrix boundary probe script absent")
  log=OUT/"mgba-native-boundary-invocation.log"
  with log.open("w") as h:
   proc=subprocess.run(["bash",str(runner)],stdout=h,stderr=subprocess.STDOUT,check=False)
  for name in ("mgba-boundary-configure.log","mgba-boundary-build.log","mgba-boundary-runtime.log",
               "mgba-boundary-backtrace.log","mgba-boundary-log-sha256.txt","mgba_native_test_revision.txt"):
   candidate=Path("audit-output")/name
   if candidate.is_file(): (OUT/name).write_bytes(candidate.read_bytes())
  recorded=OUT/"mgba-boundary-runtime.log"
  if recorded.is_file():
   runtime_text=recorded.read_text(errors="replace")
   outcome={"source_revision":PIN,
     "run_kind":"NATIVE_MGBA_SYNTHETIC_CARTRIDGE_ONLY",
     "positive_checks_passed":len(re.findall(r"^PASS ",runtime_text,re.M)),
     "positive_checks_failed":len(re.findall(r"^FAIL ",runtime_text,re.M)),
     "native_gap_observations":re.findall(r"^OBSERVATION (.+)$",runtime_text,re.M),
     "native_probe_exit_code":proc.returncode,
     "independent_semantic_reviews_approved":0,
     "external_XGBA_banking_implemented":False,
     "phase1_mapping_complete":False}
   (OUT/"mgba-native-boundary-result.json").write_text(json.dumps(outcome,indent=2,sort_keys=True)+"\n")
   print("Native mGBA fixture check summary:",outcome["positive_checks_passed"],
         "passed,",outcome["positive_checks_failed"],"failed")
  print("Pinned native Matrix boundary probe:", "PASS" if proc.returncode==0 else "FAIL", "log:", log)
  if proc.returncode:
   print("Boundary probe error tail:",log.read_text(errors="replace")[-7500:])
   backtrace=OUT/"mgba-boundary-backtrace.log"
   if backtrace.exists(): print("Native debugger backtrace:",backtrace.read_text(errors="replace")[-5500:])
   raise RuntimeError(f"Native Matrix probe failed, see {log}")

if __name__=="__main__":main()
