#!/usr/bin/env python3
"""Read-only, pinned XGBA source census. Does NOT certify Phase 1 semantic mapping."""
from __future__ import annotations
import argparse, collections, csv, gzip, hashlib, json, os, re, subprocess, sys
from pathlib import Path

PINS = (
    ("pret/pokefirered", "ce6406d8c2eaf46d543c8a2606de0c3cb1951982", 9857),
    ("mgba-emu/mgba", "fd9dc5c2cbf234365068855851107e762fc6211b", 3161),
    ("huderlem/porymap", "26b919d7ff4b54152de010abd5bf344af2ebe116", 858),
    ("huderlem/poryscript", "c32481161c767b25a3425fa9f1f8729927ff3d55", 26),
    ("pret/agbcc", "da598c1d918402c42c0c0d7128ba14567f3175e9", 932),
)
SOURCE_EXT = {".c",".h",".cpp",".hpp",".cc",".cxx",".s",".asm",".inc",".ld",
              ".mk",".py",".sh",".go",".pl",".rs",".cmake",".pro",".pri",".js",".ts",".pory"}
CONFIG_EXT = {".json",".yaml",".yml",".toml",".ini",".cfg",".xml",".def",".in",".csv",".txt",
              ".qrc",".ui",".map"}
SOURCE_NAMES = {"Makefile","makefile","GNUmakefile","CMakeLists.txt","Dockerfile"}
RULES = {
    "rom_window": r"\b(?:GBA_(?:BASE|SIZE|REGION)_ROM[012](?:_EX)?|romMask|romSize|pristineRomSize|GBALoadROM|LOAD_CART)\b",
    "cartridge_stream": r"\b(?:romVf|GBAMatrix\w*|GBA_MATRIX_MAPPINGS_MAX|GBALoad(?:8|16|32)|GBAView(?:8|16|32))\b",
    "cpu_fetch": r"\b(?:activeRegion|activeMask|ARMWritePC|lastPrefetchedPc|prefetch)\b",
    "dma_save": r"\b(?:GBADMA\w*|EEPROM|SRAM|EREADER|waitstates|SaveSector)\b",
    "map_layout": r"\b(?:gMapLayouts|gMapGroups|map_groups\.json|layouts\.json|MapConnection|MapLayout|WarpEvent)\b",
    "script": r"\b(?:ScriptReadWord|ScriptReadByte|ScriptCall|ScriptJump|scriptPtr|ScrCmd_\w+|emitScriptStatement|map_script)\b",
    "graphics": r"\b(?:gMonFrontPicTable|gMonBackPicTable|gMonPaletteTable|CompressedSpriteSheet|LZ77UnComp\w*)\b",
    "audio": r"\b(?:gSongTable|m4aSongNum\w+|gVoicegroups|voicegroup|mid2agb|MPlayStart)\b",
    "game_data": r"\b(?:gSpeciesInfo|gBattleMoves|gItems|gTrainers|gEvolutionTable|gLevelUpLearnsets)\b",
    "save_state": r"\b(?:GBASerialize|GBADeserialize|GBASerializedState|romCrc32|GBAMatrixSerialize|GBAMatrixDeserialize)\b",
    "linker_build": r"\b(?:LD_SCRIPT|OBJCOPY|MAPJSON|PREPROC)\b|(?:\.incbin\s+|\.4byte\s+)",
    "editor_format": r"\b(?:ProjectFilePath|loadMap|saveMap|loadProject|saveProject|map\.json|QFile|QDir)\b",
}
PATTERNS = {key: re.compile(p) for key,p in RULES.items()}
INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]')
GOFUNC = re.compile(r'^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)\s*\(')
CFUNC = re.compile(r'^\s*(?:static\s+|inline\s+|const\s+|extern\s+|unsigned\s+|struct\s+)*[A-Za-z_][\w\s*&]*?\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{')
FIELDS = ("repo","revision","path","mode","blob_sha","bytes","category","scan_status",
          "source_lines","lexical_hits","reason")

def run(*cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT)

