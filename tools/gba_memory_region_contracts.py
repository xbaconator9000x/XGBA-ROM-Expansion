#!/usr/bin/env python3
"""Extract every mGBA GBA memory decoder region branch from pinned source.

Enumerates the region access surface of actual CPU callback implementations.
Source-backed only: preprocessor cases, fallthrough, and runtime predicate values
still require separate compiler/CFG checks before semantic approval.
"""
from __future__ import annotations
import csv,gzip,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path("upstream/mgba")
OUT=Path("audit-output")
COMMIT="fd9dc5c2cbf234365068855851107e762fc6211b"
PATH="src/gba/memory.c";BLOB="aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc"
FUNCS=("GBASetActiveRegion","GBALoad32","GBALoad16","GBALoad8",
       "GBAStore32","GBAStore16","GBAStore8","GBALoadMultiple","GBAStoreMultiple")
FIELDS=["repo","path","blob_sha","function","function_start","function_end",
  "case_region","case_line","next_case_line","body_preview",
  "reads_rom_bytes","uses_romsize","uses_rommask","uses_eeprom",
  "uses_sram","uses_ereader","uses_gpio","uses_matrix","reads_ram",
  "uses_waitstate","branch_proof","semantic_status"]
CASE=re.compile(r"^\s*case\s+(GBA_REGION_[A-Za-z0-9_]+)\s*:")
def gitsha(b):return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=COMMIT:
  raise RuntimeError("Wrong pinned mGBA source")
 b=(ROOT/PATH).read_bytes()
 if gitsha(b)!=BLOB:raise RuntimeError("Pinned mGBA memory.c source bytes changed")
 lines=b.decode("utf-8","surrogateescape").splitlines()
 with gzip.open(OUT/"semantic_ast_sites.jsonl.gz","rt",encoding="utf-8") as f:
  source=next((json.loads(l) for l in f
    if '"path":"src/gba/memory.c"' in l and '"repo":"mgba-emu/mgba"' in l),None)
 if not source or source["git_blob_sha"]!=BLOB:
  raise RuntimeError("AST semantic evidence missing pinned memory.c")
 byname={x["name"]:x for x in source["functions"]}
 missing=[fn for fn in FUNCS if fn not in byname]
 if missing:raise RuntimeError("Memory region functions not indexed "+str(missing))
 totals={};enum_dist={};seen=set()
 with gzip.open(OUT/"gba_memory_region_branches.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
  for fn in FUNCS:
   meta=byname[fn];start=int(meta["line"]);end=int(meta["end_line"])
   region_lines=[]
   for lineno in range(start,end+1):
    m=CASE.match(lines[lineno-1])
    if m:region_lines.append((lineno,m.group(1)))
   if not region_lines:raise RuntimeError("No GBA memory enum case evidence in "+fn)
   totals[fn]=len(region_lines)
   for i,(line,region) in enumerate(region_lines):
    nxt=region_lines[i+1][0] if i+1<len(region_lines) else end+1
    body="\n".join(lines[line-1:min(nxt-1,end)])
    # Read/write classifications are lexical evidence inside a case scope, not
    # proof of active fallthrough or selected condition at execution time.
    text=body.lower()
    flags={
     "reads_rom_bytes":bool(re.search(r"(?:memory->rom|gba->memory.rom|romvf|rommask)",text)),
     "uses_romsize":"romsize" in text,
     "uses_rommask":"rommask" in text,
     "uses_eeprom":"eeprom" in text,
     "uses_sram":"sram" in text,
     "uses_ereader": "ereader" in text,
     "uses_gpio": "gpio" in text,
     "uses_matrix": "matrix" in text,
     "reads_ram":bool(re.search(r"(?:wram|iwram|memory->bios)",text)),
     "uses_waitstate":bool(re.search(r"(?:waitstates|wait\s*=|cycles)",text))}
    enum_dist[region]=enum_dist.get(region,0)+1
    w.writerow({"repo":"mgba-emu/mgba","path":PATH,"blob_sha":BLOB,
      "function":fn,"function_start":start,"function_end":end,
      "case_region":region,"case_line":line,"next_case_line":nxt,
      "body_preview":re.sub(r"\s+"," ",body)[:280],
      **flags,"branch_proof":f"{PATH}:{line}",
      "semantic_status":"RAW_REGION_BRANCH_EVIDENCE_CONDITIONAL_FLOW_UNVERIFIED"})
    seen.add((fn,region))
 summary={"pinned_revision":COMMIT,"source_blob_sha":BLOB,
   "memory_callback_functions_mapped":len(FUNCS),
   "region_case_sites":sum(totals.values()),
   "cases_per_function":totals,"region_occurrences":enum_dist,
   "missing_functions":missing,
   "rom2_extra_access_paths":[fn for fn,r in seen if r=="GBA_REGION_ROM2_EX"],
   "compiler_bound_mgba_core_available_separately":True,
   "region_fallthrough_semantics_verified":False,
   "external_memory_streaming_implemented":False,"phase1_mapping_complete":False}
 (OUT/"gba_memory_region_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
