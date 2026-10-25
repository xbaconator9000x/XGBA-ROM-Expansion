#!/usr/bin/env python3
"""Resolve outstanding compiled object references against actual linked ELF symbols.

Does NOT claim a particular hidden archive object provides a symbol. Separates
unresolved *object* names from names that were linked into the final ELF, and
checks whether final-ELF-absent names carry relocation records in the object.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered").resolve()
OUT=Path("firered-variant-evidence")
COMMIT="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
VARIANTS={"original_agbcc":"pokefirered.elf","modern_gcc":"pokefirered_modern.elf"}
COLS=["variant","consumer_object","consumer_source_candidate","consumer_source_blob_sha",
      "undefined_symbol","resolution_class","present_as_final_global",
      "final_elf_address_hex","final_elf_region","relocation_reference_present",
      "relocation_line_samples","linker_binding_verified"]
def readcsv(path):
 with gzip.open(path,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def main():
 revision=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if revision!=COMMIT:raise RuntimeError("Pinned source commit changed")
 index=collections.defaultdict(dict)
 for e in readcsv(OUT/"compiled_all_defined_symbols.csv.gz"):
  if e["visibility_heuristic"]=="global":
   index[e["variant"]][e["name"]]=e
 unknown=[r for r in readcsv(OUT/"compiled_object_symbol_dependencies.csv.gz")
  if r["provider_status"]=="LINKER_ARCHIVE_GENERATED_OR_EXTERNAL_UNRESOLVED"]
 full=json.loads((OUT/"compiled_full_symbol_delta_summary.json").read_text())
 original=json.loads((OUT/"compiled_object_binding_summary.json").read_text())
 if set(full["elf_variants"])!=set(VARIANTS) or set(original["configurations"])!=set(VARIANTS):
  raise RuntimeError("Expected two compiled variants")
 cache={};stats=collections.defaultdict(collections.Counter);unique_missing=collections.defaultdict(set)
 with gzip.open(OUT/"compiled_external_symbol_resolution.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=COLS);w.writeheader()
  for x in unknown:
   variant=x["variant"]
   if variant not in VARIANTS:raise RuntimeError("Unknown variant")
   s=x["undefined_symbol"]
   final=index[variant].get(s)
   if final:
    status="LINKED_FINAL_ELF_GLOBAL_SYMBOL_PRESENT_FROM_OTHER_SOURCE"
    reloc=""
    samples=[]
   else:
    obj_path=ROOT/x["consumer_object"]
    if not obj_path.is_file():raise RuntimeError("Compiled reference object missing: "+str(obj_path))
    if str(obj_path) not in cache:
     cp=subprocess.run(["arm-none-eabi-objdump","-r",str(obj_path)],
         capture_output=True,text=True,timeout=30)
     if cp.returncode:raise RuntimeError("objdump relocation read failed "+str(obj_path))
     cache[str(obj_path)]=cp.stdout.splitlines()
    matches=[l.strip() for l in cache[str(obj_path)]
      if re.search(r"(?<![A-Za-z_0-9])"+re.escape(s)+r"(?![A-Za-z_0-9])",l)]
    samples=matches[:5]
    reloc=str(bool(matches))
    if matches:
     status="FINAL_ELF_ABSENT_WITH_OBJECT_RELOCATION_REVIEW_SECTION_DISCARD"
    else:
     status="FINAL_ELF_ABSENT_NO_RELOCATION_REFERENCE_IN_OBJECT"
    unique_missing[variant].add(s)
   stats[variant][status]+=1
   w.writerow({"variant":variant,"consumer_object":x["consumer_object"],
    "consumer_source_candidate":x["consumer_source_candidate"],
    "consumer_source_blob_sha":x["consumer_source_blob_sha"],
    "undefined_symbol":s,"resolution_class":status,
    "present_as_final_global":bool(final),
    "final_elf_address_hex":final["address_hex"] if final else "",
    "final_elf_region":final["memory_region"] if final else "",
    "relocation_reference_present":reloc,
    "relocation_line_samples":" | ".join(samples),
    "linker_binding_verified":bool(final)})
 result={"pinned_revision":COMMIT,"compiled_variants":{},
  "originally_unmatched_external_or_linker_reference_sites":len(unknown),
  "unique_unlisted_symbols_by_variant":{v:sorted(names) for v,names in unique_missing.items()},
  "compiler_object_to_linker_symbol_reconciliation":"SOURCE_PINNED_COMPILATION_AND_ELF_NAME_BINDING",
  "every_linked_final_symbol_provider_proven":False,
  "whole_source_file_signoffs":0,"phase1_mapping_complete":False,
  "limitations":["A final ELF symbol name and address confirms a linked binding, not which hidden library/archive was selected.",
                 "An undefined object symbol without relocation can legitimately be absent from the linked ELF.",
                 "A relocation in an object not appearing in final ELF requires section/linker-map investigation.",
                 "Only original and modern FireRed builds are covered, not third-party ROM forks."]}
 for v in VARIANTS:
  d=stats[v]
  if sum(d.values())!=original["configurations"][v]["external_linker_archive_reference_sites"]:
   raise RuntimeError("Did not reconcile all unknown references in "+v)
  result["compiled_variants"][v]={"reference_sites_by_class":dict(d),
    "reference_sites_reconciled":sum(d.values()),
    "unique_missing_names":len(unique_missing[v]),
    "elf_sha256":full["elf_variants"][v]["elf_sha256"]}
 (OUT/"compiled_external_symbol_resolution_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in result.items() if k not in ("unique_unlisted_symbols_by_variant","limitations")},indent=2))
if __name__=="__main__":main()