def checkout_sources(root):
    root.mkdir(parents=True, exist_ok=True)
    for repo,pin,_ in PINS:
        target = root / repo.split("/")[-1]
        if target.exists():
            raise RuntimeError(f"Refusing to reuse an existing checkout: {target}")
        print(f"Cloning {repo} at {pin[:12]}", flush=True)
        subprocess.run(["git","clone","--quiet","--filter=blob:none",
                        "https://github.com/"+repo+".git",str(target)],check=True)
        subprocess.run(["git","-C",str(target),"fetch","--quiet","origin",pin],check=True)
        subprocess.run(["git","-C",str(target),"checkout","--quiet","--detach",pin],check=True)
        if run("git","-C",str(target),"rev-parse","HEAD").decode().strip()!=pin:
            raise RuntimeError(f"Pinned commit mismatch: {repo}")
        if run("git","-C",str(target),"status","--porcelain").strip():
            raise RuntimeError(f"Checkout not clean: {repo}")

def classify(path):
    p=Path(path)
    if p.name in SOURCE_NAMES or p.suffix.lower() in SOURCE_EXT:
        return "source", ""
    if p.suffix.lower() in CONFIG_EXT:
        return "structured_or_text_config", ""
    if p.suffix.lower() in {".md",".rst",".pdf",".html",".htm"}:
        return "documentation", "preserved in manifest; no lexical source scan"
    return "asset_or_other", "preserved in manifest; requires asset-specific dependency review"

def git_entries(root):
    raw=run("git","-C",str(root),"ls-tree","-r","-l","-z","HEAD")
    for entry in raw.split(b"\0"):
        if not entry:
            continue
        attrs,path=entry.split(b"\t",1)
        mode,kind,sha,size=attrs.decode().split()
        yield mode,kind,sha,int(size) if size!="-" else -1,path.decode("utf-8","surrogateescape")

