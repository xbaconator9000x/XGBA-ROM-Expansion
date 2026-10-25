#!/usr/bin/env python3
"""Compare two independent pinned FireRed builds: ROM bytes vs host ELF metadata.

Never infer unchanged runtime code from ELF symbol names alone. The original
cart image must hash identically, page-for-page, before reporting ROM identity.
"""
import argparse,csv,gzip,json
from pathlib import Path
VARIANTS=("original_agbcc","modern_gcc")
def pages(path):
 with gzip.open(path,"rt",newline="",encoding="utf-8") as f:
  return {(r["variant"],int(r["page_index"])):r["page_sha256"] for r in csv.DictReader(f)}
def run(a,b,out):
 pa=json.loads((a/"compiled_runtime_rom_image_hashes.json").read_text())
 pb=json.loads((b/"compiled_runtime_rom_image_hashes.json").read_text())
 if pa["pinned_revision"]!=pb["pinned_revision"]:
  raise RuntimeError("Cannot compare different FireRed source revisions")
 if pa["page_size_bytes"]!=pb["page_size_bytes"]:
  raise RuntimeError("ROM page-size comparison invalid")
 pages_a=pages(a/"compiled_rom_page_hashes.csv.gz")
 pages_b=pages(b/"compiled_rom_page_hashes.csv.gz")
 if set(pages_a)!=set(pages_b):raise RuntimeError("ROM page index sets differ")
 hot_a=a/"compiled_rom_page30_32byte_hashes.csv.gz"
 hot_b=b/"compiled_rom_page30_32byte_hashes.csv.gz"
 hot={}
 if hot_a.exists() and hot_b.exists():
  def hotrows(path):
   with gzip.open(path,"rt",newline="",encoding="utf-8") as f:
    return {(r["variant"],int(r["offset_inside_rom"])):r for r in csv.DictReader(f)}
  fine_a=hotrows(hot_a);fine_b=hotrows(hot_b)
  if set(fine_a)!=set(fine_b):raise RuntimeError("Hot-page 32-byte evidence row sets differ")
  for v in VARIANTS:
   differences=[]
   for (var,offset),r in fine_a.items():
    if var==v and r["chunk_sha256"]!=fine_b[(var,offset)]["chunk_sha256"]:
     differences.append({"rom_offset":hex(offset),"gba_bus_address":r["gba_bus_address"]})
   hot[v]={"available":True,"changed_32_byte_chunks":len(differences),
           "changed_gba_addresses":differences[:200],
           "sample_truncated":len(differences)>200,
           "total_hot_region_chunks":sum(var==v for var,_ in fine_a)}
 else:
  for v in VARIANTS:hot[v]={"available":False}
 variants={}
 for v in VARIANTS:
  aa=pa["variants"][v];bb=pb["variants"][v]
  damaged=[n for (var,n),sha in pages_a.items()
    if var==v and sha!=pages_b[(var,n)]]
  if hot[v]["available"]:
   if (30 in damaged)!=(hot[v]["changed_32_byte_chunks"]>0):
    raise RuntimeError("Coarse 64KiB page 30 and fine 32-byte hashes disagree: "+v)
  if bool(damaged)!=(aa["rom_sha256"]!=bb["rom_sha256"]):
   raise RuntimeError("Page hash disagreement with ROM-level checksum for "+v)
  variants[v]={"hot_region_32byte_diff":hot[v],
   "elf_sha256_identical":aa["elf_sha256"]==bb["elf_sha256"],
   "native_gba_sha256_identical":aa["rom_sha256"]==bb["rom_sha256"],
   "nm_defined_symbol_table_sha256_identical":
      aa["nm_defined_symbol_table_sha256"]==bb["nm_defined_symbol_table_sha256"],
   "native_header_sha256_identical":
      aa["header_first_192_bytes_sha256"]==bb["header_first_192_bytes_sha256"],
   "native_image_bytes_run_a":aa["rom_size_bytes"],
   "native_image_bytes_run_b":bb["rom_size_bytes"],
   "changed_65536_byte_rom_pages":len(damaged),
   "changed_page_indices_sample":damaged[:32],
   "runtime_rom_hash_run_a":aa["rom_sha256"],"runtime_rom_hash_run_b":bb["rom_sha256"],
   "elf_hash_run_a":aa["elf_sha256"],"elf_hash_run_b":bb["elf_sha256"]}
  if aa["rom_sha256"]==bb["rom_sha256"] and aa["elf_sha256"]!=bb["elf_sha256"]:
   variants[v]["interpretation"]="NONROM_ELF_CONTENT_OR_METADATA_DIFFERENCE_OBSERVED"
  elif aa["rom_sha256"]!=bb["rom_sha256"]:
   variants[v]["interpretation"]="EXECUTABLE_ROM_BYTES_CHANGED_REQUIRES_BINARY_DIFF"
  else:
   variants[v]["interpretation"]="ELF_AND_NATIVE_ROM_MATCH"
 result={"pinned_commit":pa["pinned_revision"],
  "toolchain_metadata_identical":pa["toolchain"]==pb["toolchain"],
  "variants":variants,
  "allow_rom_hash_plugin_identity_when_rom_byte_identical":
    all(v["native_gba_sha256_identical"] and
     v["nm_defined_symbol_table_sha256_identical"] for v in variants.values()),
  "source_level_signoffs":0,"phase1_mapping_complete":False,
  "caveats":["Identical ROM bytes across two builds do not guarantee deterministic outputs for every future environment.",
    "Changed ELF bytes with same ROM hash shows a difference outside the native cartridge image, not the exact cause.",
    "Exact ROM hash can support a pinned adapter preflight, not an arbitrary fork compatibility claim."]}
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in result.items() if k!="caveats"},indent=2))
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--run-a",type=Path,required=True)
 p.add_argument("--run-b",type=Path,required=True)
 p.add_argument("--out",type=Path,default=Path("runtime-reproducibility-result.json"))
 z=p.parse_args()
 run(z.run_a,z.run_b,z.out)
