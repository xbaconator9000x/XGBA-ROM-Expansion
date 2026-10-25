#!/usr/bin/env python3
"""Prove important Qt map-editor signal ABI against real generated MOC and ELF.

Generated MOC source is compiler output, not a tracked upstream blob. The original
QObject header is pinned by Git SHA, each generated signal is present in MOC,
and a corresponding compiled method symbol is required in the original ELF.
"""
from pathlib import Path
import csv,hashlib,json,re,subprocess,sys
ROOT=Path("upstream/porymap")
OUT=Path("porymap-compiler-evidence")
PIN="26b919d7ff4b54152de010abd5bf344af2ebe116"
SOURCES={
 "Map":("include/core/map.h","47d52b08e4a403e88c80c0d436f563460721e65d","moc_map.cpp",
   ("modified","scriptsModified","mapDimensionsChanged","openScriptRequested","connectionAdded","connectionRemoved","layoutChanged")),
 "MapHeader":("include/core/mapheader.h","2058280a5c98d9abaf55bcda2a68471e6d26cccc","moc_mapheader.cpp",
   ("songChanged","locationChanged","requiresFlashChanged","weatherChanged","typeChanged","showsLocationNameChanged",
    "allowsRunningChanged","allowsBikingChanged","allowsEscapingChanged","floorNumberChanged","battleSceneChanged","modified")),
 "Layout":("include/core/maplayout.h","3095574b79604307ee31cc3fa0d111bd2cef242a","moc_maplayout.cpp",
   ("dimensionsChanged","needsRedrawing"))
}
CONNECTS={
 "src/core/map.cpp":("MapHeader::modified","Map::modified"),
 "src/mainwindow.cpp":("Map::modified",)
}
COLUMNS=("class","signal","header","header_git_sha","declaration_line","moc_cpp",
 "moc_source_sha256","moc_def_line","compiled_elf_symbol","compiled_symbol_present","source_evidence")
def blob(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Wrong Porymap commit")
 exe=ROOT/"porymap"
 if not exe.is_file():raise RuntimeError("Need previously compiled original Porymap executable")
 nm=subprocess.run(["nm","-C","--defined-only",str(exe)],capture_output=True,text=True,check=True)
 nms=nm.stdout.splitlines();records=[];moc_sizes={}
 for cls,(header,sha,generated,expected) in SOURCES.items():
  hdr=(ROOT/header).read_bytes()
  if blob(hdr)!=sha:raise RuntimeError("Pinned Qt header changed "+header)
  txt=hdr.decode("utf-8","surrogateescape")
  if "Q_OBJECT" not in txt:raise RuntimeError("Expected Q_OBJECT header "+header)
  signal_start=txt.find("signals:")
  if signal_start<0:raise RuntimeError("Missing signal block "+header)
  rest=txt[signal_start+len("signals:"):]
  end=re.search(r"(?m)^\s*(?:private|protected|public)(?:\s+slots)?:",rest)
  block=rest[:end.start()] if end else rest
  moc=ROOT/generated
  if not moc.is_file():raise RuntimeError("Missing generated Qt meta-object "+generated)
  mt=moc.read_text(errors="surrogateescape")
  if f"{cls}::qt_static_metacall" not in mt and f"{cls}::qt_metacall" not in mt:
   raise RuntimeError("Generated meta-object dispatch missing "+cls)
  moc_sizes[generated]=len(mt)
  for name in expected:
   mm=re.search(r"\bvoid\s+"+re.escape(name)+r"\s*\(",block)
   if not mm:raise RuntimeError(f"Missing upstream signal declaration {cls}::{name}")
   dline=txt.count("\n",0,signal_start+len("signals:")+mm.start())+1
   method=re.compile(r"\bvoid\s+"+re.escape(cls)+r"::"+re.escape(name)+r"\s*\(")
   generated_match=method.search(mt)
   if not generated_match:raise RuntimeError(f"Qt MOC omitted {cls}::{name}")
   mline=mt.count("\n",0,generated_match.start())+1
   compiled=[line.strip() for line in nms if re.search(r"\b"+re.escape(cls)+r"::"+re.escape(name)+r"\(",line)]
   if not compiled:raise RuntimeError(f"Qt ELF signal symbol missing {cls}::{name}")
   records.append({"class":cls,"signal":name,"header":header,
    "header_git_sha":sha,"declaration_line":dline,"moc_cpp":generated,
    "moc_source_sha256":hashlib.sha256(moc.read_bytes()).hexdigest(),
    "moc_def_line":mline,"compiled_elf_symbol":compiled[0][:220],
    "compiled_symbol_present":True,
    "source_evidence":"PINNED_QOBJECT_HEADER_AND_GENERATED_MOC_AND_COMPILED_ELF"})
 connection_proofs=[]
 for src,names in CONNECTS.items():
  text=(ROOT/src).read_text(encoding="utf-8",errors="surrogateescape")
  for name in names:
   index=text.find("&"+name)
   if index<0:raise RuntimeError("Missing pinned connection "+src+":"+name)
   tracked=subprocess.check_output(["git","-C",str(ROOT),"ls-files","-s","--",src],text=True).split()
   if len(tracked)<2 or blob((ROOT/src).read_bytes())!=tracked[1]:
    raise RuntimeError("Source changed "+src)
   connection_proofs.append({"file":src,"git_blob_sha":tracked[1],
     "signal_address_operand":name,"line":text.count("\n",0,index)+1,
     "binding_status":"CONNECT_SYNTAX_SOURCE_BACKED_RUNTIME_DELIVERY_UNPROVEN"})
 OUT.mkdir(parents=True,exist_ok=True)
 with (OUT/"qt_compiled_map_metaobject_signals.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(records)
 summary={"pinned_revision":PIN,"qobject_classes":len(SOURCES),"source_header_signals_proven":len(records),
  "generated_moc_translation_units":len(SOURCES),"moc_size_bytes":moc_sizes,
  "compiled_qt_elf_signal_symbols":len(records),"static_connection_site_samples":connection_proofs,
  "unresolved_dynamic_signal_connections":"NOT_FULLY_ANALYZED",
  "runtime_signal_delivery_tested":False,"whole_file_semantic_signoffs":0,"phase1_mapping_complete":False}
 (OUT/"qt_compiled_map_metaobject_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"classes":len(SOURCES),"compiled_signal_symbols_proven":len(records),
  "pinned_connection_operands":len(connection_proofs),"semantic_completion":False},indent=2))
if __name__=="__main__":main()
