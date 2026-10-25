#!/usr/bin/env python3
"""Pinned-source structural/semantic-index pass using real parser syntax trees.

Distinguishes observed AST facts from speculative cross-file targets. Every site
is pinned by Git blob hash and line. Parsing is not independent semantic signoff.
Never silently 'pass' files where parsing failed or grammar is unsupported.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,hashlib,json,os,re,sys
from pathlib import Path
from tree_sitter import Language,Parser
import tree_sitter_c,tree_sitter_cpp,tree_sitter_go,tree_sitter_python

LANGUAGES={
 "c":Language(tree_sitter_c.language()),
 "cpp":Language(tree_sitter_cpp.language()),
 "go":Language(tree_sitter_go.language()),
 "python":Language(tree_sitter_python.language()),
}
EXT={
 ".c":"c",".h":"c",".cc":"cpp",".cpp":"cpp",".cxx":"cpp",
 ".hpp":"cpp",".hh":"cpp",".hxx":"cpp",".go":"go",".py":"python",
}
PARSERS={k:Parser(v) for k,v in LANGUAGES.items()}
RELEVANT_MACROS={"ROM","RAM","EWRAM","IWRAM","SCRIPT","MAP","LAYOUT","SAVE","FLASH","DMA",
                 "EEPROM","PALETTE","TILESET","SPECIES","ITEM","TRAINER","AUDIO","M4A",
                 "GRAPHICS","POINTER","BANK","REGION","PAGE","DMA","MATRIX","GPIO"}
MEMORY_SIGNALS=re.compile(
 r"\b(?:0x0[89ABCDEF][0-9A-Fa-f]{6}|0x08[0-9A-Fa-f]{6}|"
 r"GBA_REGION_ROM[012]|GBA_BASE_ROM[012]|ROM_SIZE|romSize|romMask|"
 r"ROM_BASE|BASE_OFFSET|ROM0|ROM1|ROM2|EEPROM|SRAM|romVf|"
 r"activeRegion|activeMask|prefetch|GBASerialize|GBADeserialize|"
 r"gSaveBlock[12]Ptr|ScriptReadWord|scriptPtr|MapLayout|gMapGroups)\b")
DECLS={"function_definition","function_declaration","method_declaration","method_definition",
       "function_definition","method_definition"}
CALLS={"call_expression","call"}
READINGS={"field_expression","member_expression","selector_expression","attribute"}
WRITINGS={"assignment_expression","assignment","augmented_assignment","update_expression","assignment_statement"}
CONTROL={"if_statement","for_statement","for_range_loop","while_statement","switch_statement",
         "case_statement","return_statement","goto_statement","break_statement",
         "continue_statement","do_statement","for_in_clause","try_statement"}
STRUCTS={"struct_specifier","union_specifier","class_specifier","enum_specifier",
         "type_declaration","type_definition","type_spec"}
MAX_FILE=10*1024*1024
def sha(data):return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()
def preview(node,data,limit=200):
 return data[node.start_byte:min(node.end_byte,node.start_byte+limit)].decode("utf-8","replace").replace("\n"," ").strip()
def simple_name(node,data):
 if not node:return None
 if node.type in ("identifier","field_identifier","type_identifier","property_identifier"):
  return preview(node,data,160)
 if node.type in ("qualified_identifier","scoped_identifier","namespace_identifier"):
  return preview(node,data,160)
 if node.type in ("field_expression","member_expression","selector_expression","attribute"):
  fld=node.child_by_field_name("field") or node.child_by_field_name("name") or node.child_by_field_name("attribute")
  return simple_name(fld,data) if fld else preview(node,data,160)
 if node.type in ("pointer_declarator","reference_declarator","function_declarator","parenthesized_declarator",
                "array_declarator","attributed_declarator","init_declarator","abstract_function_declarator"):
  return simple_name(node.child_by_field_name("declarator"),data) or next(
   (x for n in node.named_children if (x:=simple_name(n,data))),None)
 if node.type in ("call_expression","call"):
  return simple_name(node.child_by_field_name("function"),data)
 return None
def def_name(node,data):
 return (simple_name(node.child_by_field_name("declarator"),data)
         or simple_name(node.child_by_field_name("name"),data)
         or simple_name(node.child_by_field_name("function"),data)
         or next((simple_name(n,data) for n in node.named_children if n.type in ("identifier","function_declarator")),None))
def parse_file(repo,path,blob,raw):
 lang=EXT[Path(path).suffix.lower()]
 tree=PARSERS[lang].parse(raw)
 root=tree.root_node
 functions=[];sites=[];type_defs=[];defs=[];errors=[]
 frames=[(root,None)]
 while frames:
  node,owner=frames.pop()
  typ=node.type
  here=owner
  if typ in DECLS and node.type!="function_declaration":
   name=def_name(node,raw)
   if not name: name=f"<anonymous@{node.start_point.row+1}>"
   here=f"{name}@{node.start_point.row+1}"
   functions.append({"name":name,"scope_id":here,"line":node.start_point.row+1,
         "end_line":node.end_point.row+1,
         "language":lang,"body_bytes":node.end_byte-node.start_byte})
   defs.append({"kind":"function","name":name,"line":node.start_point.row+1})
  elif typ in STRUCTS:
   name=def_name(node,raw)
   if name:type_defs.append({"kind":typ,"name":name,"line":node.start_point.row+1})
  if typ in CALLS:
   callee=node.child_by_field_name("function")
   if callee is None and node.named_children:callee=node.named_children[0]
   name=simple_name(callee,raw)
   is_direct=bool(callee and callee.type=="identifier" and name)
   sites.append({"kind":"call","scope":here,"line":node.start_point.row+1,
       "callee":name or preview(callee,raw,100) if callee else None,
       "direct_identifier":is_direct,
       "arg_count":sum(1 for x in (node.child_by_field_name("arguments").named_children
                    if node.child_by_field_name("arguments") else []) if x.type!="comment")})
  elif typ in WRITINGS:
   lhs=node.child_by_field_name("left") or node.child_by_field_name("target")
   rhs=node.child_by_field_name("right") or node.child_by_field_name("value")
   if lhs is None and node.named_children:lhs=node.named_children[0]
   sites.append({"kind":"write","scope":here,"line":node.start_point.row+1,
       "target":preview(lhs,raw,160) if lhs else None,
       "value_sample":preview(rhs,raw,120) if rhs else None,
       "operator":preview(node,raw,140)[:100]})
  elif typ in READINGS:
   sites.append({"kind":"member","scope":here,"line":node.start_point.row+1,
       "member":simple_name(node,raw),"expression":preview(node,raw,160)})
  elif typ in CONTROL:
   sites.append({"kind":"control","scope":here,"line":node.start_point.row+1,
       "control":typ})
  elif typ in ("preproc_def","preproc_function_def"):
   name=node.child_by_field_name("name")
   n=preview(name,raw,128) if name else None
   if n:defs.append({"kind":"macro","name":n,"line":node.start_point.row+1})
  elif typ=="ERROR":
   errors.append({"line":node.start_point.row+1,"excerpt":preview(node,raw,80)})
  # Inspect token text for memory expressions only on leaf nodes, not whole subtrees
  if len(node.children)==0 and (typ in ("identifier","number_literal","integer_literal","hex_integer")):
   val=preview(node,raw,95)
   if MEMORY_SIGNALS.search(val):
    sites.append({"kind":"memory_reference","scope":here,"line":node.start_point.row+1,"token":val})
  for child in reversed(node.named_children):frames.append((child,here))
 return {"lang":lang,"tree_has_errors":root.has_error,
   "error_nodes":errors[:120],"error_nodes_total":len(errors),
   "functions":functions,"type_definitions":type_defs,"definitions":defs,"sites":sites}
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--root",type=Path,default=Path("upstream"))
 ap.add_argument("--census",type=Path,default=Path("audit-output"))
 ap.add_argument("--out",type=Path,default=Path("audit-output"))
 a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 with gzip.open(a.census/"tracked_file_manifest.csv.gz","rt",newline="") as f:manifest=list(csv.DictReader(f))
 counts=collections.Counter();lang_counts=collections.Counter();all_functions=[];file_details=[]
 priority=json.loads((a.census/"second_pass_summary.json").read_text())
 risk_map={}
 with gzip.open(a.census/"semantic_review_queue.csv.gz","rt") as f:
  for row in csv.DictReader(f):risk_map[(row["repo"],row["path"])]=row["priority"]
 with gzip.open(a.out/"semantic_ast_sites.jsonl.gz","wt",encoding="utf-8") as out, \
      gzip.open(a.out/"semantic_ast_file_manifest.csv.gz","wt",encoding="utf-8",newline="") as index:
  fields=["repo","path","blob_sha","language","status","priority","functions",
          "types","sites","errors","parse_has_errors"]
  iw=csv.DictWriter(index,fieldnames=fields);iw.writeheader()
  for row in manifest:
   repo,path,blob=row["repo"],row["path"],row["blob_sha"]
   if row["category"] not in ("source","structured_or_text_config"):continue
   lang=EXT.get(Path(path).suffix.lower())
   if not lang:counts["unsupported_grammar"]+=1;continue
   target=a.root/repo.split("/")[-1]/path
   if target.is_symlink():
    counts["symlink_not_parsed"]+=1;continue
   data=target.read_bytes()
   if sha(data)!=blob:raise RuntimeError("Pinned blob changed "+repo+"/"+path)
   status="PARSED_AST"
   result={}
   if len(data)>MAX_FILE:
    status="LARGE_FILE_NOT_PARSED"
    result={"functions":[],"type_definitions":[],"definitions":[],"sites":[],
            "tree_has_errors":True,"error_nodes_total":0}
   elif b"\0" in data:
    status="BINARY_LIKE_TEXT_NOT_PARSED"
    result={"functions":[],"type_definitions":[],"definitions":[],"sites":[],
            "tree_has_errors":True,"error_nodes_total":0}
   else:
    result=parse_file(repo,path,blob,data)
    if result["tree_has_errors"]:status="PARSED_WITH_SYNTAX_ERRORS"
   rec={"repo":repo,"path":path,"git_blob_sha":blob,
     "pinned_revision":row["revision"],"status":status,"language":lang,
     "priority":risk_map.get((repo,path),"UNKNOWN"),
     "tree_has_errors":result["tree_has_errors"],"error_nodes_total":result["error_nodes_total"],
     "functions":result["functions"],"types":result["type_definitions"],
     "definitions":result["definitions"],"sites":result["sites"]}
   out.write(json.dumps(rec,ensure_ascii=True,separators=(",",":"))+"\n")
   iw.writerow({"repo":repo,"path":path,"blob_sha":blob,"language":lang,
    "status":status,"priority":rec["priority"],"functions":len(rec["functions"]),
    "types":len(rec["types"]),"sites":len(rec["sites"]),
    "errors":result["error_nodes_total"],"parse_has_errors":result["tree_has_errors"]})
   counts[status]+=1;lang_counts[lang]+=1
   for fn in result["functions"]:
    all_functions.append((repo,path,blob,fn["name"],fn["scope_id"],fn["line"],fn["end_line"],rec["priority"]))
   if sum(lang_counts.values())%500==0:
    p=a.out/"ast_checkpoints";p.mkdir(exist_ok=True)
    (p/f"parsed_{sum(lang_counts.values()):05d}.json").write_text(json.dumps({
      "ast_files_processed":sum(lang_counts.values()),"source_semantic_signoffs":0,
      "status":"UNREVIEWED_AST_INDEX_ONLY"})+"\n")
 byname=collections.defaultdict(list)
 for r in all_functions:byname[(r[0],r[3])].append(r)
 ambiguous=0;resolved=0;indirect=0;unknown=0
 with gzip.open(a.out/"semantic_call_graph.csv.gz","wt",encoding="utf-8",newline="") as fh:
  w=csv.writer(fh);w.writerow(["repo","caller_file","caller_scope","caller_line",
     "callee_name","resolution","candidate_targets","callee_paths"])
  with gzip.open(a.out/"semantic_ast_sites.jsonl.gz","rt",encoding="utf-8") as inp:
   for line in inp:
    r=json.loads(line)
    for s in r["sites"]:
     if s["kind"]!="call":continue
     key=(r["repo"],s["callee"])
     choices=byname.get(key,[])
     # A cross-file symbol match is only syntactic; don't confuse with actual linker resolution.
     if not s["direct_identifier"]:
      kind="INDIRECT_OR_MEMBER_CALL_UNRESOLVED";indirect+=1
     elif len(choices)==1:
      kind="UNIQUE_REPO_SYMBOL_CANDIDATE";resolved+=1
     elif choices:
      kind="AMBIGUOUS_REPO_SYMBOL_CANDIDATE";ambiguous+=1
     else:
      kind="EXTERNAL_MACRO_OR_FUNCTION_UNRESOLVED";unknown+=1
     w.writerow([r["repo"],r["path"],s["scope"] or "",s["line"],
       s["callee"] or "",kind,len(choices),
       ";".join(z[1]+":"+str(z[5]) for z in choices[:50])])
 with gzip.open(a.out/"semantic_function_definitions.csv.gz","wt",encoding="utf-8",newline="") as f:
  w=csv.writer(f);w.writerow(["repo","path","blob_sha","name","scope","start_line","end_line","priority"])
  w.writerows(all_functions)
 summary={"phase":"1","source_files_ast_attempted":sum(lang_counts.values()),
  "parse_status":dict(counts),"languages":dict(lang_counts),
  "function_definitions_indexed":len(all_functions),
  "direct_calls_unique_repo_symbol_candidate":resolved,
  "direct_calls_ambiguous_candidates":ambiguous,
  "calls_unresolved":unknown+indirect,
  "calls_indirect_member_unresolved":indirect,
  "file_semantic_signoffs":0,"phase1_mapping_complete":False,
  "limitations":[
    "Tree-sitter syntax trees do not preprocess conditional compilation.",
    "Unique symbol-name matching is not C/C++ name binding or linker resolution.",
    "Function-pointer, macros, templates, callbacks and generated code are not fully resolved.",
    "Grammar errors and unsupported file types are visible, not silently approved.",
    "No dynamic execution, binary inspection or external sidecar compatibility tests."
  ]}
 (a.out/"semantic_ast_summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
 print(json.dumps(summary,indent=2))
if __name__=="__main__":main()
