#!/usr/bin/env python3
"""FireRed battle script opcode emitter-vs-runtime cursor audit.

The original C battle handlers access gBattlescriptCurrInstr directly; compare
bytecode macro widths to *literal unconditional-looking* cursor advances. This
is a conservative source-level correspondence, not path-complete data flow.
Every opcode receives a row with ambiguity classification and source anchors.
"""
from pathlib import Path
import collections,csv,gzip,hashlib,json,re,subprocess
ROOT=Path("upstream/pokefirered");OUT=Path("audit-output")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOB="67f90a37044db87091b2174f78fe1e31ad2ef10d"
COLUMNS=("opcode","handler","source_sha","source_line","end_line",
 "assembler_macros","macro_emitted_widths","expected_command_length",
 "literal_cursor_advances","cursor_assignment_count","read_pointer_count",
 "cursor_other_mutations","conditional_branch_tokens","helper_calls",
 "status","independent_semantic_signoff")
CODE=re.compile(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
INC=re.compile(r"\bgBattlescriptCurrInstr\s*\+=\s*(0x[0-9A-Fa-f]+|\d+)\s*;")
SET=re.compile(r"\bgBattlescriptCurrInstr\s*=(?!=)")
PTR=re.compile(r"\b(?:T1_READ_PTR|T2_READ_PTR)\s*\(")
OTHER=re.compile(r"\bgBattlescriptCurrInstr\s*(?:\+\+|--|-=|\*=|/=)")
BRANCH=re.compile(r"\b(?:if|switch|while|for|goto|case|else)\b")
CALL=re.compile(r"\b([A-Za-z_]\w*)\s*\(")
def blob(b):return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def rows(name):
 with gzip.open(OUT/name,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def noncode(text):return CODE.sub(lambda m:re.sub(r"[^\n]"," ",m.group(0)),text)
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Wrong pinned FireRed source commit")
 data=(ROOT/"src/battle_script_commands.c").read_bytes()
 if blob(data)!=BLOB:raise RuntimeError("Battle script command source content changed")
 lines=data.decode("utf-8","surrogateescape").splitlines()
 handlers={int(x["opcode"]):x for x in rows("script_opcode_semantic_obligations.csv.gz")
           if x["script_kind"]=="BATTLE"}
 if len(handlers)!=248:raise RuntimeError("Expected 248 battle opcode handlers")
 macros=collections.defaultdict(list)
 with gzip.open(OUT/"script_assembler_operand_variants.jsonl.gz","rt",encoding="utf-8") as f:
  for line in f:
   m=json.loads(line)
   if m["kind"]=="BATTLE":macros[int(m["opcode"])].append(m)
 if set(handlers)!=set(macros):raise RuntimeError("Battle opcode macro registry does not cover all 248 slots")
 counts=collections.Counter();output=[]
 for op,h in sorted(handlers.items()):
  first,last=int(h["definition_line"]),int(h["end_line"])
  if not 1<=first<=last<=len(lines):raise RuntimeError("Missing pinned handler positions")
  if h["source_git_blob_sha"]!=BLOB:raise RuntimeError("Wrong handler Git hash")
  code=noncode("\n".join(lines[first-1:last]))
  literal=[int(v,0) for v in INC.findall(code)]
  assignment=len(SET.findall(code))
  pointer=len(PTR.findall(code))
  other=len(OTHER.findall(code))
  branches=len(BRANCH.findall(code))
  call_names={n for n in CALL.findall(code) if n not in {"if","for","while","switch","return","sizeof","Cmd_"}}
  # Direct handler can call helpers that modify the global cursor indirectly.
  helpers=len({n for n in call_names if n != h["handler"]})
  variants=macros[op]
  fixed=[v for v in variants if v["grammar_status"]=="FIXED_LITERAL_ASSEMBLY_MACRO"]
  width=int(fixed[0]["fixed_macro_byte_count"]) if len(variants)==1 and len(fixed)==1 else None
  if len(variants)>1:
   status="MULTIPLE_ASSEMBLY_MACRO_VARIANTS"
  elif width is None:
   status="NONTRIVIAL_ASSEMBLER_GRAMMAR"
  elif branches or assignment or other:
   status="BRANCH_OR_CURSOR_REASSIGNMENT_REQUIRES_PATH_ANALYSIS"
  elif len(literal)==1 and literal[0]==width:
   status="LITERAL_CURSOR_ADVANCE_EQUALS_EMITTED_COMMAND_WIDTH"
  elif len(literal)==0:
   status="HANDLER_DOES_NOT_DIRECTLY_ADVANCE_CURSOR"
  else:
   status="LITERAL_ADVANCE_MISMATCH_OR_MULTIPLE_SITES"
  counts[status]+=1
  output.append({"opcode":op,"handler":h["handler"],"source_sha":BLOB,
   "source_line":first,"end_line":last,
   "assembler_macros":";".join(v["macro_name"] for v in variants),
   "macro_emitted_widths":";".join(",".join(str(x) for x in v["emitted_byte_lengths"]) for v in variants),
   "expected_command_length":width if width is not None else "",
   "literal_cursor_advances":";".join(str(v) for v in literal),
   "cursor_assignment_count":assignment,"read_pointer_count":pointer,
   "cursor_other_mutations":other,"conditional_branch_tokens":branches,
   "helper_calls":helpers,"status":status,
   "independent_semantic_signoff":False})
 with gzip.open(OUT/"battle_opcode_cursor_vs_assembler.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(output)
 summary={"battle_opcode_handlers_checked":len(output),"all_handlers_source_hash_verified":True,
  "classification_counts":dict(counts),
  "direct_literal_cursor_advance_matches":counts["LITERAL_CURSOR_ADVANCE_EQUALS_EMITTED_COMMAND_WIDTH"],
  "independent_complete_operand_role_reviews":0,
  "phase1_mapping_complete":False,
  "limitations":["One matching cursor increment need not be executed on every code path.",
   "Handler helper calls, macros and callbacks can mutate cursor indirectly.",
   "Script branch/pointer reads can use data tables and external calls with unknown ownership.",
   "Source emission width does not establish resource handle relocation safety."]}
 (OUT/"battle_opcode_cursor_alignment_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k!="limitations"},indent=2))
 if len(output)!=248:raise RuntimeError("Battle opcode coverage changed")
if __name__=="__main__":main()
