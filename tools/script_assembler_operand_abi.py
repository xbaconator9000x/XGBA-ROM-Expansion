#!/usr/bin/env python3
"""Pinned FireRed assembler opcode operand layout inventory.

Registers 213 field and 248 battle handler slots against the actual assembler
macros that emit bytecode. Verifies emitted byte widths, macro variants and
argument positions where fully literal and fixed width. Does not assume pointer
semantic roles merely because an operand is 32 bits, and does not certify
conditional macros or handler control-flow.
"""
from pathlib import Path
import collections,csv,gzip,hashlib,json,re,subprocess
ROOT=Path("upstream/pokefirered")
OUT=Path("audit-output")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
INPUTS={
 "FIELD":("asm/macros/event.inc","142ad979d7d3093244087a247fa2b4883424f77f"),
 "BATTLE":("asm/macros/battle_script.inc","392a387e97adc84102a529f5a932db6745303b63")}
OUTPUT_FIELDS=("kind","opcode","handler","macro_name","macro_params","source_path","source_sha",
 "line_start","line_end","opcode_directive","emitted_byte_lengths",
 "emitted_operands","total_min_literal_bytes","fixed_macro_byte_count","grammar_status",
 "conditional_directives","unknown_emit_directives","macro_source_sha256")
EMITTER=re.compile(r"^\s*\.(byte|2byte|4byte|hword|short|word|long)\s+(.+)")
OPEN=re.compile(r"^\s*\.macro\s+([A-Za-z_]\w*)(.*)")
CLOSE=re.compile(r"^\s*\.endm\b")
LITERAL=re.compile(r"^0x[0-9a-fA-F]+$|^\d+$")
COND=re.compile(r"^\s*\.(?:if|ifdef|ifndef|ifc|ifnc|ifb|ifnb|else|elseif|endif|rept|endr|irp|irpc|altmacro)\b")
UNKNOWN=re.compile(r"^\s*\.(?:space|fill|incbin|align|balign|p2align|org|zero)\b")
def blob(x):return hashlib.sha1(f"blob {len(x)}\0".encode()+x).hexdigest()
def lines(path,expect):
 data=(ROOT/path).read_bytes()
 if blob(data)!=expect:raise RuntimeError("Pinned script macro blob differs "+path)
 return data.decode("utf-8","surrogateescape").splitlines()
def split_operands(text):
 # Top-level commas; do not split a parenthesized macro arithmetic expression
 expr=text.split("@",1)[0].strip()
 parts=[];depth=0;start=0
 for n,c in enumerate(expr):
  if c=="(":depth+=1
  elif c==")":depth=max(0,depth-1)
  elif c=="," and depth==0:
   parts.append(expr[start:n].strip());start=n+1
 parts.append(expr[start:].strip())
 return [p for p in parts if p]
def parse_macros(source):
 start=None;name=None;params="";body=[]
 for lineno,text in enumerate(source,1):
  m=OPEN.match(text)
  if m:
   if name is not None:raise RuntimeError("Nested macro definition "+name)
   name=m.group(1);params=m.group(2).strip();start=lineno;body=[];continue
  if CLOSE.match(text):
   if name is None:raise RuntimeError("Orphan .endm")
   yield {"name":name,"params":params,"start":start,"end":lineno,"body":body}
   start=None;name=None;body=[];continue
  if name is not None:body.append((lineno,text))
 if name is not None:raise RuntimeError("Unclosed assembler macro "+name)
def emitted(macro):
 emitted=[];widths=[];conditions=[];unknown=[];other=[]
 for lineno,txt in macro["body"]:
  stripped=txt.split("@",1)[0].strip()
  if COND.match(stripped):conditions.append({"line":lineno,"text":stripped});continue
  if UNKNOWN.match(stripped):unknown.append({"line":lineno,"text":stripped});continue
  m=EMITTER.match(stripped)
  if m:
   width={"byte":1,"2byte":2,"4byte":4,"hword":2,"short":2,"word":4,"long":4}[m.group(1)]
   for operand in split_operands(m.group(2)):
    emitted.append({"line":lineno,"bytes":width,"value":operand})
    widths.append(width)
  elif stripped and not stripped.startswith((".", "#", "@")):
   # A macro invocation or assembly instruction may emit bytes indirectly.
   other.append({"line":lineno,"text":stripped[:180]})
 return emitted,widths,conditions,unknown,other
