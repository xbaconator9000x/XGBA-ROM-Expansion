#!/usr/bin/env python3
"""Classify unresolved include candidates; these are hypotheses, not a compiler include graph."""
import collections,csv,gzip,json,re,sys
from pathlib import Path
ROOT=Path("audit-output")
STD_C={"assert.h","ctype.h","errno.h","float.h","inttypes.h","limits.h","locale.h",
 "math.h","setjmp.h","signal.h","stdarg.h","stdbool.h","stddef.h","stdint.h",
 "stdio.h","stdlib.h","string.h","time.h","wchar.h","wctype.h","iso646.h",
 "complex.h","fenv.h","tgmath.h","unistd.h","fcntl.h","memory.h","malloc.h",
 "strings.h","sys/types.h","sys/stat.h","sys/time.h","sys/mman.h","dirent.h",
 "windows.h","winuser.h","io.h","process.h","libgen.h","pthread.h",
 "dlfcn.h","getopt.h","alloca.h","reent.h","_ansi.h","varargs.h"}
STD_CPP={"string","vector","memory","utility","algorithm","iostream","fstream",
 "sstream","map","unordered_map","set","unordered_set","list","deque","queue",
 "stack","functional","tuple","array","iterator","atomic","mutex","thread",
 "chrono","random","numeric","limits","type_traits","stdexcept","exception",
 "cstdio","cstdlib","cstring","cstdint","cstddef","cmath","cassert",
 "climits","cctype","optional","variant","filesystem","initializer_list",
 "iomanip","ostream","istream","new","typeinfo","locale","bitset","memory"}
THIRD_PARTY={"zlib.h","png.h","jpeglib.h","SDL.h","SDL2/SDL.h","glib.h",
 "gdk/gdk.h","libintl.h","sqlite3.h","json/json.h","windowsx.h"}
GENERATED=re.compile(r"^(?:config\.h|insn-(?:config|codes|flags|attr(?:s)?|constants)\.h|"
 "insn-attr-common\.h|tm(?:_p)?\.h|auto-host\.h|options\.h|version\.h|"
 "constants/(?:layouts|map_groups|heal_locations|map_event_ids|region_map_sections)\.h)$")
QT=re.compile(r"^(?:Q[A-Z]\w*|Qt[A-Z]\w*|Qt(?:Core|Gui|Widgets|Network)/)")
def main():
 with gzip.open(ROOT/"tracked_file_manifest.csv.gz","rt") as f:manifest=list(csv.DictReader(f))
 by_repo=collections.defaultdict(list);basenames=collections.defaultdict(lambda:collections.defaultdict(list))
 for x in manifest:
  by_repo[x["repo"]].append(x["path"])
  basenames[x["repo"]][Path(x["path"]).name].append(x["path"])
 counts=collections.Counter(); byrepo=collections.defaultdict(collections.Counter)
 with gzip.open(ROOT/"resolved_include_edges.csv.gz","rt") as f:edges=list(csv.DictReader(f))
 with gzip.open(ROOT/"unresolved_include_dispositions.csv.gz","wt",newline="") as f:
  cols=["repo","from_path","line","include","class","hypothetical_local_paths","needs_manual_review"]
  out=csv.DictWriter(f,fieldnames=cols);out.writeheader()
  for edge in edges:
   if edge["resolution"]!="UNRESOLVED":continue
   repo=edge["repo"];inc=edge["include"];base=Path(inc).name
   choices=basenames[repo].get(base,[])
   if inc in STD_C or inc in STD_CPP:cls="STANDARD_LIBRARY_CANDIDATE"
   elif QT.match(inc):cls="QT_EXTERNAL_DEPENDENCY_CANDIDATE"
   elif GENERATED.match(inc):cls="GENERATED_BUILD_HEADER_CANDIDATE"
   elif inc in THIRD_PARTY or "/" in inc and inc.split("/")[0] in {"SDL2","GL","GLES2","sys","netinet","arpa","X11"}:
    cls="THIRD_PARTY_OR_PLATFORM_CANDIDATE"
   elif choices:cls="LOCAL_FILENAME_MATCH_REQUIRES_INCLUDE_PATH_REVIEW"
   else:cls="UNKNOWN_UNRESOLVED_INCLUDE"
   counts[cls]+=1;byrepo[repo][cls]+=1
   out.writerow({"repo":repo,"from_path":edge["from_path"],"line":edge["line"],
    "include":inc,"class":cls,"hypothetical_local_paths":";".join(choices[:16]),
    "needs_manual_review":True})
 result={"unresolved_includes_total":len([x for x in edges if x["resolution"]=="UNRESOLVED"]),
  "candidate_classification":dict(counts),"by_repository":{k:dict(v) for k,v in byrepo.items()},
  "semantic_resolution_verified":False,
  "warning":"These labels are heuristics. Build systems and compiler include flags must be inspected to verify actual resolution."}
 assert sum(counts.values())==result["unresolved_includes_total"]
 (ROOT/"include_classification_summary.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
 print(json.dumps(result["candidate_classification"],indent=2))
if __name__=="__main__":main()
