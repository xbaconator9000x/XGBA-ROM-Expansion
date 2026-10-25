#!/usr/bin/env python3
"""Exact-pinned mGBA CPU/Matrix Phase 1 source assertions; never review signoff."""
from __future__ import annotations
import collections, copy, csv, gzip, hashlib, json, re, subprocess, sys
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
REGISTRY = Path("semantic-snapshots/curated/mgba_cpu_matrix_abi_additive_candidates_2026-10-26.json")
QUEUE = Path("semantic-snapshots/current/semantic_review_queue.csv.gz")
BASE = Path("semantic-snapshots/curated/p0_semantic_review_candidates_2026-10-26.json")
GATE = Path("semantic-snapshots/current/phase1_mapping_gate.json")
OUT = Path("audit-output/mgba_cpu_matrix_abi_source_evidence.json")
CANDIDATES = {
    "include/mgba/internal/arm/arm.h": ("5ef2da96519ac3f429b65fd6d323be0775f3b3cf", [1,217]),
    "include/mgba/internal/arm/isa-inlines.h": ("ebda28e411f627c6cd1570aff6f29a3b79a60840", [1,186]),
    "include/mgba/internal/gba/memory.h": ("0aad912613e726560d06bbdbf6061986e69e5842", [1,183]),
    "include/mgba/internal/gba/cart/matrix.h": ("27e32a75c0f521dac9ded53821591485089d7b76", [1,35]),
}
EXPECTED = {p: sha for p,(sha,_) in CANDIDATES.items()}
EXPECTED.update({
    "src/arm/arm.c":"0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
    "src/gba/memory.c":"aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
    "src/gba/cart/matrix.c":"9ccbe883235b98bcf56cd609015e7b4003aa832c",
    "src/gba/serialize.c":"a307a51e751f412c64a7378323c56758304ebe85",
    "src/gba/gba.c":"c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
})
EDGES = {
    "CPU_TWO_SLOT_PREFETCH":("src/arm/arm.c:198-225","include/mgba/internal/arm/arm.h:168-189"),
    "BRANCH_REFILL_BINDS_GBA_REGION":("include/mgba/internal/arm/isa-inlines.h:73-91","src/gba/memory.c:42-80"),
    "ROM_EXEC_REGION_USES_BUFFER_AND_MASK":("src/gba/memory.c:338-349","include/mgba/internal/gba/memory.h:102-125"),
    "MATRIX_REMAPPING_MUTATES_EXEC_BACKING":("src/gba/cart/matrix.c:16-38","src/gba/memory.c:338-349"),
    "MATRIX_FIXED_16_SLOT_SAVESTATE":("include/mgba/internal/gba/cart/matrix.h:13-31","src/gba/cart/matrix.c:100-134"),
    "SAVESTATE_REPLAYS_MATRIX_AFTER_SAVEDATA":("src/gba/serialize.c:230-240","src/gba/cart/matrix.c:116-134"),
    "ROM_LOADER_MATRIX_MODE_NOT_EXTENSION":("src/gba/gba.c:432-449","src/gba/cart/matrix.c:40-80"),
    "ROM2_EX_HEADER_TO_EEPROM_DISPATCH":("include/mgba/internal/gba/memory.h:26-44","src/gba/memory.c:986-1001"),
}
# Source assertions are bounded to the exact line intervals, not whole-file
# regexes that can accidentally match a different function.
CHECKS = [
 ("ARM_CORE_TWO_SLOT_PREFETCH","include/mgba/internal/arm/arm.h",168,189,r"uint32_t prefetch\[2\];"),
 ("ARM_CALLBACK_ACTIVE_REGION_ABI","include/mgba/internal/arm/arm.h",113,136,r"const uint32_t\* activeRegion;\s*uint32_t activeMask;.*?void \(\*setActiveRegion\)"),
 ("ARM_BRANCH_REFILL_32","include/mgba/internal/arm/isa-inlines.h",73,81,r"setActiveRegion\(cpu, pc\);\s*LOAD_32\(cpu->prefetch\[0\], pc & cpu->memory.activeMask, cpu->memory.activeRegion\);.*?LOAD_32\(cpu->prefetch\[1\]"),
 ("THUMB_BRANCH_REFILL_16","include/mgba/internal/arm/isa-inlines.h",83,91,r"setActiveRegion\(cpu, pc\);\s*LOAD_16\(cpu->prefetch\[0\], pc & cpu->memory.activeMask, cpu->memory.activeRegion\);.*?LOAD_16\(cpu->prefetch\[1\]"),
 ("ARM_STEP_SHIFT_DIRECT_PREFETCH","src/arm/arm.c",198,214,r"cpu->prefetch\[0\] = cpu->prefetch\[1\];.*?LOAD_32\(cpu->prefetch\[1\], cpu->gprs\[ARM_PC\] & cpu->memory.activeMask, cpu->memory.activeRegion\)"),
 ("THUMB_STEP_SHIFT_DIRECT_PREFETCH","src/arm/arm.c",215,225,r"cpu->prefetch\[0\] = cpu->prefetch\[1\];.*?LOAD_16\(cpu->prefetch\[1\], cpu->gprs\[ARM_PC\] & cpu->memory.activeMask, cpu->memory.activeRegion\)"),
 ("GBA_ACTIVE_REGION_CALLBACK_BINDING","src/gba/memory.c",42,80,r"cpu->memory.setActiveRegion = GBASetActiveRegion;"),
 ("GBA_SAME_REGION_FAST_RETURN","src/gba/memory.c",285,302,r"if \(newRegion == memory->activeRegion\) \{.*?return;"),
 ("GBA_ROM_EXECUTION_REGION","src/gba/memory.c",338,349,r"case GBA_REGION_ROM2_EX:\s*cpu->memory.accessSource = mACCESS_PROGRAM;\s*cpu->memory.activeRegion = memory->rom;\s*cpu->memory.activeMask = memory->romMask;"),
 ("GBA_MEMORY_ROM_AND_PERIPHERAL_FIELDS","include/mgba/internal/gba/memory.h",102,125,r"uint32_t\* rom;.*?struct GBASavedata savedata;\s*struct GBAMatrix matrix;.*?size_t romSize;\s*uint32_t romMask;"),
 ("GBA_MEMORY_ROM2_EX_REGION","include/mgba/internal/gba/memory.h",26,44,r"GBA_REGION_ROM2_EX = 0xD"),
 ("MATRIX_FIXED_MAPPING_ARRAY","include/mgba/internal/gba/cart/matrix.h",13,31,r"#define GBA_MATRIX_MAPPINGS_MAX 16.*?uint32_t mappings\[GBA_MATRIX_MAPPINGS_MAX\];"),
 ("MATRIX_BACKING_VFILE_READ","src/gba/cart/matrix.c",16,38,r"gba->romVf->seek\(gba->romVf, gba->memory.matrix.paddr, SEEK_SET\);\s*gba->romVf->read\(gba->romVf, &gba->memory.rom\[gba->memory.matrix.vaddr >> 2\], gba->memory.matrix.size\);"),
 ("MATRIX_PADDR_26_BIT","src/gba/cart/matrix.c",40,80,r"gba->memory.matrix.paddr = value & 0x03FFFFFF;"),
 ("MATRIX_RESTORE_SIXTEEN_ENTRIES","src/gba/cart/matrix.c",116,134,r"for \(i = 0; i < 16; \+\+i\) \{\s*LOAD_32\(gba->memory.matrix.mappings\[i\].*?_remapMatrix\(gba\);"),
 ("MATRIX_SERIALIZE_SIXTEEN_ENTRIES","src/gba/cart/matrix.c",100,114,r"for \(i = 0; i < 16; \+\+i\) \{\s*STORE_32\(gba->memory.matrix.mappings\[i\]"),
 ("MATRIX_RESTORE_AFTER_EEPROM","src/gba/serialize.c",230,240,r"GBASavedataDeserialize\(&gba->memory.savedata, state\);.*?GBAMatrixDeserialize\(gba, state\);.*?mTimingInterrupt\(&gba->timing\);"),
 ("NATIVE_MATRIX_MARKER_NOT_XGBA","src/gba/gba.c",432,449,r"if \(gba->pristineRomSize > GBA_SIZE_ROM0\).*?if \(ident == 'M'\)"),
 ("ROM2_EX_EEPROM_AND_EREADER_PRIORITY","src/gba/memory.c",986,1001,r"case GBA_REGION_ROM2_EX:.*?GBACartEReaderWrite\(&memory->ereader, address, value\);.*?GBASavedataWriteEEPROM\(&memory->savedata, value, 1\);"),
]