def git_blob_sha(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")

def census(root,out):
    out.mkdir(parents=True,exist_ok=True)
    (out/"checkpoints").mkdir(exist_ok=True)
    counts=collections.Counter()
    repos={}
    problems=[]
    total=0
    with (out/"tracked_file_manifest.csv.gz").open("wb") as mf, \
         (out/"lexical_sites.csv.gz").open("wb") as hf, \
         (out/"includes.csv.gz").open("wb") as inf, \
         (out/"symbol_candidates.csv.gz").open("wb") as sf:
        with gzip.open(mf,"wt",encoding="utf-8",newline="") as manifest, \
             gzip.open(hf,"wt",encoding="utf-8",newline="") as hits, \
             gzip.open(inf,"wt",encoding="utf-8",newline="") as incl, \
             gzip.open(sf,"wt",encoding="utf-8",newline="") as symbols:
            mw=csv.DictWriter(manifest,fieldnames=FIELDS);mw.writeheader()
            hw=csv.writer(hits);hw.writerow(("repo","path","blob_sha","line","rule","excerpt"))
            iw=csv.writer(incl);iw.writerow(("repo","path","blob_sha","line","include","resolution"))
            sw=csv.writer(symbols);sw.writerow(("repo","path","blob_sha","line","symbol","status"))
            for repo,pin,expected in PINS:
                checkout=root/repo.split("/")[-1]
                commit=run("git","-C",str(checkout),"rev-parse","HEAD").decode().strip()
                if commit!=pin: raise RuntimeError(f"Wrong pin: {repo}")
                entries=list(git_entries(checkout))
                repos[repo]={"commit":commit,"tracked":len(entries),"expected":expected,
                             "source_or_config_scanned":0,"lexical_sites":0}
                if len(entries)!=expected:
                    problems.append(f"Unexpected tracked-file count {repo}: {len(entries)} != {expected}")
                for mode,kind,sha,nbytes,path in entries:
                    total+=1
                    category,reason=classify(path)
                    status="excluded_with_reason"
                    line_count=0; hit_count=0
                    if kind!="blob":
                        status="non_blob";reason="git tree entry is not a blob"
                        problems.append(f"Non-blob entry: {repo}/{path}")
                    elif category in ("source","structured_or_text_config"):
                        try:
                            target=checkout/path
                            data=os.readlink(target).encode() if target.is_symlink() else target.read_bytes()
                            if git_blob_sha(data)!=sha:
                                raise ValueError("Git blob SHA mismatch")
                            if b"\0" in data:
                                raise ValueError("NUL bytes in apparent text")
                            content=data.decode("utf-8")
                            lines=content.splitlines()
                            line_count=len(lines)
                            for lineno,line in enumerate(lines,1):
                                for rule,regex in PATTERNS.items():
                                    if regex.search(line):
                                        hw.writerow((repo,path,sha,lineno,rule,line.strip()[:180]))
                                        hit_count+=1
                                im=INCLUDE.match(line)
                                if im: iw.writerow((repo,path,sha,lineno,im.group(1),"unresolved"))
                                if category=="source":
                                    f=GOFUNC.match(line) if path.endswith(".go") else CFUNC.match(line)
                                    if f: sw.writerow((repo,path,sha,lineno,f.group(1),"regex_candidate"))
                            status="lexically_scanned_review_pending"
                            reason="semantic disposition and dependent assets still require review"
                            repos[repo]["source_or_config_scanned"]+=1
                            repos[repo]["lexical_sites"]+=hit_count
                        except (OSError,UnicodeError,ValueError) as exc:
                            status="scan_error";reason=str(exc)
                            problems.append(f"{repo}/{path}: {exc}")
                    counts[status]+=1
                    mw.writerow({"repo":repo,"revision":pin,"path":path,"mode":mode,
                                 "blob_sha":sha,"bytes":nbytes,"category":category,
                                 "scan_status":status,"source_lines":line_count,
                                 "lexical_hits":hit_count,"reason":reason})
                    if total%500==0:
                        write_json(out/"checkpoints"/f"tracked_{total:05d}.json",
                                   {"tracked_processed":total,"scanned_source_config":counts["lexically_scanned_review_pending"],
                                    "lexical_sites":sum(r["lexical_sites"] for r in repos.values()),
                                    "mapping_approved":False})
                        print(f"Checkpoint: {total} tracked files",flush=True)
    expected_total=sum(p[2] for p in PINS)
    conditions={"tracked_file_count_matches":total==expected_total,
                "all_pinned_revisions_match":all(v["commit"]==next(p[1] for p in PINS if p[0]==k) for k,v in repos.items()),
                "all_source_config_content_scanned":not problems,
                "semantic_dispositions_complete":False}
    summary={"phase":"1","checkpoint":"full pinned Git source census",
             "repositories":repos,"tracked_files":total,
             "source_and_config_scanned":counts["lexically_scanned_review_pending"],
             "excluded_with_reason":counts["excluded_with_reason"],
             "lexical_sites":sum(v["lexical_sites"] for v in repos.values()),
             "source_scan_errors":problems[:200],"conditions":conditions,
             "census_complete":all(v for k,v in conditions.items() if k!="semantic_dispositions_complete"),
             "phase1_mapping_complete":False,
             "warning":"Lexical matches and source inventory do NOT constitute semantic review or a working ROM expansion."}
    write_json(out/"audit_summary.json",summary)
    write_json(out/"checkpoints"/f"tracked_{total:05d}_FINAL.json",
               {"tracked_processed":total,"scanned_source_config":summary["source_and_config_scanned"],
                "mapping_approved":False})
    print(json.dumps({"tracked_files":total,"scanned":summary["source_and_config_scanned"],
                      "lexical_sites":summary["lexical_sites"],
                      "census_complete":summary["census_complete"],"phase1_mapping_complete":False},indent=2))
    return 0 if summary["census_complete"] else 2

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,default=Path("upstream"))
    p.add_argument("--out",type=Path,default=Path("audit-output"))
    p.add_argument("--checkout",action="store_true")
    a=p.parse_args()
    try:
        if a.checkout: checkout_sources(a.root)
        sys.exit(census(a.root,a.out))
    except (RuntimeError,subprocess.CalledProcessError,OSError) as exc:
        a.out.mkdir(parents=True,exist_ok=True)
        write_json(a.out/"audit_failure.json",{"error":str(exc),"phase1_complete":False})
        print("AUDIT FAILED:",str(exc),file=sys.stderr)
        sys.exit(2)
