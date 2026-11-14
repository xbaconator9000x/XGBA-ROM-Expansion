#!/usr/bin/env python3
"""Build XGBA Goldenrod BG from the official PUBLIC v2.0.6 HnS source build.

Do not publish source-built .gba, asset bytes or a host provider. Original
owner-ROM identity is NOT asserted to match the source-built GBA's SHA.
"""
import argparse,hashlib,json,re,struct,subprocess,zlib
from pathlib import Path
import xgba_r53_original_tileset_packs as r53
import xgba_resource_sidecar as sidecar

RELEASE="167aa6d537b109bb229c231ddce4616974c4da71"
UPSTREAM="PokemonHnS-Development/pokehns-expansion"
SETS=(("gTileset_Johto_General_Hns",0x00f8823c,False,
       "data/tilesets/primary/johto_general_hns"),
      ("gTileset_Goldenrod_Hns",0x00f885e4,True,
       "data/tilesets/secondary/goldenrod_hns"))
class HnsSourceError(ValueError):pass

def attest(root,*,require_git=True):
 root=Path(root)
 if require_git:
  head=subprocess.run(["git","-C",str(root),"rev-parse","HEAD"],
    check=True,capture_output=True,text=True).stdout.strip()
  if head!=RELEASE:raise HnsSourceError("HnS source is NOT the official released v2.0.6 commit")
 m=json.loads((root/"data/maps/GoldenrodCity_hns/map.json").read_text())
 ls=json.loads((root/"data/layouts/layouts.json").read_text())["layouts"]
 matched=[x for x in ls if x["id"]=="LAYOUT_GOLDENROD_CITY_HNS"]
 if len(matched)!=1:raise HnsSourceError("Source Goldenrod layout missing/ambiguous")
 d=matched[0]
 if (m["id"]!="MAP_GOLDENROD_CITY_HNS" or
     m["layout"]!=d["id"] or d["width"]!=58 or d["height"]!=46 or
     (d["primary_tileset"],d["secondary_tileset"])!=tuple(x[0] for x in SETS)):
  raise HnsSourceError("Official Goldenrod map/layout/tilesets have drifted")
 if (root/d["blockdata_filepath"]).stat().st_size!=5336:
  raise HnsSourceError("Native Goldenrod 58x46 16-bit grid is not present")
 if sum(x.get("graphics_id")=="OBJ_EVENT_GFX_BOY_2_HNS" and
        (x.get("x"),x.get("y"))==(39,22) for x in m["object_events"])!=1:
  raise HnsSourceError("Original Goldenrod native NPC witness absent")
 for name,identity,secondary,prefix in SETS:
  p=root/prefix
  if not all((p/x).is_file() for x in
            ("tiles.png","metatiles.bin","metatile_attributes.bin")):
   raise HnsSourceError("Official BG art unavailable: "+name)
  if not all((p/"palettes"/f"{i:02d}.pal").is_file()
              for i in (range(7,13) if secondary else range(7))):
   raise HnsSourceError("Original palette slots missing: "+name)
 if not (root/"graphics/object_events/pics/people/boy_2_hns.png").is_file():
  raise HnsSourceError("Original Boy2 NPC art missing")
 return {"commit":RELEASE,"map":"GoldenrodCity_hns",
         "size":[58,46],"npc":"OBJ_EVENT_GFX_BOY_2_HNS","npc_xy":[39,22]}

def source_symbols(raw):
 found={}
 for line in raw.splitlines():
  m=re.fullmatch(r"([0-9A-Fa-f]{8})\s+[a-zA-Z]\s+([a-zA-Z_]\w*)",line.strip())
  if m:found[m[2]]=int(m[1],16)
 return found

def compile_source(root,rom,elf,out,*,symbols=None,require_git=True):
 proof=attest(root,require_git=require_git)
 rom=Path(rom);elf=Path(elf);out=Path(out)
 if out.exists():raise HnsSourceError("Private R93 art output directory must not exist")
 blob=rom.read_bytes()
 if not 16*1024*1024<=len(blob)<=32*1024*1024:
  raise HnsSourceError("Upstream source-built HnS ROM size invalid")
 if symbols is None:
  listing=subprocess.run(["arm-none-eabi-nm","-an","--defined-only",str(elf)],
      check=True,text=True,capture_output=True).stdout
  symbols=source_symbols(listing)
 resources=[]
 report=[]
 for name,logical,secondary,prefix in SETS:
  addr=symbols.get(name)
  if not isinstance(addr,int) or not 0x08000000<=addr<0x08000000+len(blob):
   raise HnsSourceError("Compiled HnS ELF missing actual original linked tileset: "+name)
  actual=addr-0x08000000
  try:
   _,head,parts=r53.descriptor_asset(blob,2,2,actual,secondary)
  except r53.TilesetFormatError as e:
   raise HnsSourceError("Real original source-built tileset decoder: "+str(e)) from e
  # Source-build ELF offsets may differ from the user's historical HnS ROM.
  # Re-key only R53's logical world2 resource ID, NOT the source pixel bytes.
  head=bytearray(head)
  struct.pack_into("<I",head,8,logical)
  struct.pack_into("<I",head,60,zlib.crc32(head[:60])&0xffffffff)
  identity=f"r53.w2.v2.t{logical:08x}"
  resources.append((identity+".meta",bytes(head)))
  for label,part in zip(r53.GRAPHIC_SECTIONS,parts):
   for i,offset in enumerate(range(0,len(part),r53.PAGE)):
    resources.append((f"{identity}.{label}{i:02d}",
          part[offset:offset+r53.PAGE].ljust(r53.PAGE,b"\0")))
  report.append({"source_symbol":name,"actual_built_offset":actual,
   "source_map_r52_logical_offset":logical,
   "source_rekeyed":actual!=logical,
   "decoded_source_section_sha256":[hashlib.sha256(p).hexdigest() for p in parts]})
 out.mkdir(parents=True,exist_ok=False)
 datafile=out/"r93-open-source-hns-tileset.bin"
 entries=[]
 with datafile.open("xb") as f:
  for key,payload in resources:
   offset=f.tell();f.write(payload)
   entries.append({"id":key,"offset":offset,"length":len(payload),
                   "sha256":hashlib.sha256(payload).hexdigest()})
 manifest={"format":sidecar.FORMAT,"version":sidecar.VERSION,
   "source_identity":{"id":"upstream-hns-v2.0.6-built",
     "sha256":hashlib.sha256(blob).hexdigest()},
   "data_file":datafile.name,"resources":entries}
 (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n")
 sidecar.load_manifest(out/"manifest.json")
 result={**proof,"result":"UPSTREAM_BUILD_R53_GOLDENROD_TWO_ORIGINAL_BG_TILESETS",
     "rom_sha256":hashlib.sha256(blob).hexdigest(),"tilesets":report,
     "resources":len(entries),"original_owner_rom_sha_equal_claimed":False,
     "native_hns_npc_animations_complete":False,
     "actual_player_three_world_fly_complete":False}
 (out/"provenance.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ("source-tree","built-gba","built-elf","private-out"):
  p.add_argument("--"+name,required=True,type=Path)
 a=p.parse_args()
 print(json.dumps(compile_source(a.source_tree,a.built_gba,a.built_elf,
                                 a.private_out),sort_keys=True,indent=2))
if __name__=="__main__":main()
