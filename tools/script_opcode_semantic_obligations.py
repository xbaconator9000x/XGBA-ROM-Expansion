#!/usr/bin/env python3
"""Pinned source execution/operand triage for every FireRed field and battle opcode.

This tool parses all 461 registered handlers and records explicit bytecode
cursor reads and writes, native pointer transformations, call/jump/return,
branching and ambiguous indirect reads. It DOES NOT infer path-complete schemas
from textual patterns. Unknown/branch-dependent cases must be reviewed.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path("upstream/pokefirered");OUT=Path("audit-output")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={"src/scrcmd.c":"97b695ee2f6fca80a3b78f52f6a444f696fe5814",
"src/battle_script_commands.c":"67f90a37044db87091b2174f78fe1e31ad2ef10d"}
FIELDS=("script_kind","opcode","handler","source_file","source_git_blob_sha",
 "definition_line","end_line","source_body_sha256","field_read_byte_sites",
 "field_read_halfword_sites","field_read_word_sites","battle_pointer_read_sites",
 "battle_halfword_read_sites","battle_byte_index_sites","cursor_advances",
 "cursor_assignments","native_pointer_casts","raw_memory_derefs",
 "branch_points","returns","external_calls","operand_schema_status",
 "side_effect_status","review_status")
READ_WORD=re.compile(r"\bScriptReadWord\s*\(")
READ_HALF=re.compile(r"\bScriptReadHalfword\s*\(")
READ_BYTE=re.compile(r"\bScriptReadByte\s*\(")
BATTLE_PTR=re.compile(r"\b(?:T1_READ_PTR|T2_READ_PTR)\s*\(")
BATTLE_HALF=re.compile(r"\b(?:T1_READ_16|T2_READ_16)\s*\(")
BATTLE_INDEX=re.compile(r"\bgBattlescriptCurrInstr\s*\[\s*[^]]+\]")
BRANCH=re.compile(r"\b(?:if|else|switch|case|for|while|goto|break|continue)\b")
RETURN=re.compile(r"\breturn\b")
CALL=re.compile(r"\b([A-Za-z_]\w*)\s*\(")
DEFS=re.compile(r"(?m)^\s*(?:static\s+)?(?:void|bool8|u8|u16|u32|s16|s32|int)\s+(ScrCmd_\w+|Cmd_\w+)\s*\([^;]*\)\s*\{")
CLEAN_BLOCK=re.compile(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",re.S)
def gib(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def clean(s):
 return CLEAN_BLOCK.sub(lambda m:" " if m.group(0).startswith(("/",'"',"'")) else m.group(0),s)
def braceclose(text,start):
 depth=0;state=None;escape=False;i=start
 while i<len(text):
  c=text[i]
  if state:
   if escape:escape=False
   elif c=="\\":escape=True
   elif c==state:state=None
  else:
   if c in ('"',"'"):state=c
   elif c=="{" :depth+=1
   elif c=="}":
    depth-=1
    if depth==0:return i+1
  i+=1
 raise RuntimeError("Unbalanced function braces at "+str(start))
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("FireRed pin mismatch")
 files={};defs={}
 for p,sha in BLOBS.items():
  data=(ROOT/p).read_bytes()
  if gib(data)!=sha:raise RuntimeError("Pinned source bytes changed: "+p)
  src=data.decode("utf-8","surrogateescape")
  files[p]=src
  sanitized=CLEAN_BLOCK.sub(lambda m:re.sub(r"[^\n]"," ",m.group(0)),src)
  for m in DEFS.finditer(sanitized):
   name=m.group(1)
   if name in defs:raise RuntimeError("Duplicate handler definition "+name)
   pos=sanitized.index("{",m.start(),m.end())
   end=braceclose(sanitized,pos)
   text=src[m.start():end]
   defs[name]={"source":p,"line":src.count("\n",0,m.start())+1,
     "end_line":src.count("\n",0,end)+1,"body":text}
 rows=[]
 with gzip.open(OUT/"bytecode_opcode_dispatch_semantic.csv.gz","rt",encoding="utf-8",newline="") as f:
  rows=list(csv.DictReader(f))
 if len(rows)!=461:raise RuntimeError("Expected 461 field/battle opcode slots")
 counts=collections.Counter();statuses=collections.Counter();unique_handlers=set()
 outpath=OUT/"script_opcode_semantic_obligations.csv.gz"
 with gzip.open(outpath,"wt",encoding="utf-8",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
  for entry in rows:
   kind=entry["dispatch_table"];idx=int(entry["opcode"]);name=entry["handler"]
   d=defs.get(name)
   if d is None:raise RuntimeError("Missing definition "+name)
   if d["source"]!=entry["handler_path"] or d["line"]!=int(entry["handler_definition_line"]):
    raise RuntimeError("Mismatched handler position "+name)
   unique_handlers.add((kind,name))
   body=clean(d["body"])
   read_byte=len(READ_BYTE.findall(body));read_half=len(READ_HALF.findall(body))
   read_word=len(READ_WORD.findall(body))
   bptr=len(BATTLE_PTR.findall(body));bhalf=len(BATTLE_HALF.findall(body))
   bindex=len(BATTLE_INDEX.findall(body))
   cursor_adv=len(re.findall(r"\b(?:ctx->scriptPtr|gBattlescriptCurrInstr)\s*(?:\+\+|--|\+=|-=)",body))
   cursor_assign=len(re.findall(r"\b(?:ctx->scriptPtr|gBattlescriptCurrInstr)\s*=(?!=)",body))
   native=bool(re.search(r"\(\s*(?:bool8|void|u16)\s*\(\s*\*|SetupNativeScript",body))
   raw=bool(re.search(r"\*\s*\(\s*(?:const\s+)?(?:u8|u16|u32)\s*\*\s*\)|\*\s*(?:ctx->scriptPtr|gBattlescriptCurrInstr)",body))
   branches=len(BRANCH.findall(body))
   returns=len(RETURN.findall(body))
   calls=set(CALL.findall(body))
   calls={n for n in calls if n not in {"if","for","while","switch","sizeof","return"}}
   external=len(calls)
   if kind=="FIELD":
    # Even a branch-free field handler may read pointer offsets indirectly.
    if branches or cursor_assign or native or raw:
     schema="BRANCH_POINTER_OR_SIDE_EFFECT_REVIEW"
    elif read_word or read_half or read_byte:
     schema="LINEAR_EXPLICIT_READ_SITES_ONLY_NOT_PATH_PROVED"
    else:schema="NO_EXPLICIT_SCRIPTREAD_IN_BODY_REQUIRES_CALL_REVIEW"
   else:
    schema=("BATTLE_CURSOR_CONTROL_FLOW_REVIEW" if branches or cursor_assign or bptr else
      "BATTLE_LITERAL_CURSOR_INCREMENT_CANDIDATE" if cursor_adv else
      "BATTLE_CURSOR_ACCESS_UNRESOLVED")
   side="NATIVE_OR_RAW_MEMORY_REQUIRES_MANUAL" if native or raw else "POSSIBLE_CALL_SIDE_EFFECTS_NOT_PROVED"
   for flag,observed in [("branching",branches>0),("cursor_assignment",cursor_assign>0),
                         ("native_cast",native),("raw_memory",raw),("ptr_read",read_word+bptr>0)]:
    if observed:counts[f"{kind.lower()}_{flag}"]+=1
   statuses[schema]+=1
   writer.writerow({"script_kind":kind,"opcode":idx,"handler":name,
      "source_file":d["source"],"source_git_blob_sha":BLOBS[d["source"]],
      "definition_line":d["line"],"end_line":d["end_line"],
      "source_body_sha256":hashlib.sha256(d["body"].encode("utf-8","surrogateescape")).hexdigest(),
      "field_read_byte_sites":read_byte,"field_read_halfword_sites":read_half,
      "field_read_word_sites":read_word,"battle_pointer_read_sites":bptr,
      "battle_halfword_read_sites":bhalf,"battle_byte_index_sites":bindex,
      "cursor_advances":cursor_adv,"cursor_assignments":cursor_assign,
      "native_pointer_casts":int(native),"raw_memory_derefs":int(raw),
      "branch_points":branches,"returns":returns,"external_calls":external,
      "operand_schema_status":schema,"side_effect_status":side,
      "review_status":"SOURCE_OBSERVED_PENDING_PATH_COMPLETE_SEMANTIC_REVIEW"})
  result={"opcodes_checked":len(rows),"unique_handlers":len(unique_handlers),
    "field_opcodes":sum(x["dispatch_table"]=="FIELD" for x in rows),
    "battle_opcodes":sum(x["dispatch_table"]=="BATTLE" for x in rows),
    "source_blob_sha_verified":BLOBS,"review_classifications":dict(statuses),
    "risk_site_counts":dict(counts),"path_complete_operand_schemas_approved":0,
    "handler_side_effects_fully_approved":0,
    "semantic_file_signoffs":0,"phase1_mapping_complete":False,
    "limitations":["Source body regex cannot prove path-dependent operand widths or macro expansion.",
      "Call-side effects and aliased pointers require compiler-backed control/data flow.",
      "Handlers that call helper functions can consume or modify cursor indirectly.",
      "Flags measure syntactic sites, not number of paths or runtime executions."]}
  (OUT/"script_opcode_semantic_obligations_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
