#!/usr/bin/env python3
"""Complete pinned FireRed classic/modern ELF symbol inventory and ABI drift.

Unlike eleven sampled critical bindings, inspect every defined ELF symbol from
both exact source+compiler builds. Do NOT treat all static/compiler-generated
symbols as a stable public plugin ABI, or address changes as automatically safe.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,re,subprocess
from pathlib import Path

ROOT=Path("upstream/pokefirered")
OUT=Path("firered-variant-evidence")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
ELFS={"original_agbcc":"pokefirered.elf","modern_gcc":"pokefirered_modern.elf"}
CRITICAL={"gScriptCmdTable","gScriptCmdTableEnd","gBattleScriptingCommandsTable",
          "gMonFrontPicTable","gMonBackPicTable","gSongTable","gMPlayTable",
          "gMapGroups","gMapLayouts","gSaveBlock1Ptr","gSaveBlock2Ptr"}
REGIONS=(
 ("EWRAM",0x02000000,0x02040000),
 ("IWRAM",0x03000000,0x03008000),
 ("IO",0x04000000,0x04000400),
 ("PALRAM",0x05000000,0x05000400),
 ("VRAM",0x06000000,0x06018000),
 ("OAM",0x07000000,0x07000400),
 ("CART_ROM0_ROM1_32M",0x08000000,0x0A000000),
 ("CART_ROM2",0x0A000000,0x0C000000),
 ("CART_SRAM",0x0E000000,0x0E010000),
)
NUM=re.compile(r"^[0-9a-fA-F]+$")
def segment(address,typ):
 if typ.upper()=="A":return "ABSOLUTE_NOT_RELOCATABLE"
 for name,lo,hi in REGIONS:
  if lo<=address<hi:return name
 return "OUTSIDE_KNOWN_GBA_REGIONS_OR_DEBUG"
def get_all_symbols(path):
 result=subprocess.check_output(["arm-none-eabi-nm","--defined-only","--numeric-sort","-S",str(path)],text=True)
 entries=[];errors=[]
 for line in result.splitlines():
  part=line.split(maxsplit=3)
  if len(part)==3:
   addr,typ,name=part;size=None
  elif len(part)==4:
   addr,size_raw,typ,name=part
   if not NUM.fullmatch(size_raw):
    errors.append(line[:200]);continue
   size=int(size_raw,16)
  else:
   errors.append(line[:200]);continue
  if not NUM.fullmatch(addr) or len(typ)!=1:
   errors.append(line[:200]);continue
  address=int(addr,16)
  binding=("global" if typ.isupper() else "local")
  entries.append({"name":name,"address":address,"size":size,"type":typ,
                  "binding":binding,"region":segment(address,typ)})
 if errors:
  raise RuntimeError("Unrecognized ARM nm entry format "+str(errors[:5]))
 return entries
def main():
 rev=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if rev!=PIN:raise RuntimeError("FireRed source revision changed")
 OUT.mkdir(exist_ok=True)
 symbol_sets={};variants={};dups={}
 for variant,filename in ELFS.items():
  path=ROOT/filename
  if not path.is_file():raise RuntimeError("Missing compiled ELF: "+str(path))
  syms=get_all_symbols(path)
  if len(syms)<500:raise RuntimeError("Too few defined ELF symbols")
  byname=collections.defaultdict(list)
  for r in syms:
   if r["binding"]=="global":byname[r["name"]].append(r)
  uniques={name:v[0] for name,v in byname.items() if len(v)==1}
  duplicates={name:len(v) for name,v in byname.items() if len(v)>1}
  if not CRITICAL.issubset(uniques):
   raise RuntimeError("Original critical ABI symbols absent or duplicate: "+str(CRITICAL-set(uniques)))
  variants[variant]={"elf_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
    "elf_bytes":path.stat().st_size,
    "all_defined_symbols":len(syms),"global_symbol_names":len(byname),
    "unique_global_symbols":len(uniques),"ambiguous_global_names":len(duplicates),
    "symbols_by_segment":dict(collections.Counter(r["region"] for r in syms)),
    "global_symbols_by_segment":dict(collections.Counter(r["region"] for r in syms if r["binding"]=="global")),
    "symbol_bindings":dict(collections.Counter(r["binding"] for r in syms)),
    "symbol_kinds":dict(collections.Counter(r["type"] for r in syms))}
  symbol_sets[variant]={"all":syms,"uniques":uniques}
  dups[variant]=duplicates
 with gzip.open(OUT/"compiled_all_defined_symbols.csv.gz","wt",encoding="utf-8",newline="") as f:
  fields=["variant","source_commit","elf_sha256","name","address_hex","size_bytes",
          "symbol_type","visibility_heuristic","memory_region"]
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for v,r in symbol_sets.items():
   for s in r["all"]:
    w.writerow({"variant":v,"source_commit":PIN,"elf_sha256":variants[v]["elf_sha256"],
      "name":s["name"],"address_hex":f"0x{s['address']:08X}",
      "size_bytes":s["size"] if s["size"] is not None else "",
      "symbol_type":s["type"],"visibility_heuristic":s["binding"],
      "memory_region":s["region"]})
 original=symbol_sets["original_agbcc"]["uniques"]
 modern=symbol_sets["modern_gcc"]["uniques"]
 common=set(original)&set(modern)
 changes=collections.Counter()
 with gzip.open(OUT/"compiled_global_symbol_semantic_delta.csv.gz","wt",encoding="utf-8",newline="") as f:
  fields=["name","classification","original_address","modern_address",
          "original_size","modern_size","original_type","modern_type",
          "original_region","modern_region","address_changed","size_changed"]
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for name in sorted(set(original)|set(modern)):
   a=original.get(name);b=modern.get(name)
   if a is None:classif="NEW_IN_MODERN"
   elif b is None:classif="ONLY_CLASSIC"
   elif a["region"]!=b["region"]:classif="REGION_CHANGED"
   elif a["address"]!=b["address"] and a["size"]!=b["size"]:classif="LOCATION_AND_SIZE_CHANGED"
   elif a["address"]!=b["address"]:classif="LOCATION_CHANGED"
   elif a["size"]!=b["size"]:classif="SIZE_CHANGED"
   else:classif="LOCATION_AND_SIZE_SAME"
   changes[classif]+=1
   w.writerow({"name":name,"classification":classif,
     "original_address":f"0x{a['address']:08X}" if a else "",
     "modern_address":f"0x{b['address']:08X}" if b else "",
     "original_size":a["size"] if a and a["size"] is not None else "",
     "modern_size":b["size"] if b and b["size"] is not None else "",
     "original_type":a["type"] if a else "","modern_type":b["type"] if b else "",
     "original_region":a["region"] if a else "",
     "modern_region":b["region"] if b else "",
     "address_changed":a is not None and b is not None and a["address"]!=b["address"],
     "size_changed":a is not None and b is not None and a["size"]!=b["size"]})
 checked_previous=json.loads((OUT/"firered_variants_abi_summary.json").read_text())
 if checked_previous["pinned_commit"]!=PIN:
  raise RuntimeError("Previous compiled ABI provenance missing")
 for n in CRITICAL:
  for variant,key in [("original_agbcc","classic_hex"),("modern_gcc","modern_hex")]:
   s=symbol_sets[variant]["uniques"][n]
   prev=next(r for r in checked_previous["symbols"] if r["symbol"]==n)
   if s["address"]!=int(prev[key],16):
    raise RuntimeError("Full compiled symbol census disagrees with previously verified critical ABI: "+n)
 summary={"pinned_revision":PIN,"elf_variants":variants,
  "unique_global_symbols_shared":len(common),
  "global_delta_class_counts":dict(changes),
  "global_symbols_unique_to_classic":len(set(original)-set(modern)),
  "global_symbols_unique_to_modern":len(set(modern)-set(original)),
  "sampled_critical_contracts_reconciled":len(CRITICAL),
  "ambiguous_globals_by_variant":dups,
  "full_symbol_coverage":"ALL_ARM_NM_DEFINED_SYMBOLS_FOR_TWO_COMPILED_BASELINES",
  "plugin_ABI_inferred_for_all_symbols":False,"runtime_execution_tested":False,
  "independent_whole_file_signoffs":0,"phase1_mapping_complete":False,
  "caveats":[
   "All ELF symbols are inventoried; symbol names are not a promise of public stable ABI.",
   "Uppercase nm symbol classification distinguishes binding only approximately; weak symbols can be special.",
   "Size and address changes may be compiler layout churn, not meaningful behavior changes.",
   "Local static symbols are collected but not aligned across translation units without DWARF provenance.",
   "Matching name/size/location does not guarantee identical code or resource semantics.",
   "An unknown ROM, emulator core or compiler requires new cryptographic and ABI preflight."
  ]}
 (OUT/"compiled_full_symbol_delta_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("elf_variants","ambiguous_globals_by_variant","caveats")},indent=2))
if __name__=="__main__":main()
