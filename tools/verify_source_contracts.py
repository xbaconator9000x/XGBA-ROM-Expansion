#!/usr/bin/env python3
"""Source-backed contract checks against pinned upstream bytes.
Assertions are exact invariants, not semantic signoff or execution tests."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
PINS={
"pret/pokefirered":"ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
"mgba-emu/mgba":"fd9dc5c2cbf234365068855851107e762fc6211b"}
CHECKS=[
("MGBA_CRC_WARNING_NONFATAL","mgba-emu/mgba","src/gba/serialize.c",
 "a307a51e751f412c64a7378323c56758304ebe85",
 r"if \(ucheck != gba->romCrc32\)\s*\{\s*mLOG\([^;]+;\s*\}"),
("MGBA_REMAP_BEFORE_REGION_RESET","mgba-emu/mgba","src/gba/serialize.c",
 "a307a51e751f412c64a7378323c56758304ebe85",
 r"GBAUnlCartDeserialize\(gba, state\);\s*gba->memory\.activeRegion = -1;\s*gba->cpu->memory\.setActiveRegion"),
("FIRERED_RAW_BYTECODE_DISPATCH","pret/pokefirered","src/script.c",
 "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
 r"cmdCode = \*\(ctx->scriptPtr\);\s*ctx->scriptPtr\+\+;"),
("FIRERED_RAW_SCRIPT_WORD","pret/pokefirered","src/script.c",
 "d0433bdda062b138e53d1a1d3184b4566ad7d9dc",
 r"u32 ScriptReadWord\([^)]*\)\s*\{[^}]*ctx->scriptPtr\+\+[^}]*\}"),
("FIRERED_SAVEBLOCK_RANDOM_OFFSET","pret/pokefirered","src/load_save.c",
 "8b723dd044c6024b3671bb890b25b56a53f99ec5",
 r"offset = \(Random\(\)\)[^;]*;\s*gSaveBlock2Ptr"),
("FIRERED_SAVE_ENCRYPTION_ROTATION","pret/pokefirered","src/load_save.c",
 "8b723dd044c6024b3671bb890b25b56a53f99ec5",
 r"ApplyNewEncryptionKeyToAllEncryptedData\(encryptionKey\);")
]
def run(root):
 findings=[]
 for label,repo,path,sha,pattern in CHECKS:
  folder=root/repo.split("/")[-1]
  commit=subprocess.check_output(["git","-C",str(folder),"rev-parse","HEAD"],text=True).strip()
  if commit!=PINS[repo]:raise RuntimeError("Wrong pinned commit for "+repo)
  data=(folder/path).read_bytes()
  blob=hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
  if blob!=sha:raise RuntimeError("Pinned blob mismatch "+repo+"/"+path)
  text=data.decode("utf-8","surrogateescape")
  match=re.search(pattern,text,re.S)
  if not match:raise RuntimeError("Source invariant not found: "+label)
  start=text.count("\n",0,match.start())+1
  end=text.count("\n",0,match.end())+1
  findings.append({"contract":label,"repo":repo,"commit":commit,"path":path,
                   "git_blob_sha":sha,"lines":[start,end],"source_check":"PASS",
                   "runtime_check":"NOT_RUN","whole_file_semantic_signoff":False})
 result={"source_checks":len(findings),"source_checks_passed":len(findings),
         "runtime_tests_run":0,"phase1_mapping_complete":False,"findings":findings}
 out=Path("audit-output/source_contract_assertions.json")
 out.parent.mkdir(exist_ok=True)
 out.write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps({"passed":len(findings),"mapping_complete":False}))
if __name__=="__main__":
 try:run(Path(sys.argv[1] if len(sys.argv)>1 else "upstream"))
 except Exception as e:print("CONTRACT CHECK FAILED:",e,file=sys.stderr);sys.exit(2)
