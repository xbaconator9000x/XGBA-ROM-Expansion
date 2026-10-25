#!/usr/bin/env python3
"""Conservatively match FireRed field-script assembler operand widths to C reads.

A byte-exact emission grammar is checked against the directly observed sequence
of ScriptReadByte/Halfword/Word for eligible handlers. Helpers, aliases, native
pointers and branches are explicitly left unapproved for path-complete semantics.
"""
import collections,csv,gzip,hashlib,json,re,subprocess
from pathlib import Path
OUT=Path("audit-output");ROOT=Path("upstream/pokefirered")
PIN="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
SRC_SHA="97b695ee2f6fca80a3b78f52f6a444f696fe5814"
COLUMNS=["opcode","opcode_hex","handler","macro_variant_names","macro_emitted_operand_widths",
 "handler_explicit_read_widths","handler_branch_sites","handler_external_calls",
 "pinned_handler_blob_sha","handler_line_start","handler_line_end",
 "source_match_status","semantic_signoff"]
WIDTHS={"Byte":1,"Halfword":2,"Word":4}
READS=re.compile(r"\bScriptRead(Byte|Halfword|Word)\s*\(")
def sha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
C_LEXICAL_NONCODE=re.compile(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
def c_code_without_comments(text):
 # Preserve physical line count and byte offsets for pinned source evidence.
 return C_LEXICAL_NONCODE.sub(lambda m:re.sub(r"[^\n]"," ",m.group(0)),text)
def items_csv(path):
 with gzip.open(path,"rt",encoding="utf-8",newline="") as f:yield from csv.DictReader(f)
def main():
 if subprocess.check_output(["git","-C",str(ROOT),"rev-parse","HEAD"],text=True).strip()!=PIN:
  raise RuntimeError("Pinned FireRed moved")
 body=(ROOT/"src/scrcmd.c").read_bytes()
 if sha(body)!=SRC_SHA:raise RuntimeError("Handler source blob mismatch")
 lines=body.decode("utf-8","surrogateescape").splitlines()
 handlers={int(r["opcode"]):r for r in items_csv(OUT/"script_opcode_semantic_obligations.csv.gz")
            if r["script_kind"]=="FIELD"}
 if len(handlers)!=213:raise RuntimeError("Expected all 213 field opcode handler obligations")
 base=collections.defaultdict(list)
 with gzip.open(OUT/"script_assembler_operand_variants.jsonl.gz","rt",encoding="utf-8") as f:
  for line in f:
   v=json.loads(line)
   if v["kind"]=="FIELD":base[v["opcode"]].append(v)
 extended=collections.defaultdict(list)
 for r in items_csv(OUT/"script_conditional_opcode_variants.csv.gz"):
  extended[int(r["opcode"])].append({
    "macro_name":r["macro"]+"/"+r["variant"],
    "grammar_status":"GAS_CONDITIONAL_WITH_MAP_HELPER_SOURCE_RESOLVED",
    "emitted_byte_lengths":[int(v) for v in r["emitted_widths"].split(",")],
    "derived_handler_source_matched":r.get("handler_operand_width_match","False")=="True"})
 assert set(base)|set(extended)==set(handlers), "Assembler macros do not cover every field opcode"
 stats=collections.Counter();results=[]
 for opcode,handler in sorted(handlers.items()):
  starts=int(handler["definition_line"]);ends=int(handler["end_line"])
  if not 1<=starts<=ends<=len(lines):raise RuntimeError("Out-of-range pinned handler "+handler["handler"])
  section=c_code_without_comments("\n".join(lines[starts-1:ends]))
  if handler["source_git_blob_sha"]!=SRC_SHA:raise RuntimeError("Stale handler source revision")
  sequence=[WIDTHS[s] for s in READS.findall(section)]
  variants=base.get(opcode,[])
  if opcode in extended:
   # Explicitly compiled branch/width rule and matching C reads.
   v=extended[opcode][0]
   widths=v["emitted_byte_lengths"][1:]
   status="SOURCE_MATCHED_CONDITIONAL_BRANCH" if (widths==sequence and v["derived_handler_source_matched"]) else "CONDITIONAL_HANDLER_MISMATCH"
   variants=[v]
  elif len(variants)!=1:
   status="MULTIPLE_MACRO_VARIANTS_REVIEW"
   widths=[]
  else:
   v=variants[0]
   widths=v["emitted_byte_lengths"][1:]
   if v["grammar_status"]!="FIXED_LITERAL_ASSEMBLY_MACRO":
    status="NONTRIVIAL_ASSEMBLER_GRAMMAR"
   elif sequence!=widths:
    status="EXPLICIT_OPERAND_READ_SEQUENCE_MISMATCH_OR_INDIRECT_READ"
   elif int(handler["branch_points"])>0 or int(handler["cursor_assignments"])>0:
    status="SOURCE_READ_SEQUENCE_MATCHES_BUT_BRANCHING_REQUIRES_REVIEW"
   elif int(handler["native_pointer_casts"])>0 or int(handler["raw_memory_derefs"])>0:
    status="SOURCE_READ_SEQUENCE_MATCHES_BUT_POINTER_ROLE_REQUIRES_REVIEW"
   else:
    status="SOURCE_EXPLICIT_OPERAND_SEQUENCE_MATCHES_ASSEMBLER"
  stats[status]+=1
  results.append({"opcode":opcode,"opcode_hex":hex(opcode),"handler":handler["handler"],
    "macro_variant_names":";".join(v["macro_name"] for v in variants),
    "macro_emitted_operand_widths":",".join(str(x) for x in widths),
    "handler_explicit_read_widths":",".join(str(x) for x in sequence),
    "handler_branch_sites":handler["branch_points"],
    "handler_external_calls":handler["external_calls"],
    "pinned_handler_blob_sha":SRC_SHA,
    "handler_line_start":starts,"handler_line_end":ends,
    "source_match_status":status,"semantic_signoff":False})
 with gzip.open(OUT/"field_opcode_macro_vs_handler_alignment.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(results)
 summary={"field_opcodes_reviewed":len(results),"source_and_macro_sha_verified":True,
  "status_counts":dict(stats),
  "source_observed_operand_widths_match_without_flagged_control_or_pointer_ambiguity":
    stats["SOURCE_EXPLICIT_OPERAND_SEQUENCE_MATCHES_ASSEMBLER"],
  "source_proven_conditional_map_variants":stats["SOURCE_MATCHED_CONDITIONAL_BRANCH"],
  "path_complete_operand_schemas_approved":0,
  "source_opcode_handler_side_effects_approved":0,
  "phase1_mapping_complete":False,
  "limitations":["Direct ScriptRead calls may be delegated to helper routines or macros; unobserved cursor changes remain possible.",
    "Even a matching byte-read sequence does not prove destination type, resource ownership or pointer lifetime.",
    "Branch handlers, context mutation, pointer dereferences and alternate macro variants require dedicated review.",
    "Assembler macros are pinned source, not freshly executed machine-byte assembly fixtures."]}
 (OUT/"field_opcode_macro_vs_handler_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps({k:v for k,v in summary.items() if k!="limitations"},indent=2))
 if len(results)!=213:raise RuntimeError("Field opcode count mismatch")
 if stats["SOURCE_MATCHED_CONDITIONAL_BRANCH"]!=8:
  raise RuntimeError("Lost 8 verified conditional movement opcode schemas")
if __name__=="__main__":main()