def gitsha(raw):
 return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def span(ref):
 p, coords = ref.rsplit(":",1)
 a,b = [int(n) for n in coords.split("-")]
 return p,a,b

def validate(doc):
 if (doc.get("schema")!="xgba.phase1.additive_cpu_matrix_abi_semantic_candidates.v1"
     or doc.get("source_repository")!="mgba-emu/mgba" or doc.get("pinned_revision")!=PIN
     or doc.get("parent_curated_count_unchanged")!=29 or doc.get("prior_crosspacket_candidates")!=33
     or doc.get("additional_source_files")!=4 or doc.get("independent_whole_file_approvals")!=0
     or doc.get("phase1_mapping_complete") is not False):
  raise ValueError("Source packet pin, schema or review status drift")
 items=doc.get("candidates")
 if not isinstance(items,list) or len(items)!=4:
  raise ValueError("Four additive candidates required")
 seen=set()
 for item in items:
  p=item.get("path")
  if p not in CANDIDATES or p in seen:
   raise ValueError("Unknown/duplicate candidate")
  sha,lines=CANDIDATES[p]
  if (item.get("git_blob_sha1")!=sha or item.get("source_lines")!=lines
      or item.get("independent_signoff") is not False
      or not isinstance(item.get("semantic_roles"),list) or len(item["semantic_roles"])<2
      or not isinstance(item.get("unresolved"),list) or len(item["unresolved"])<2):
   raise ValueError("Candidate identity, roles, obligations or signoff invalid")
  seen.add(p)
 if seen!=set(CANDIDATES):
  raise ValueError("Missing source candidate")
 edges=doc.get("cross_source_contracts")
 if not isinstance(edges,list) or len(edges)!=len(EDGES):
  raise ValueError("Missing typed dependency")
 seen=set()
 for edge in edges:
  ident=edge.get("id")
  if ident not in EDGES or ident in seen:
   raise ValueError("Unknown/duplicate dependency")
  if (edge.get("producer"),edge.get("consumer"))!=EDGES[ident]:
   raise ValueError("Changed dependency endpoints")
  if (edge.get("proof_level")!="PINNED_SOURCE_INTERPRETATION_ONLY"
      or not isinstance(edge.get("meaning"),str) or len(edge["meaning"])<40):
   raise ValueError("False approval or missing semantic interpretation")
  for endpoint in ("producer","consumer"):
   p,a,b=span(edge[endpoint])
   if p not in EXPECTED or a<1 or b<a or not any(q==p and max(a,c)<=min(b,d) for _,q,c,d,_ in CHECKS):
    raise ValueError("Dependency endpoint lacks source expression")
  seen.add(ident)
 return True

