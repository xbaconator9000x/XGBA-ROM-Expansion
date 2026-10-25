#!/usr/bin/env python3
"""Source and ELF-verified reproducible FireRed cartridge identity excluding ONLY BuildDateTime.

The pinned original source has:
  #if MODERN
  const char BuildDateTime[] = __DATE__ " " __TIME__;
  #else
  #if REVISION == 0
  const char BuildDateTime[] = "2004 04 26 11:20";
This tool reads the actual symbol address and size from each linked ELF
and checks the ROM payload matches the expected type/width. NO other byte is
canonicalized; don't use this normalized SHA as an emulator execution guarantee.
"""
from __future__ import annotations
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered")
OUT=Path("firered-variant-evidence")
COMMIT="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MAIN_BLOB="542b0f5d16dd93107523d11163bfcb70a42b707a"
ROM_BASE=0x08000000
NAMES={"original_agbcc":("pokefirered.elf","pokefirered.gba"),
       "modern_gcc":("pokefirered_modern.elf","pokefirered_modern.gba")}
DATE_RE=re.compile(
 rb"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) [ 0-3][0-9] [0-9]{4} "
 rb"[0-2][0-9]:[0-5][0-9]:[0-5][0-9]\x00$")
def sha(data):return hashlib.sha256(data).hexdigest()
def gitsha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def main():
 revision=subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()
 if revision!=COMMIT:raise RuntimeError("Pinned FireRed revision mismatch")
 source=(ROOT/"src/main.c").read_bytes()
 if gitsha(source)!=MAIN_BLOB:raise RuntimeError("Changed BuildDateTime source revision")
 text=source.decode("utf-8","surrogateescape")
 patterns=[
  r"#if MODERN\s+const char BuildDateTime\[\] = __DATE__ \" \" __TIME__;",
  r"#else\s+#if REVISION == 0\s+const char BuildDateTime\[\] = \"2004 04 26 11:20\";",
 ]
 for pattern in patterns:
  if not re.search(pattern,text):raise RuntimeError("BuildDateTime source generation rule changed")
 source_count=text.count("const char BuildDateTime[]")
 if source_count!=4:raise RuntimeError("Unexpected BuildDateTime declarations")
 runtime=json.loads((OUT/"compiled_runtime_rom_image_hashes.json").read_text())
 allsym=json.loads((OUT/"compiled_full_symbol_delta_summary.json").read_text())
 if allsym["pinned_revision"]!=COMMIT or runtime["pinned_revision"]!=COMMIT:
  raise RuntimeError("Upstream compiler census revision mismatch")
 result={"pinned_commit":COMMIT,"source_main_blob_sha":MAIN_BLOB,
  "source_build_date_time_conditional_rule_verified":True,
  "symbol_name":"BuildDateTime","variants":{},
  "normalized_rom_byte_mutations_are_only_verified_timestamp_field":True,
  "runtime_behavior_tested":False,
  "independent_semantic_dispositions":0,
  "phase1_mapping_complete":False,
  "caveats":[
    "Normalized ROM SHA is a reproducibility diagnostic, not a legal native GBA checksum and not a final adapter authorization.",
    "The live original ROM bytes and exact ROM SHA remain authoritative for a strict plugin binary preflight.",
    "No instruction, palette, pointer, address, jump or other data is canonicalized.",
    "Changing other source/compiler settings requires new provenance and this contract must fail closed."
  ]}
 for variant,(elfname,romname) in NAMES.items():
  elf=ROOT/elfname
  rom=ROOT/romname
  if not elf.is_file() or not rom.is_file():raise RuntimeError("Missing compiled artifact "+variant)
  items=subprocess.check_output(["arm-none-eabi-nm","-n","-S",str(elf)],text=True)
  defs=[]
  for line in items.splitlines():
   x=re.match(r"^([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([RrDd])\s+BuildDateTime$",line)
   if x:defs.append((int(x.group(1),16),int(x.group(2),16),x.group(3)))
  if len(defs)!=1:raise RuntimeError("BuildDateTime missing/ambiguous in "+variant)
  address,size,typ=defs[0]
  data=rom.read_bytes()
  offset=address-ROM_BASE
  if not 0<=offset<len(data) or offset+size>len(data):
   raise RuntimeError("Timestamp symbol outside original ROM "+variant)
  section=data[offset:offset+size]
  if variant=="original_agbcc":
   if size!=17 or section!=b"2004 04 26 11:20\0":
    raise RuntimeError("Unexpected fixed classic BuildDateTime symbol")
  else:
   if size!=21 or not DATE_RE.fullmatch(section):
    raise RuntimeError("Unexpected modern GCC build-time symbol "+repr(section))
  if sha(data)!=runtime["variants"][variant]["rom_sha256"]:
   raise RuntimeError("Actual ROM hash mismatches previously checked image")
  normalized=bytearray(data)
  normalized[offset:offset+size]=b"\x00"*size
  result["variants"][variant]={
   "raw_rom_sha256":sha(data),
   "timestamp_neutralized_rom_sha256":sha(normalized),
   "symbol_address":hex(address),
   "rom_offset":hex(offset),
   "symbol_type":typ,
   "symbol_bytes":size,
   "compiler_timestamp_format":"YYYY_MM_DD_FIXED" if variant=="original_agbcc" else "GCC_DATE_TIME_MACROS",
   "field_start_inside_page_30":0x001E0000<=offset<0x001F0000,
   "source_blob_sha_verified":MAIN_BLOB,
   "mutation_scope":"ONLY_BuildDateTime_string_in_native_gba"
  }
 if not result["variants"]["modern_gcc"]["field_start_inside_page_30"]:
  raise RuntimeError("Modern BuildDateTime no longer resides in the previously observed differing page")
 OUT.mkdir(exist_ok=True)
 (OUT/"compiled_timestamp_neutralized_rom_hashes.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
