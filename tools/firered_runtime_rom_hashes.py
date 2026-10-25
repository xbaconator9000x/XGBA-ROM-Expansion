#!/usr/bin/env python3
"""Hash actual pinned compiled .gba runtime images independently from host ELF.

An ELF may contain debugging/build metadata that is not part of a GBA cartridge.
The future XGBA adapter must not infer runtime byte identity from source revision
or an ELF hash alone. This verifies the exact original/modern cartridge outputs
without publishing copyrighted ROM bytes.
"""
import csv,gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered")
OUT=Path("firered-variant-evidence")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
NAMES={"original_agbcc":("pokefirered.elf","pokefirered.gba"),
       "modern_gcc":("pokefirered_modern.elf","pokefirered_modern.gba")}
PAGE=0x10000
def sha(d):return hashlib.sha256(d).hexdigest()
def version(name):
 return subprocess.check_output([name,"--version"],text=True).splitlines()[0]
def symbols_hash(variant):
 h=hashlib.sha256();count=0
 with gzip.open(OUT/"compiled_all_defined_symbols.csv.gz","rt",newline="") as f:
  for r in csv.DictReader(f):
   if r["variant"]!=variant:continue
   fields=("name","address_hex","size_bytes","symbol_type","visibility_heuristic","memory_region")
   h.update(json.dumps([r[k] for k in fields],separators=(",",":"),ensure_ascii=True).encode()+b"\n")
   count+=1
 return h.hexdigest(),count
def main():
 commit=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if commit!=PIN:raise RuntimeError("Changed pinned FireRed revision")
 old=json.loads((OUT/"compiled_full_symbol_delta_summary.json").read_text())
 if old["pinned_revision"]!=PIN:raise RuntimeError("ELF census provenance mismatch")
 report={"pinned_revision":PIN,"page_size_bytes":PAGE,
         "toolchain":{"arm_none_eabi_objcopy":version("arm-none-eabi-objcopy"),
          "arm_none_eabi_ld":version("arm-none-eabi-ld"),
          "arm_none_eabi_gcc":version("arm-none-eabi-gcc")},
         "variants":{},"runtime_image_execution_tested":False,
         "independent_source_semantic_signoffs":0,"phase1_mapping_complete":False,
         "caveats":["The hashed GBA output is the unmodified pinned build, not an XGBA implementation.",
          "Byte-identical ROMs are necessary, not sufficient, for behavior identity across emulators.",
          "Different ELF SHA values may originate in non-ROM bytes; this test does not locate the cause in ELF sections.",
          "Page hashes enable cross-run comparison without sharing proprietary game images."]}
 with gzip.open(OUT/"compiled_rom_page_hashes.csv.gz","wt",encoding="utf-8",newline="") as out:
  w=csv.writer(out);w.writerow(["variant","page_index","byte_offset","byte_count","page_sha256"])
  for variant,(elfname,romname) in NAMES.items():
   elf=ROOT/elfname;rom=ROOT/romname
   if not elf.is_file() or not rom.is_file():raise RuntimeError("Missing compiled ELF/ROM: "+romname)
   raw=rom.read_bytes()
   if len(raw)<1024*1024 or len(raw)>32*1024*1024 or len(raw)%PAGE:
    raise RuntimeError("Unexpected original GBA output length "+str(len(raw)))
   eh=sha(elf.read_bytes())
   if eh!=old["elf_variants"][variant]["elf_sha256"]:
    raise RuntimeError("Compiler ELF SHA disagrees with pinned symbol census")
   symhash,count=symbols_hash(variant)
   if count!=old["elf_variants"][variant]["all_defined_symbols"]:
    raise RuntimeError("Full symbol hash count mismatch")
   for offset in range(0,len(raw),PAGE):
    part=raw[offset:offset+PAGE]
    w.writerow([variant,offset//PAGE,offset,len(part),sha(part)])
   header=raw[:0xC0]
   if raw[0xB2]!=0x96:raise RuntimeError("GBA fixed header value invalid for "+variant)
   record={"elf_sha256":eh,"rom_sha256":sha(raw),"rom_size_bytes":len(raw),
      "rom_pages_sha256":sha(b"".join(bytes.fromhex(sha(raw[x:x+PAGE])) for x in range(0,len(raw),PAGE))),
      "page_count":len(raw)//PAGE,
      "header_first_192_bytes_sha256":sha(header),
      "gba_header_fixed_value_0xb2":hex(raw[0xB2]),
      "gba_title_hex":raw[0xA0:0xAC].hex(),
      "gba_game_code_ascii":raw[0xAC:0xB0].decode("ascii","replace"),
      "gba_maker_code_ascii":raw[0xB0:0xB2].decode("ascii","replace"),
      "gba_header_complement":hex(raw[0xBD]),
      "last_non_ff_byte_index":len(raw.rstrip(b"\xff"))-1,
      "nm_defined_symbol_entries":count,
      "nm_defined_symbol_table_sha256":symhash}
   report["variants"][variant]=record
 if report["variants"]["original_agbcc"]["header_first_192_bytes_sha256"]!=report["variants"]["modern_gcc"]["header_first_192_bytes_sha256"]:
  raise RuntimeError("Pin-identical original and modern GBA cartridge headers unexpectedly differ")
 OUT.mkdir(exist_ok=True)
 (OUT/"compiled_runtime_rom_image_hashes.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k!="caveats"},indent=2))
if __name__=="__main__":main()
