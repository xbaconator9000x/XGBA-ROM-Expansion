#!/usr/bin/env python3
"""Proposed exact-ROM-and-source-symbol adapter preflight (Phase 1 only).

Avoid binding runtime compatibility to reproducibly irrelevant ELF metadata.
No XGBA runtime/patcher exists; this defines a candidate format and tests
its fail-closed behavior on two original FireRed compiled baselines.
"""
from __future__ import annotations
import copy,hashlib,json,re
from pathlib import Path
OUT=Path("firered-variant-evidence")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
SCHEMA="XGBA/Phase1/RuntimeROMSourceSymbols/1"
CRITICAL=("gScriptCmdTable","gScriptCmdTableEnd","gBattleScriptingCommandsTable",
    "gMonFrontPicTable","gMonBackPicTable","gSongTable","gMPlayTable",
    "gMapGroups","gMapLayouts","gSaveBlock1Ptr","gSaveBlock2Ptr")
SHA256=re.compile(r"^[0-9a-f]{64}$")
def stable(d):
 return hashlib.sha256(json.dumps(d,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
def preflight(candidate,reference):
 if not isinstance(candidate,dict):return False,"candidate is not an object"
 if candidate.get("schema")!=SCHEMA:return False,"schema mismatch"
 for k in ("source_revision","variant","rom_sha256","compiled_symbol_table_sha256"):
  if candidate.get(k)!=reference.get(k):return False,"mismatch: "+k
 for k in ("rom_sha256","compiled_symbol_table_sha256"):
  if not SHA256.fullmatch(str(candidate.get(k,""))):return False,"invalid SHA: "+k
 if candidate.get("bindings")!=reference["bindings"]:return False,"critical symbol bindings changed"
 if set(candidate["bindings"])!=set(CRITICAL):return False,"critical symbol coverage changed"
 core={k:candidate[k] for k in ("schema","source_revision","variant","rom_sha256",
                                 "compiled_symbol_table_sha256","bindings")}
 if candidate.get("fingerprint")!=stable(core):return False,"fingerprint malformed or stale"
 # Deliberately do not compare optional host ELF SHA: only cartridge runtime
 # bytes and source-linked symbol mapping are execution-visible in this design.
 return True,"exact ROM and source-symbol identity accepted"
def main():
 runtime=json.loads((OUT/"compiled_runtime_rom_image_hashes.json").read_text())
 old=json.loads((OUT/"firered_variants_abi_summary.json").read_text())
 if runtime["pinned_revision"]!=PIN or old["pinned_commit"]!=PIN:
  raise RuntimeError("Pinned source mismatch")
 if old["compiled_ABI_check_count_passed"]!=12:
  raise RuntimeError("Original dual compiler ABI checks failed")
 supported={};tests=[]
 for variant in ("original_agbcc","modern_gcc"):
  r=runtime["variants"][variant];older=old["variants"][variant]
  if r["elf_sha256"]!=older["elf_sha256"]:raise RuntimeError("ELF cross-evidence mismatch")
  if r["gba_header_fixed_value_0xb2"]!="0x96":raise RuntimeError("Invalid native GBA header")
  if r["rom_size_bytes"]>32*1024*1024 or r["rom_size_bytes"]<1024*1024:
   raise RuntimeError("Unrealistic original ROM size")
  bindings={name:{"address_hex":hex(older["symbols"][name]["address"]),
    "symbol_type":older["symbols"][name]["type"],
    "size_bytes":older["symbols"][name]["bytes"]}
    for name in CRITICAL}
  base={"schema":SCHEMA,"source_revision":PIN,"variant":variant,
    "rom_sha256":r["rom_sha256"],
    "compiled_symbol_table_sha256":r["nm_defined_symbol_table_sha256"],
    "bindings":bindings}
  entry=copy.deepcopy(base)
  entry["fingerprint"]=stable(base)
  entry["host_build_provenance"]={
     "elf_sha256":r["elf_sha256"],
     "gba_header_first_192_sha256":r["header_first_192_bytes_sha256"],
     "native_rom_bytes":r["rom_size_bytes"]}
  ok,reason=preflight(entry,entry)
  if not ok:raise RuntimeError("Correct exact ROM binding rejected "+reason)
  # Positive deliberate metadata drift: changed host ELF bytes alone are NOT
  # evidence of modified ROM execution bytes.
  metadata=copy.deepcopy(entry)
  metadata["host_build_provenance"]["elf_sha256"]="f"*64
  ok,reason=preflight(metadata,entry)
  if not ok:raise RuntimeError("ELF-only metadata drift wrongly rejected "+reason)
  tests.append({"variant":variant,"case":"ELF_METADATA_ONLY_CHANGED","accepted":True})
  negative=[
   ("ROM_BYTES_CHANGED",lambda d:d.update(rom_sha256="0"*64)),
   ("SYMBOL_TABLE_CHANGED",lambda d:d.update(compiled_symbol_table_sha256="0"*64)),
   ("SOURCE_CHANGED",lambda d:d.update(source_revision="0"*40)),
   ("BUILD_VARIANT_CHANGED",lambda d:d.update(variant="unsupported")),
   ("CRITICAL_SYMBOL_ADDRESS_CHANGED",lambda d:d["bindings"]["gScriptCmdTable"].update(address_hex="0x09000000")),
   ("CRITICAL_SYMBOL_SIZE_CHANGED",lambda d:d["bindings"]["gBattleScriptingCommandsTable"].update(size_bytes=4)),
   ("CRITICAL_SYMBOL_REMOVED",lambda d:d["bindings"].pop("gMapGroups")),
   ("FINGERPRINT_CHANGED",lambda d:d.update(fingerprint="0"*64)),
   ("UNKNOWN_SYMBOL_ADDED",lambda d:d["bindings"].update(nonexistent={}))
  ]
  for label,fn in negative:
   bad=copy.deepcopy(entry);fn(bad)
   ok,why=preflight(bad,entry)
   tests.append({"variant":variant,"case":label,"rejected":not ok,"reason":why})
   if ok:raise RuntimeError("Unsafe candidate accepted: "+label)
  supported[variant]=entry
 if supported["original_agbcc"]["fingerprint"]==supported["modern_gcc"]["fingerprint"]:
  raise RuntimeError("Compiler variants collided")
 report={"schema":SCHEMA,"pinned_commit":PIN,
  "supported_exact_runtime_variants":supported,
  "negative_compatibility_tests_passed":sum(t.get("rejected",False) for t in tests),
  "elf_metadata_only_drift_positives_passed":sum(t.get("accepted",False) for t in tests),
  "test_evidence":tests,
  "interpretation":"CONSERVATIVE_EXACT_SOURCE_ROM_AND_SYMBOL_BINDING_PREFLIGHT_PROPOSAL",
  "is_general_rom_patch_compatibility_detector":False,
  "runtime_execution_verified":False,
  "independent_semantic_dispositions":0,
  "phase1_mapping_complete":False,
  "limitations":[
   "ELF metadata alone is excluded from the runtime preflight, but may be required for build reproducibility audits.",
   "A hashed matching ROM is necessary for this exact binary adapter; it does not authorize arbitrary forks.",
   "This source-side proposal is not incorporated in an implemented XGBA loader or emulator.",
   "No generated code or external package has been executed under a patched emulator."
  ]}
 OUT.mkdir(exist_ok=True)
 (OUT/"runtime_rom_symbol_preflight_v1.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"supported_exact_variants":len(supported),
    "negative_preflights_rejected":report["negative_compatibility_tests_passed"],
    "metadata_only_drift_accepted":report["elf_metadata_only_drift_positives_passed"],
    "whole_file_semantic_signoffs":0},indent=2))
if __name__=="__main__":main()