def validate_snapshot(doc,rows,base,gate):
 validate(doc)
 if (len(rows)!=14834 or len({(r["repo"],r["path"]) for r in rows})!=14834
     or collections.Counter(r["priority"] for r in rows)["P0"]!=338
     or gate.get("decision")!="FAIL_INCOMPLETE" or gate.get("approved_semantic_dispositions")!=0
     or base.get("candidate_file_count")!=29 or base.get("independent_review_approvals")!=0
     or any(c.get("independent_whole_file_signoff") is not False for c in base["candidate_files"])):
  raise ValueError("Authoritative source queue or fail-closed gate drift")
 original={(c["repository"],c["source_path"]) for c in base["candidate_files"]}
 indexed={(r["repo"],r["path"]):r for r in rows}
 for p,sha in EXPECTED.items():
  key=("mgba-emu/mgba",p)
  if key not in indexed or indexed[key]["blob_sha"]!=sha:
   raise ValueError("Pinned dependency missing from source queue: "+p)
  if p in CANDIDATES and key in original:
   raise ValueError("Additive candidate overlaps original curated registry")
 return {"source_rows":14834,"p0_preserved":338,"original_curated":29,"additional_candidates":4,"approved":0}

def negative_controls(doc):
 cases=[
  ("false-approval",lambda d:d.update(independent_whole_file_approvals=1)),
  ("false-complete",lambda d:d.update(phase1_mapping_complete=True)),
  ("false-signoff",lambda d:d["candidates"][0].update(independent_signoff=True)),
  ("source-hash",lambda d:d["candidates"][0].update(git_blob_sha1="0"*40)),
  ("source-lines",lambda d:d["candidates"][0].update(source_lines=[1,2])),
  ("missing-obligations",lambda d:d["candidates"][0].update(unresolved=[])),
  ("missing-candidate",lambda d:d["candidates"].pop()),
  ("duplicate-candidate",lambda d:d["candidates"][1].update(path=d["candidates"][0]["path"])),
  ("missing-edge",lambda d:d["cross_source_contracts"].pop()),
  ("changed-edge",lambda d:d["cross_source_contracts"][0].update(consumer="src/gba/memory.c:1-2")),
  ("false-proof",lambda d:d["cross_source_contracts"][0].update(proof_level="APPROVED")),
 ]
 for label,mutate in cases:
  item=copy.deepcopy(doc);mutate(item)
  try:validate(item)
  except ValueError:continue
  raise AssertionError("Fail-open candidate mutation: "+label)
 return len(cases)

