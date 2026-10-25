#!/usr/bin/env python3
"""Pinned FireRed and mGBA graphics memory, decompression and allocator ABI limits.

Checks source-anchored relations and derives concrete fixed resource bounds;
does not execute decompression or prove all possible buffer safety.
"""
import csv,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path("upstream");OUT=Path("audit-output")
PINS={"pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
"mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b"}
BLOBS={
("pret/pokefirered","src/main.c"):"542b0f5d16dd93107523d11163bfcb70a42b707a",
("pret/pokefirered","src/decompress.c"):"f4740f917ed9ae7e0fd967107e1e63733bb8c66a",
("pret/pokefirered","src/sprite.c"):"d0198d53004775c8664dcccf57833e178833776e",
("pret/pokefirered","include/gba/defines.h"):"5521e942c00cc2c263b842ae7608dfb7ac881a76",
("mgba-emu/mgba","include/mgba/internal/gba/memory.h"):"0aad912613e726560d06bbdbf6061986e69e5842",
("mgba-emu/mgba","src/gba/video.c"):"28f072ec0b880d272f4f9564cc5ca8f5af389caf"}
PROOFS=[
("XGBA-GFX-01","pret/pokefirered","src/main.c","EWRAM_DATA u8 gDecompressionBuffer[0x4000] = {0};",
 "Global decompression scratch buffer is 16 KiB in EWRAM.",
 "Compressed expansion size must be checked before using fixed EWRAM buffer."),
("XGBA-GFX-02","pret/pokefirered","src/decompress.c","LZ77UnCompWram(src->data, gDecompressionBuffer);",
 "Compressed sprite code decompresses directly into shared scratch RAM.",
 "External sprite data must validate 24-bit LZ output length, not assume fixed buffer is large enough."),
("XGBA-GFX-03","pret/pokefirered","src/decompress.c","buffer = AllocZeroed(*((u32 *)src->data) >> 8);",
 "Heap path sizes allocation using 24-bit decompressed length from first LZ word.",
 "Validate compressed header and length before reserving heap and decompressing."),
("XGBA-GFX-04","pret/pokefirered","src/decompress.c","dest.size = src->size;",
 "Sprite sheet allocation uses the declared SpriteSheet.size, separate from compressed output length.",
 "Verify declared tile count matches decompressed byte count before stage/copy."),
("XGBA-GFX-05","pret/pokefirered","src/sprite.c","s16 tileStart = AllocSpriteTiles(sheet->size / TILE_SIZE_4BPP);",
 "Sprite VRAM slot count calculated in units of 4bpp hardware tiles.",
 "Bound sprite sheet byte size, alignment and OBJ tile memory; no unlimited GPU tile slots."),
("XGBA-GFX-06","pret/pokefirered","src/sprite.c","CpuCopy16(sheet->data, (u8 *)OBJ_VRAM0 + TILE_SIZE_4BPP * tileStart, sheet->size);",
 "Sprite bytes move from transient buffer into fixed OBJ VRAM on successful load.",
 "Stage before copy; never treat a streaming host pointer as persistent OBJ tile pointer."),
("XGBA-GFX-07","pret/pokefirered","src/sprite.c","if (i == TOTAL_OBJ_TILE_COUNT)",
 "Sprite allocation explicitly stops at the hardware tile limit.",
 "Respect allocation failure instead of extending physical VRAM counts."),
("XGBA-GFX-08","pret/pokefirered","src/sprite.c","if (index == 0xFF)\n    {\n        return 0xFF;\n    }\n    else\n    {\n        sSpritePaletteTags[index] = palette->tag;",
 "Sprite palette allocator uses 0xFF when there is no free palette index.",
 "Handle palette exhaustion and preserve palette tags."),
("XGBA-GFX-09","pret/pokefirered","include/gba/defines.h","#define TOTAL_OBJ_TILE_COUNT 1024",
 "Original FireRed OBJ sprite allocator has 1024 4bpp tile units.",
 "External sprites may be unlimited in storage, never simultaneously resident in 1024 tile slots."),
("XGBA-GFX-10","mgba-emu/mgba","include/mgba/internal/gba/memory.h","GBA_SIZE_VRAM = 0x00018000,",
 "mGBA emulates 96 KiB of GBA VRAM, not arbitrary host VRAM.",
 "XGBA must maintain VRAM mirroring/timing and the hardware rendering memory model."),
("XGBA-GFX-11","mgba-emu/mgba","src/gba/video.c","video->vram = anonymousMemoryMap(GBA_SIZE_VRAM);",
 "Video memory allocation matches original GBA hardware VRAM capacity.",
 "Streaming resource cache must stage content into original VRAM budget."),
("XGBA-GFX-12","mgba-emu/mgba","src/gba/video.c","memcpy(state->vram, video->vram, GBA_SIZE_VRAM);",
 "GBA savestates serialize fixed original VRAM bytes.",
 "Any extended graphics residency cache needs separate versioned state and rebuild after restore."),
]
def sha1_blob(b):return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def main():
 for repo,pin in PINS.items():
  dest=ROOT/repo.split("/")[-1]
  if subprocess.check_output(["git","-C",str(dest),"rev-parse","HEAD"],text=True).strip()!=pin:raise RuntimeError("Pin mismatch "+repo)
 cache={};records=[]
 for id,repo,path,needle,observation,required in PROOFS:
  key=(repo,path)
  if key not in cache:
   p=ROOT/repo.split("/")[-1]/path;b=p.read_bytes()
   if sha1_blob(b)!=BLOBS[key]:raise RuntimeError("Unexpected source blob "+str(key))
   cache[key]=b.decode("utf-8","surrogateescape")
  text=cache[key]
  expected_count={"XGBA-GFX-02":2,"XGBA-GFX-03":2,
                  "XGBA-GFX-04":3,"XGBA-GFX-07":2}.get(id,1)
  actual_count=text.count(needle)
  if actual_count!=expected_count:
   raise RuntimeError(f"{id}: source anchor count differs: {actual_count} vs {expected_count}")
  location=text.index(needle)
  line=text.count("\n",0,location)+1
  records.append({"contract":id,"repo":repo,"revision":PINS[repo],"path":path,
   "source_blob":BLOBS[key],"line":line,"source_expression":needle,
   "observed":observation,"extension_requirement":required,
   "source_verification":"EXACT_PINNED_BLOB_ANCHOR",
   "decompression_or_runtime_test":"NOT_RUN","whole_file_signoff":False})
 OUT.mkdir(exist_ok=True)
 with (OUT/"graphics_hardware_contracts.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=records[0]);w.writeheader();w.writerows(records)
 summary={"source_contracts_verified":len(records),"unique_files_checked":len(cache),
  "fixed_fire_red_decompression_scratch_bytes":0x4000,
  "fire_red_4bpp_obj_tile_slots":1024,
  "gba_physical_vram_bytes":0x18000,
  "runtime_stage_tests_executed":0,
  "semantic_file_signoffs":0,"phase1_mapping_complete":False,
  "limitations":["Source anchors do not prove uncompressed LZ asset size for every sprite.",
    "Hardware VRAM capacity is distinct from external content storage size.",
    "No extended graphics stream, save state or editor round-trip implementation tested."]}
 (OUT/"graphics_hardware_contracts_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":
 try:main()
 except Exception as e:print("GRAPHICS CONTRACT ERROR",repr(e),file=sys.stderr);sys.exit(2)
