#!/usr/bin/env python3
"""Pinned original-vs-modern FireRed saved-map UBFIX conditional semantics.

Checks exact source/Git identity, configuration, default branches and typed
saved view length. This is source-and-build-config semantic proof; not a claim
of live ROM memory-safety validation or independent per-file signoff.
"""
import hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/pokefirered")
OUT=Path("firered-variant-evidence")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={
 "config.mk":"c07d31fc083fa341cca29c340e560ed107d5364a",
 "Makefile":"8b454dbd18eb0069fa5851d788697190890a5b37",
 "include/config.h":"db131b2717ab739e62e41c5054a798f045c0631d",
 "include/global.h":"77155b09014aa854fcf87260e6ad2969e222da53",
 "src/fieldmap.c":"41567772299000ba5855419e5c39ad9373a34c20",
}
def gitblob(data):
 return hashlib.sha1(("blob %d\0"%len(data)).encode()+data).hexdigest()
def require(source,needle):
 if needle not in source:raise RuntimeError("Pinned source condition missing: "+needle[:90])
def source_context(raw,needle):
 lines=raw.splitlines()
 found=[i for i,l in enumerate(lines) if needle in l]
 if len(found)!=1:raise RuntimeError("Nonunique source anchor: "+needle)
 return found[0]+1
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Wrong pinned FireRed checkout")
 sources={}
 for path,sha in BLOBS.items():
  b=(ROOT/path).read_bytes()
  if gitblob(b)!=sha:raise RuntimeError("Changed git blob: "+path)
  sources[path]=b.decode("utf-8","surrogateescape")
 build=sources["config.mk"];mk=sources["Makefile"];cfg=sources["include/config.h"]
 glob=sources["include/global.h"];field=sources["src/fieldmap.c"]
 require(build,"MODERN        ?= 0")
 require(mk,"-DMODERN=$(MODERN)")
 require(glob,'#include "config.h"')
 require(field,'#include "global.h"')
 require(cfg,"#if MODERN\n#ifndef BUGFIX\n#define BUGFIX\n#endif // BUGFIX\n#ifndef UBFIX\n#define UBFIX\n#endif // UBFIX\n#endif // MODERN")
 require(glob,"u16 mapView[0x100];")
 require(field,"#ifndef UBFIX")
 require(field,"for (i = 0; i < 0x200; i++)")
 require(field,"for (i = 0; i < NELEMS(gSaveBlock2Ptr->mapView); i++)")
 before=field.index("#ifndef UBFIX")
 corrupt=field.index("for (i = 0; i < 0x200; i++)")
 fixed=field.index("for (i = 0; i < NELEMS(gSaveBlock2Ptr->mapView); i++)")
 if not before<corrupt<fixed or "#else" not in field[corrupt:fixed]:
  raise RuntimeError("Unexpected UBFIX branch order")
 for name,elf in (("classic","pokefirered.elf"),("modern","pokefirered_modern.elf")):
  if not (ROOT/elf).is_file():raise RuntimeError("Pinned compiled variant ELF absent: "+name)
 result={
  "schema":"xgba.phase1.pinned_firered_mapview_compile_branch.v1",
  "pinned_commit":PIN,"source_blob_sha1":BLOBS,
  "build_configuration_verified":"source-default MODERN=0; CI build arguments separately use MODERN=0/1",
  "source_include_chain":"src/fieldmap.c -> include/global.h -> include/config.h",
  "saved_view":{
   "type":"u16","declared_entries":256,"entry_size_bytes":2,
   "viewport_saved_entries":210,
   "classic_original_default":{"MODERN":0,"UBFIX_default":False,"scanned_entries":512,
    "out_of_bounds_scan_entries":256,"compiler_branch":"ifndef UBFIX"},
   "modern_gcc_default":{"MODERN":1,"UBFIX_default":True,"scanned_entries":256,
    "out_of_bounds_scan_entries":0,"compiler_branch":"else NELEMS"},
   "custom_make_CPPFLAGS_override_revalidation_required":True,
   "runtime_memory_access_observed":False
  },
  "source_anchors":{
   "default_MODERN":f"config.mk:{source_context(build,'MODERN        ?= 0')}",
   "compiler_MODERN_macro":f"Makefile:{source_context(mk,'-DMODERN=$(MODERN)')}",
   "modern_UBFIX_switch":f"include/config.h:{source_context(cfg,'#if MODERN')}",
   "mapView_type":f"include/global.h:{source_context(glob,'u16 mapView[0x100];')}",
   "original_bug_path":f"src/fieldmap.c:{source_context(field,'for (i = 0; i < 0x200; i++)')}",
   "modern_safe_path":f"src/fieldmap.c:{source_context(field,'for (i = 0; i < NELEMS(gSaveBlock2Ptr->mapView); i++)')}"
  },
  "compatibility_class":"COMPILER_CONFIGURATION_SENSITIVE",
  "semantic_disposition":"SOURCE_INTERPRETED_INDEPENDENT_REVIEW_PENDING",
  "independent_whole_file_approvals":0,
  "phase1_mapping_complete":False,
  "extension_implemented":False
 }
 OUT.mkdir(exist_ok=True)
 (OUT/"firered_saved_map_view_ubfix_variant_contract.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print("Source-verified original/modern UBFIX map-view branch: PASS")
if __name__=="__main__":main()
