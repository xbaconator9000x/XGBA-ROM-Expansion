#!/usr/bin/env python3
"""All 14,834 pinned blobs: structural metadata, typed asset refs, config syntax.

Every entry verified against Git bytes. This does NOT claim that PNG meaning,
script execution, compiler macros, or unused assets can be inferred from bytes.
"""
import collections,csv,gzip,hashlib,json,os,re,struct,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path("upstream");OUT=Path("audit-output")
ASSET_EXT={".png",".gif",".bmp",".pal",".bin",".wav",".mid",".midi",".gb",".gba",".gbc",
           ".lz",".lz77",".ogg",".mp3",".flac",".ico",".jpg",".jpeg",".webp",".ttf",".woff",".woff2",".dat",".map",".sym"}
STRING_REF=re.compile(r'["\x27]([^"\x27\n]{1,350}\.(?:png|pal|bin|wav|mid|midi|gba|gbc|gb|gif|bmp|lz|lz77|ogg|mp3|jpg|jpeg|inc|s|json))["\x27]',re.I)
SCRIPT_ROLE={
 "maps":"map_assets_and_interaction","data/maps":"map_source",
 "data/layouts":"map_layout_source","graphics":"graphics_asset",
 "sound":"audio_asset","audio":"audio_asset","src/third-party":"vendor_dependency",
 "test":"test_fixture","tests":"test_fixture","fonts":"font_asset","tools":"build_tool",
}
def sha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def magic(data,ext):
 meta={"format":"unrecognized_or_raw","structural_kind":"raw_or_unknown"}
 if len(data)>=26 and data.startswith(b"\x89PNG\r\n\x1a\n"):
  w,h,depth,kind=struct.unpack(">IIBB",data[16:26])
  meta={"format":"PNG","width":w,"height":h,"bit_depth":depth,"color_type":kind}
 elif data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
  if len(data)>=10:meta={"format":"GIF","width":int.from_bytes(data[6:8],"little"),"height":int.from_bytes(data[8:10],"little")}
 elif data[:4]==b"RIFF" and data[8:12]==b"WAVE":
  meta={"format":"RIFF_WAVE"}
  pos=12
  while pos+8<=len(data):
   label=data[pos:pos+4];length=int.from_bytes(data[pos+4:pos+8],"little")
   if label==b"fmt " and length>=16 and pos+8+16<=len(data):
    fmt,ch,rate,byterate,align,bits=struct.unpack("<HHIIHH",data[pos+8:pos+24])
    meta.update({"codec_id":fmt,"channels":ch,"sample_rate_hz":rate,"bits_per_sample":bits})
    break
   pos+=8+length+(length&1)
 elif data[:4]==b"MThd" and len(data)>=14:
  n=struct.unpack(">IHHH",data[4:14])
  meta={"format":"MIDI","header_length":n[0],"midi_type":n[1],"declared_tracks":n[2],"ticks_per_quarter_or_smpte":n[3]}
 elif data.startswith(b"JASC-PAL"):
  meta={"format":"JASC_PALETTE"}
  try:meta["declared_colors"]=int(data.decode("ascii","replace").splitlines()[2])
  except (ValueError,IndexError):pass
 elif data[:4]==b"BM" and len(data)>=26:
  meta={"format":"BMP","width":int.from_bytes(data[18:22],"little"),"height":int.from_bytes(data[22:26],"little",signed=True)}
 elif data[:4]==b"\x00\x01\x00\x00" and ext==".ico":
  meta={"format":"ICO","entries":int.from_bytes(data[4:6],"little")}
 elif data[:4] in (b"wOFF",b"wOF2"):
  meta={"format":"WOFF2" if data[:4]==b"wOF2" else "WOFF"}
 elif data[:4] == b"\x7fELF":
  meta={"format":"ELF","class":data[4] if len(data)>4 else None}
 elif data[:2] == b"PK":
  meta={"format":"ZIP_CONTAINER"}
 elif ext==".pal":
  meta={"format":"PALETTE_BINARY_OR_TEXT","possible_RGB555_entries":len(data)//2 if len(data)%2==0 else None}
 elif ext in (".gb",".gba",".gbc"):
  meta={"format":"CARTRIDGE_IMAGE_CANDIDATE","header_verification":"NOT_PERFORMED"}
 return meta
def structural_role(repo,path):
 low=path.lower()
 if repo=="pret/pokefirered":
  if low.startswith(("graphics/pokemon/","sound/")):return "game_asset_potential"
  if low.startswith(("data/maps/","data/layouts/")):return "game_map_source_potential"
 for stem,role in SCRIPT_ROLE.items():
  if low.startswith(stem+"/") or "/"+stem+"/" in low:return role
 return "unclassified_structural_role"
def json_summary(data):
 try:
  obj=json.loads(data.decode("utf-8","surrogateescape"))
  if isinstance(obj,dict):return {"status":"JSON_PARSED","keys":sorted(list(obj))[:100],"root":"object","members":len(obj)}
  if isinstance(obj,list):return {"status":"JSON_PARSED","root":"array","items":len(obj)}
  return {"status":"JSON_PARSED","root":type(obj).__name__}
 except (ValueError,UnicodeError) as exc:return {"status":"JSON_PARSE_ERROR","error":str(exc)[:250]}
def xml_summary(data):
 try:
  el=ET.fromstring(data)
  return {"status":"XML_PARSED","root_tag":el.tag.split("}")[-1],"children":len(el)}
 except (ET.ParseError,UnicodeError) as exc:return {"status":"XML_PARSE_ERROR","error":str(exc)[:250]}
def lookup(repo,source,target,byrepo):
 if target.startswith("/") or ".." in Path(target).parts:return []
 poss=[target,str(Path(source).parent/target)]
 seen=set()
 for a in poss:
  key=os.path.normpath(a).replace("\\","/")
  if key in byrepo[repo]:seen.add(key)
 return sorted(seen)
def main():
 with gzip.open(OUT/"tracked_file_manifest.csv.gz","rt",encoding="utf-8",newline="") as f:manifest=list(csv.DictReader(f))
 if len(manifest)!=14834:raise RuntimeError("File manifest changed")
 byrepo=collections.defaultdict(set)
 for r in manifest:byrepo[r["repo"]].add(r["path"])
 totals=collections.Counter();formats=collections.Counter();config=collections.Counter()
 records=collections.defaultdict(list)
 with gzip.open(OUT/"all_file_structures.jsonl.gz","wt",encoding="utf-8") as out, \
      gzip.open(OUT/"explicit_asset_references.csv.gz","wt",encoding="utf-8",newline="") as refs:
  w=csv.writer(refs);w.writerow(["repo","from_path","git_blob_sha","line","literal","resolution","target_paths"])
  for n,r in enumerate(manifest,1):
   repo,path,blob=r["repo"],r["path"],r["blob_sha"]
   p=ROOT/repo.split("/")[-1]/path
   data=os.readlink(p).encode() if p.is_symlink() else p.read_bytes()
   if sha(data)!=blob:raise RuntimeError("Tracked Git blob content differs "+repo+"/"+path)
   ext=Path(path).suffix.lower()
   typ=r["category"]
   structural=magic(data,ext) if typ in ("asset_or_other","documentation") else {"format":"SOURCE_OR_CONFIG_TEXT"}
   row={"repo":repo,"revision":r["revision"],"path":path,"blob_sha":blob,
     "size":len(data),"file_type":typ,"role_hypothesis":structural_role(repo,path),
     "content":{"format":structural["format"],"metadata":structural},
     "referenced_asset_literals":0,"evidence_status":"ALL_BYTES_GIT_BLOB_VERIFIED_STRUCTURAL_ONLY",
     "semantic_signoff":False}
   formats[structural["format"]]+=1
   if ext==".json":
    row["syntax"]=json_summary(data);config[row["syntax"]["status"]]+=1
   elif ext in (".xml",".ui",".qrc",".vcxproj",".svg"):
    row["syntax"]=xml_summary(data);config[row["syntax"]["status"]]+=1
   if (typ in ("source","structured_or_text_config") or ext in (".s",".asm",".inc",".ld",".mk",".pory",".txt",".json",".yaml",".yml",".sh",".py",".html",".md")) and b"\0" not in data:
    lines=data.decode("utf-8","surrogateescape").splitlines()
    for ln,text in enumerate(lines,1):
     for match in STRING_REF.finditer(text):
      literal=match.group(1)
      opts=lookup(repo,path,literal,byrepo)
      kind=("UNIQUE_EXPLICIT_PATH_CANDIDATE" if len(opts)==1 else
            "AMBIGUOUS_EXPLICIT_PATH" if opts else "LITERAL_PATH_UNRESOLVED")
      w.writerow([repo,path,blob,ln,literal,kind,";".join(opts)])
      totals[kind]+=1
      row["referenced_asset_literals"]+=1
   out.write(json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n")
   totals["git_blob_verified"]+=1
   if n%500==0:
    folder=OUT/"asset_checkpoints";folder.mkdir(exist_ok=True)
    (folder/f"blobs_{n:05d}.json").write_text(json.dumps({
     "tracked_git_blobs_verified":n,"semantic_signoffs":0,"status":"STRUCTURAL_CLASSIFICATION_ONLY"})+"\n")
 if totals["git_blob_verified"]!=14834:raise RuntimeError("Incomplete verification")
 summary={"tracked_git_blobs_verified":14834,"tracked_total_expected":14834,
   "direct_asset_path_references":{k:v for k,v in totals.items() if k!="git_blob_verified"},
   "detected_data_formats":dict(formats),"structured_syntax":dict(config),
   "file_semantic_signoffs":0,"phase1_mapping_complete":False,
   "limitations":["Path and file magic do not establish asset usage or game meaning.",
    "Direct literal path references are candidate dependencies; generated symbol tables can be indirect.",
    "A missing direct reference does not prove an asset is unused.",
    "Binary blob content beyond recognized format headers has not been reverse-engineered.",
    "JSON/XML parse errors may be due to template files or incompatible dialects."]}
 (OUT/"all_file_structure_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k not in ("detected_data_formats","limitations")},indent=2))
if __name__=="__main__":main()
