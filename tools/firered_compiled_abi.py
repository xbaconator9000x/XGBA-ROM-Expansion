#!/usr/bin/env python3
"""Pinned FireRed ARM compiled ELF/linker constraints (no game ROM distribution).

Reads the actual generated ELF and linker map, validates section placement,
finds selected extension-relevant symbols, verifies range and provenance.
Does NOT claim any XGBA extension has been built or executed.
"""
import collections,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path("upstream/pokefirered")
OUT=Path("firered-compiler-evidence")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
TARGETS=["gScriptCmdTable","gScriptCmdTableEnd","gBattleScriptingCommandsTable",
 "gSongTable","gMonFrontPicTable","gMonBackPicTable","gSaveBlock1Ptr",
 "gSaveBlock2Ptr","gMapGroups","gMapLayouts","gBattleMoves","gItems"]
ROM_LOW=0x08000000;ROM_LIMIT=0x0A000000
def cmd(*args):
 return subprocess.check_output(args,text=True,stderr=subprocess.STDOUT)
def main():
 OUT.mkdir(exist_ok=True)
 if cmd("git","-C",str(ROOT),"rev-parse","HEAD").strip()!=PIN:
  raise RuntimeError("Unpinned ROM")
 elfs=list(ROOT.glob("*.elf"))
 if len(elfs)!=1:raise RuntimeError("Expected a single built FireRed ELF; found "+str(elfs))
 elf=elfs[0]
 # objcopy of GBA ELF output is deliberately not uploaded.
 header=cmd("arm-none-eabi-readelf","-SW",str(elf))
 sym=cmd("arm-none-eabi-nm","-n","-S",str(elf))
 sha256=hashlib.sha256(elf.read_bytes()).hexdigest()
 sections=[]
 for line in header.splitlines():
  m=re.search(r"\[\s*(\d+)\]\s+(\S+)\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+",line)
  if not m:continue
  no,name,typ,addr,offset,size=m.groups()
  addr=int(addr,16);size=int(size,16)
  sections.append({"name":name,"type":typ,"address":addr,"bytes":size,
                   "inside_gba_rom":ROM_LOW<=addr<ROM_LIMIT and addr+size<=ROM_LIMIT})
 syms=collections.defaultdict(list)
 for line in sym.splitlines():
  m=re.match(r"^([0-9a-fA-F]+)\s+(?:([0-9a-fA-F]+)\s+)?([a-zA-Z])\s+(\S+)$",line)
  if not m:continue
  a,size,typ,name=m.groups()
  if name not in TARGETS:continue
  addr=int(a,16)
  syms[name].append({"address":hex(addr),"size":int(size,16) if size else None,"symbol_type":typ,
                      "inside_rom":ROM_LOW<=addr<ROM_LIMIT})
 rom_sections=[s for s in sections if s["inside_gba_rom"] and s["bytes"]]
 invalid=[s for s in sections if ROM_LOW<=s["address"]<ROM_LIMIT and not s["inside_gba_rom"]]
 if invalid:raise RuntimeError("ELF section overlaps end of native 32MiB GBA ROM region")
 if not rom_sections:raise RuntimeError("No native ROM sections found")
 if not any(x.get("inside_rom") for v in syms.values() for x in v):
  raise RuntimeError("No named ROM symbol addresses")
 def sole(name):
  candidates=syms.get(name,[])
  if len(candidates)!=1:raise RuntimeError("Missing or ambiguous linker symbol: "+name)
  return candidates[0]
 def address(name):return int(sole(name)["address"],16)
 dispatch_span=address("gScriptCmdTableEnd")-address("gScriptCmdTable")
 battle_bytes=sole("gBattleScriptingCommandsTable")["size"]
 front_bytes=sole("gMonFrontPicTable")["size"]
 back_bytes=sole("gMonBackPicTable")["size"]
 invariants={
  "field_script_table_213_pointers":dispatch_span==213*4,
  "battle_script_table_248_pointers":battle_bytes==248*4,
  "front_sprite_table_440_entries":front_bytes==440*8,
  "back_sprite_table_440_entries":back_bytes==440*8,
  "save_block1_pointer_in_iwram":0x03000000<=address("gSaveBlock1Ptr")<0x03008000,
  "save_block2_pointer_in_iwram":0x03000000<=address("gSaveBlock2Ptr")<0x03008000,
  "all_critical_tables_in_rom":all(sole(n)["inside_rom"] for n in [
    "gScriptCmdTable","gScriptCmdTableEnd","gBattleScriptingCommandsTable",
    "gMonFrontPicTable","gMonBackPicTable","gSongTable","gMapGroups","gMapLayouts"])
 }
 if not all(invariants.values()):raise RuntimeError("Source-to-compiled ROM pointer ABI failed: "+str(invariants))
 abi_facts={
  "field_script_table_bytes":dispatch_span,
  "battle_script_table_bytes":battle_bytes,
  "front_sprite_table_bytes":front_bytes,
  "back_sprite_table_bytes":back_bytes,
  "compiled_invariants":invariants,
  "compiled_invariants_passed":sum(invariants.values()),
  "compiled_invariants_total":len(invariants)
 }
 build_map=list(ROOT.glob("*.map"))
 result={"pinned_fire_red_commit":PIN,"elf_basename":elf.name,
  "elf_sha256":sha256,"linker_map_names":[m.name for m in build_map],
  "rom_link_window":[hex(ROM_LOW),hex(ROM_LIMIT)],
  "rom_section_count":len(rom_sections),
  "rom_section_total_bytes":sum(x["bytes"] for x in rom_sections),
  "rom_section_high_water_mark":hex(max(x["address"]+x["bytes"] for x in rom_sections)),
  "sections":sections,"selected_symbol_addresses":dict(syms),
  "symbols_found_count":len(syms),"symbols_requested":TARGETS,
  "compiled_dispatch_and_pointer_abi":abi_facts,
  "compiled_baseline_verified":True,
  "xgba_external_memory_implemented":False,
  "phase1_mapping_complete":False,
  "limitations":["Build variant and user-specific flags must be compared independently.",
    "Linker symbol existence does not prove runtime semantics or pointer lifetime.",
    "Generated ROM image is intentionally excluded from upload.",
    "All 14,834 files still require source-anchored dispositions for mapping gate."]}
 (OUT/"firered_compiled_abi_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in result.items() if k not in ("sections","selected_symbol_addresses","limitations")},indent=2))
if __name__=="__main__":main()
