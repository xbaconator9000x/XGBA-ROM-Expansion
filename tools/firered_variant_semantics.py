#!/usr/bin/env python3
"""Compare compiled original FireRed versus modern GCC ARM/Thumb ABI.

This is symbol/linker evidence for two original pinned build configurations,
not a proof that an XGBA patch can run on either or that other forks match.
"""
from __future__ import annotations
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered")
OUT=Path("firered-variant-evidence")
COMMIT="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
SYMBOLS=["gScriptCmdTable","gScriptCmdTableEnd","gBattleScriptingCommandsTable",
         "gMonFrontPicTable","gMonBackPicTable","gSongTable","gMPlayTable",
         "gMapGroups","gMapLayouts","gSaveBlock1Ptr","gSaveBlock2Ptr"]
ROM_START=0x08000000;ROM_END=0x0A000000
def read_symbols(file):
 data=subprocess.check_output(["arm-none-eabi-nm","-n","-S",str(file)],text=True)
 found={}
 for line in data.splitlines():
  m=re.match(r"^([0-9a-fA-F]+)\s+(?:([0-9a-fA-F]+)\s+)?([a-zA-Z])\s+(\S+)$",line)
  if not m:continue
  address,size,kind,name=m.groups()
  if name in SYMBOLS:
   if name in found:raise RuntimeError("Multiple global symbols "+name+" in "+str(file))
   found[name]={"address":int(address,16),"bytes":int(size,16) if size else None,
                "type":kind}
 absent=set(SYMBOLS)-set(found)
 if absent:raise RuntimeError("Symbol missing from compiled build "+str(file)+": "+str(sorted(absent)))
 return found
def check(elf,s):
 rom=["gScriptCmdTable","gScriptCmdTableEnd","gBattleScriptingCommandsTable",
     "gMonFrontPicTable","gMonBackPicTable","gSongTable","gMPlayTable","gMapGroups","gMapLayouts"]
 facts={
 "field_opcode_table_213x4":s["gScriptCmdTableEnd"]["address"]-s["gScriptCmdTable"]["address"]==213*4,
 "battle_opcode_table_248x4":s["gBattleScriptingCommandsTable"]["bytes"]==248*4,
 "front_sprite_table_440x8":s["gMonFrontPicTable"]["bytes"]==440*8,
 "back_sprite_table_440x8":s["gMonBackPicTable"]["bytes"]==440*8,
 "all_ROM_table_addresses_native_32MiB":all(ROM_START<=s[x]["address"]<ROM_END for x in rom),
 "both_save_pointers_inside_IWRAM":all(0x03000000<=s[x]["address"]<0x03008000 for x in ("gSaveBlock1Ptr","gSaveBlock2Ptr"))}
 if not all(facts.values()):raise RuntimeError("Compiled variant ABI differs from expected original tables: "+str(facts))
 return facts
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=COMMIT:
  raise RuntimeError("Wrong pinned FireRed source")
 variants={}
 for variant,name in [("original_agbcc","pokefirered.elf"),("modern_gcc","pokefirered_modern.elf")]:
  elf=ROOT/name
  if not elf.is_file():raise RuntimeError("Built ELF absent: "+str(elf))
  symbols=read_symbols(elf)
  facts=check(elf,symbols)
  variants[variant]={"elf_file":name,"elf_sha256":hashlib.sha256(elf.read_bytes()).hexdigest(),
   "elf_bytes":elf.stat().st_size,"symbols":symbols,"compiled_abi_checks":facts}
 old=variants["original_agbcc"]["symbols"];new=variants["modern_gcc"]["symbols"]
 diffs=[]
 for name in SYMBOLS:
  o=old[name];m=new[name]
  diffs.append({"symbol":name,"classic_hex":hex(o["address"]),
    "modern_hex":hex(m["address"]),"offset_difference":m["address"]-o["address"],
    "size_classic":o["bytes"],"size_modern":m["bytes"],
    "address_changed":o["address"]!=m["address"],
    "size_changed":o["bytes"]!=m["bytes"]})
 summary={"pinned_commit":COMMIT,"compared_variants":list(variants),
 "source_compiler_configuration":{"original_agbcc":"MODERN=0","modern_gcc":"MODERN=1"},
 "symbol_count_compared":len(SYMBOLS),"compiled_ABI_checks_per_variant":6,
 "compiled_ABI_check_count_passed":sum(sum(v["compiled_abi_checks"].values()) for v in variants.values()),
 "symbol_addresses_changed":sum(d["address_changed"] for d in diffs),
 "symbol_sizes_changed":sum(d["size_changed"] for d in diffs),
 "symbols":diffs,"variants":variants,
 "design_requirements":["Never hardcode vanilla ARM linker addresses across compiler variants.",
  "Preserve opcode widths and sprite table entries even if compiled addresses move.",
  "Versioned XGBA plugin adapters should resolve source-to-binary symbols from a pinned build manifest.",
  "Native GBA ROM pointer space remains 32 MiB; no expanded emulator package is tested here."],
 "runtime_emulation_tested":False,"whole_source_file_semantic_signoffs":0,
 "phase1_mapping_complete":False}
 OUT.mkdir(exist_ok=True)
 (OUT/"firered_variants_abi_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("symbols","variants","design_requirements")},indent=2))
 # Resolve real per-build source preprocessor branches under both pinned ELFs;
 # this supplements symbol ABI and never represents emulator runtime proof.
 subprocess.run(["python3","tools/firered_map_view_variant_semantics.py"],check=True)

if __name__=="__main__":main()