def verify_expressions(sources):
 evidence=[]
 for ident,path,start,end,pattern in CHECKS:
  lines=sources[path].splitlines(keepends=True)
  if end>len(lines):
   raise ValueError("Out-of-range source assertion: "+ident)
  m=re.search(pattern,"".join(lines[start-1:end]),re.S)
  if not m:
   raise ValueError("Missing pinned source expression: "+ident)
  evidence.append({"contract_id":ident,"source_path":path,"source_lines":[start,end],
   "git_blob_sha1":EXPECTED[path],"matched_expression_sha256":hashlib.sha256(m.group(0).encode("utf-8","surrogateescape")).hexdigest(),
   "status":"PINNED_SOURCE_ASSERTION_ONLY","independent_whole_file_signoff":False})
 return evidence

def verify(root,doc):
 validate(doc);negative=negative_controls(doc)
 with gzip.open(QUEUE,"rt",encoding="utf-8",newline="") as stream:rows=list(csv.DictReader(stream))
 base=json.loads(BASE.read_text(encoding="utf-8"));gate=json.loads(GATE.read_text(encoding="utf-8"))
 reconciliation=validate_snapshot(doc,rows,base,gate)
 if subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise ValueError("Wrong pinned mGBA commit")
 sources={}
 for p,sha in EXPECTED.items():
  raw=(root/p).read_bytes()
  if gitsha(raw)!=sha:raise ValueError("Pinned Git blob mismatch: "+p)
  sources[p]=raw.decode("utf-8","surrogateescape")
 evidence=verify_expressions(sources)
 mutants=[
  ("src/gba/cart/matrix.c","gba->romVf->read(","gba->romVf->skip("),
  ("include/mgba/internal/arm/isa-inlines.h","LOAD_16(cpu->prefetch[1]","LOAD_16(cpu->prefetch[2]"),
 ]
 for p,old,new in mutants:
  if old not in sources[p]:raise ValueError("Missing mutation anchor "+p)
  changed=dict(sources);changed[p]=changed[p].replace(old,new,1)
  try:verify_expressions(changed)
  except ValueError:continue
  raise AssertionError("Fail-open source-expression mutation: "+p)
 return {"schema":"xgba.phase1.mgba_cpu_matrix_abi_source_evidence.v1",
  "source_pin":PIN,"verified_source_blobs":len(EXPECTED),"verified_source_expressions":len(evidence),
  "verified_dependency_edges":len(EDGES),"additional_candidates":len(CANDIDATES),
  "registry_negative_controls_passed":negative,"source_mutation_negative_controls_passed":len(mutants),
  "source_queue_reconciliation":reconciliation,
  "source_queue_sha256":hashlib.sha256(QUEUE.read_bytes()).hexdigest(),
  "registry_sha256":hashlib.sha256(REGISTRY.read_bytes()).hexdigest(),
  "source_evidence":evidence,"independent_whole_file_approvals":0,
  "phase1_mapping_complete":False,"decision":"FAIL_INCOMPLETE",
  "limitations":["Line-bounded source assertions only; no full control-flow proof",
   "No independent review, compiled ABI, CPU/DMA runtime or editor round-trip certification",
   "No Phase 2 implementation or source census mutation"]}

if __name__=="__main__":
 try:
  doc=json.loads(REGISTRY.read_text(encoding="utf-8"))
  result=verify(Path(sys.argv[1] if len(sys.argv)>1 else "upstream/mgba"),doc)
  OUT.parent.mkdir(parents=True,exist_ok=True)
  OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
  print("Pinned CPU/Matrix: %d blobs, %d expressions, %d edges, %d negative controls, zero approvals; FAIL_INCOMPLETE" %
        (len(EXPECTED),len(CHECKS),len(EDGES),result["registry_negative_controls_passed"]+result["source_mutation_negative_controls_passed"]))
 except Exception as error:
  print("CPU/Matrix source verifier FAILED:",error,file=sys.stderr)
  sys.exit(2)