def parse_id(arg):
 a=arg.split("@",1)[0].strip()
 m=re.match(r"^(0x[0-9A-Fa-f]+|\d+)(?=$|,|\s)",a)
 return int(m.group(1),0) if m else None
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Pinned FireRed checkout changed")
 slots={}
 with gzip.open(OUT/"bytecode_opcode_dispatch_semantic.csv.gz","rt",encoding="utf-8",newline="") as f:
  for row in csv.DictReader(f):
   k=(row["dispatch_table"],int(row["opcode"]))
   if k in slots:raise RuntimeError("Duplicate script opcode slot "+str(k))
   slots[k]=row
 if len(slots)!=461:raise RuntimeError("Expected original 461 field and battle opcode slots")
 variants=[];meta=collections.Counter();orphans=[];wrappers=[]
 byslot=collections.defaultdict(list)
 for kind,(path,sha) in INPUTS.items():
  src=lines(path,sha)
  for m in parse_macros(src):
   entries,widths,conditions,unknown,other=emitted(m)
   # stringvar is a one-byte argument encoder, not field opcode 0x00.
   # Its conditional 0/1/2 bytes are string-buffer indices and it is
   # invoked *inside* other field command macros (e.g. bufferspeciesname).
   if kind=="FIELD" and m["name"]=="stringvar":
    if m["params"]!="id:req" or m["start"]!=1028 or len(conditions)!=5:
     raise RuntimeError("Unexpected pinned stringvar helper ABI changed")
    wrappers.append({"kind":kind,"macro_name":m["name"],
      "start_line":m["start"],"reason":"CONDITIONAL_ARGUMENT_ENCODER_NOT_OPCODE",
      "emissions":len(entries),"source_blob_sha":sha})
    continue
   op=None
   if entries and entries[0]["bytes"]==1:op=parse_id(entries[0]["value"])
   if op is None:
    wrappers.append({"kind":kind,"macro_name":m["name"],
      "start_line":m["start"],"reason":"NO_LITERAL_1BYTE_OPCODE_FIRST","emissions":len(entries)})
    continue
   key=(kind,op)
   if key not in slots:
    orphans.append({"kind":kind,"macro_name":m["name"],"opcode":op,"line":m["start"]})
    continue
   if widths[0]!=1:raise RuntimeError("Non-byte opcode emitter "+m["name"])
   direct=not conditions and not unknown and not other
   klass=("FIXED_LITERAL_ASSEMBLY_MACRO" if direct else
          "CONDITIONAL_OR_NONTRIVIAL_ASSEMBLY_MACRO")
   if not direct:
    meta["dynamic_macro_variants"]+=1
   elif len(entries)>1:meta["fixed_operand_macros"]+=1
   else:meta["zero_operand_macros"]+=1
   body="\n".join(t for n,t in m["body"])
   entry={"kind":kind,"opcode":op,"handler":slots[key]["handler"],
    "macro_name":m["name"],"macro_params":m["params"],"source_path":path,
    "source_sha":sha,"line_start":m["start"],"line_end":m["end"],
    "opcode_directive":entries[0],
    "emitted_byte_lengths":widths,
    "emitted_operands":entries,
    "total_min_literal_bytes":sum(widths),
    "fixed_macro_byte_count":sum(widths) if direct else None,
    "grammar_status":klass,"conditional_directives":conditions,
    "unknown_emit_directives":unknown+other,
    "macro_source_sha256":hashlib.sha256(body.encode("utf-8","surrogateescape")).hexdigest()}
   byslot[key].append(entry);variants.append(entry)
 macroslots={k for k in byslot}
 missing=sorted(set(slots)-macroslots)
 field=[e for e in variants if e["kind"]=="FIELD"]
 battle=[e for e in variants if e["kind"]=="BATTLE"]
 with gzip.open(OUT/"script_assembler_operand_variants.jsonl.gz","wt",encoding="utf-8") as f:
  for m in variants:f.write(json.dumps(m,sort_keys=True,separators=(",",":"))+"\n")
 with gzip.open(OUT/"script_assembler_opcode_schema.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=OUTPUT_FIELDS);w.writeheader()
  for row in variants:
   w.writerow({"kind":row["kind"],"opcode":row["opcode"],"handler":row["handler"],
    "macro_name":row["macro_name"],"macro_params":row["macro_params"],
    "source_path":row["source_path"],"source_sha":row["source_sha"],
    "line_start":row["line_start"],"line_end":row["line_end"],
    "opcode_directive":row["opcode_directive"]["value"],
    "emitted_byte_lengths":",".join(str(x) for x in row["emitted_byte_lengths"]),
    "emitted_operands":json.dumps(row["emitted_operands"],separators=(",",":")),
    "total_min_literal_bytes":row["total_min_literal_bytes"],
    "fixed_macro_byte_count":row["fixed_macro_byte_count"] or "",
    "grammar_status":row["grammar_status"],
    "conditional_directives":len(row["conditional_directives"]),
    "unknown_emit_directives":len(row["unknown_emit_directives"]),
    "macro_source_sha256":row["macro_source_sha256"]})
 report={"original_opcode_slots":len(slots),"macro_variants_identified":len(variants),
  "field_macro_variants":len(field),"battle_macro_variants":len(battle),
  "opcode_slots_with_a_macro":len(macroslots),
  "opcode_slots_without_literal_opcode_macro":len(missing),
  "unmapped_opcode_slots":[{"kind":k,"opcode":n,"handler":slots[(k,n)]["handler"]} for k,n in missing],
  "fixed_width_macro_variants":meta["fixed_operand_macros"]+meta["zero_operand_macros"],
  "nontrivial_macro_variants":meta["dynamic_macro_variants"],
  "zero_operand_macro_variants":meta["zero_operand_macros"],
  "helper_macros_without_direct_opcode":len(wrappers),
  "macros_emitting_unknown_opcode":orphans[:80],
  "unmapped_helper_samples":wrappers[:30],
  "per_macro_compiled_assembler_execution":False,
  "pointer_roles_path_complete":False,"handler_cursors_crosschecked":False,
  "phase1_mapping_complete":False,"whole_file_signoffs":0,
  "limitations":["Width schema is the original GAS emission contract, not a proof that handlers consume exactly those bytes on all paths.",
    "Conditional macros, nested helper invocations and arithmetic packing remain unresolved.",
    "Several differently named macro variants can encode the same opcode with distinct defaults.",
    "A 32-bit macro operand can represent a code pointer, RAM pointer, table pointer or scalar; semantic roles require independent handler review."]}
 (OUT/"script_assembler_operand_summary.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in report.items() if k not in ("unmapped_opcode_slots","macros_emitting_unknown_opcode","unmapped_helper_samples","limitations")},indent=2))
 if len(variants)<300 or len(macroslots)<250:
  raise RuntimeError("Too few pinned assembler opcode definitions; inspect source syntax")
if __name__=="__main__":main()
