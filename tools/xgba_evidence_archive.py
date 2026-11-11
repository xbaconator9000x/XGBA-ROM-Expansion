#!/usr/bin/env python3
"""Preserve selected byte-identical native screenshots and report summaries from verified CI."""
import hashlib, io, json, os, struct, time, zipfile
from pathlib import Path
from urllib.request import Request, urlopen

REPO="xbaconator9000x/XGBA-ROM-Expansion"
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"evidence"/"verified"
SOURCES={
 "r9":(42950960274,13824972843,"83f50c9d65ed949e0b06e633efaae1f7eaf207dd",49,
  "crystal-real-mgba.gif magma-real-mgba.gif fallback-real-mgba.gif crystal-screenshot.png magma-screenshot.png fallback-screenshot.png r9-three-runs-comparison.png proof.json README.txt".split()),
 "r10":(42955838562,13827221467,"2ede1b8470cbf71318e44873497a8b8d2ab51526",51,
  "pallet-town-live-select-swap.gif pallet-town-crystal-before.png pallet-town-magma-after.png pallet-town-real-engine-comparison.png proof.json README.txt".split()),
 "r11":(42959825105,13828577188,"168d9137cb6b1576b53b6b0455d8c56a39bd943b",52,
  "r11-summary.json r11-frame-timings.csv 01-disabled.json 02-enabled.json 03-enabled.json 04-disabled.json 05-disabled.json 06-enabled.json README.txt".split()),
 "r12":(42964008063,13830302814,"864804eebcc90a90fb07a81ddc449440b2725827",53,
  ("enabled/01-initial.png enabled/02-after-select.png enabled/03-restored.png enabled/04-replayed.png "
   "disabled/01-initial.png disabled/02-after-select.png disabled/03-restored.png disabled/04-replayed.png "
   "enabled/proof.json disabled/proof.json summary.json").split()),
 "r13":(42966044589,13831536868,"f3ae6846e5971c0617674d5cef98be5331b91b2d",54,
  ("enabled/01-pallet.png enabled/02-house-external.png enabled/03-pallet-return.png "
   "enabled/04-house-reloaded.png disabled/01-pallet.png disabled/02-entry-refused.png proof.json").split()),
 "r14":(42977112057,13835737289,"3a1988e99da9285e8d194e9b1bbf9b3d936b6d3e",56,
  "01-pallet-external-tiles.png 02-house-door-external.png 03-pallet-door-return.png 04-route1-connected-external.png proof.json".split()),
}
def sha(b): return hashlib.sha256(b).hexdigest()
def fetch(url,token,maxlen):
    for attempt in range(3):
        req=Request("https://api.github.com"+url,headers={"Authorization":"Bearer "+token,
          "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
          "User-Agent":"xgba-verified-evidence"})
        try:
            with urlopen(req,timeout=90) as response:data=response.read(maxlen+1)
            if len(data)>maxlen:raise ValueError("Oversized response")
            return data
        except Exception:
            if attempt==2:raise
            time.sleep(1+attempt)
def check_media(name,b):
    if name.endswith(".png"):
        if not b.startswith(b"\x89PNG\r\n\x1a\n") or len(b)<24:raise ValueError("Invalid PNG")
        if struct.unpack(">II",b[16:24]) not in ((240,160),(1008,372),(1520,384)):
            raise ValueError("Unexpected native screenshot dimensions")
    elif name.endswith(".gif") and b[:6] not in (b"GIF89a",b"GIF87a"):
        raise ValueError("Invalid GIF")
def compact_json(b):
    obj=json.loads(b)
    if isinstance(obj,dict):
        for k in ("native_log","native_logs","native_execution_log","emulator_logs"):
            if k in obj:
                log=json.dumps(obj.pop(k),sort_keys=True,separators=(",",":")).encode()
                obj[k+"_sha256"]=sha(log)
                obj[k+"_note"]="Full native emulator console log in linked CI run"
    return (json.dumps(obj,indent=2,sort_keys=True)+"\n").encode()
def archive_one(name,info,token):
    run_id,artifact_id,head,pr,selected=info
    run=json.loads(fetch(f"/repos/{REPO}/actions/runs/{run_id}",token,200000))
    if run.get("head_sha")!=head or run.get("conclusion")!="success" or run.get("status")!="completed":
        raise ValueError(name+" is not passing exact-head CI")
    art=json.loads(fetch(f"/repos/{REPO}/actions/artifacts/{artifact_id}",token,200000))
    if art.get("expired") or art.get("workflow_run",{}).get("id") not in (None,run_id):
        raise ValueError(name+" artifact has expired or belongs to another run")
    data=fetch(f"/repos/{REPO}/actions/artifacts/{artifact_id}/zip",token,32*1024*1024)
    if not zipfile.is_zipfile(io.BytesIO(data)):raise ValueError(name+" not ZIP")
    folder=BASE/name
    folder.mkdir(parents=True,exist_ok=True)
    manifest={"milestone":name.upper(),"source_run":f"https://github.com/{REPO}/actions/runs/{run_id}",
      "source_artifact":f"https://github.com/{REPO}/actions/runs/{run_id}/artifacts/{artifact_id}",
      "source_head_sha":head,"implementation_pr":f"https://github.com/{REPO}/pull/{pr}",
      "source_artifact_zip_sha256":sha(data),"files":{}}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for item in selected:
            if item not in z.namelist() or item.startswith("/") or ".." in Path(item).parts:
                raise ValueError("Missing/unsafe evidence file "+item)
            ext=Path(item).suffix.lower()
            if ext not in (".png",".gif",".json",".txt",".csv"):
                raise ValueError("Forbidden file type "+item)
            original=z.read(item)
            if len(original)>4*1024*1024:raise ValueError("Unexpectedly large file")
            if ext in (".png",".gif"):check_media(item,original)
            content=compact_json(original) if ext==".json" and len(original)>100000 else original
            if ext==".json":json.loads(content)
            target=folder/item
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(content)
            manifest["files"][item]={"original_sha256":sha(original),
               "archived_sha256":sha(content),"unaltered":original==content,
               "size":len(content)}
    (folder/"provenance.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("PASS_ARCHIVED_"+name.upper(),len(selected),"files")
    return len(selected)
def thumb(folder,file,title):
    path=f"verified/{folder}/{file}"
    return f"[![{title}]({path})]({path})"
def row(cells):
    return "| "+" | ".join(cells)+" |"
def gallery():
    x=["# XGBA — permanent verified evidence gallery","",
       "Native emulator screenshot/GIF files here are unmodified bytes from passing exact-head CI.",
       "No AI mockups or host-made replacement scenes. Large emulator-console JSON logs",
       "are omitted from compact verification summaries, with their source hashes preserved.",
       "No executable ROMs, sidecars, save files or raw proprietary game assets are archived.",
       "Screenshots contain game imagery belonging to its rights holders and are shown",
       "only as limited, noncommercial engineering documentation.","",
       "## R14 — external tilesets, actual house door and connected Route 1","",
       row(["Pallet Town","Player's house","House exit","Route 1"]),
       row(["---"]*4),
       row([thumb("r14",f,n) for f,n in [
         ("01-pallet-external-tiles.png","Outdoor"),
         ("02-house-door-external.png","House"),
         ("03-pallet-door-return.png","Return"),
         ("04-route1-connected-external.png","Connected Route 1")]]),
       "",
       "[Original R14 4/4 native CI](https://github.com/"+REPO+"/actions/runs/42977112057) · ",
       "[Provenance](verified/r14/provenance.json) · [Proof summary](verified/r14/proof.json)","",
       "## R13 — the original house layout beyond 32 MiB","",
       row(["Externally loaded house","Returned to Pallet","Re-entered house","Disabled-mode control"]),
       row(["---"]*4),
       row([thumb("r13",f,n) for f,n in [
         ("enabled/02-house-external.png","House"),
         ("enabled/03-pallet-return.png","Pallet"),
         ("enabled/04-house-reloaded.png","Reload"),
         ("disabled/02-entry-refused.png","Disabled")]]),
       "",
       "[Original R13 4/4 native CI](https://github.com/"+REPO+"/actions/runs/42966044589) · [Provenance](verified/r13/provenance.json)","",
       "## R12 — real save-state restoration and external resource reacquisition","",
       row(["Before SELECT","After SELECT","Native restore","Reacquisition"]),
       row(["---"]*4),
       row([thumb("r12",f,n) for f,n in [
         ("enabled/01-initial.png","Initial"),
         ("enabled/02-after-select.png","Swapped"),
         ("enabled/03-restored.png","Restored"),
         ("enabled/04-replayed.png","Reacquired")]]),
       "",
       "[Original R12 4/4 native CI](https://github.com/"+REPO+"/actions/runs/42964008063) · [Provenance](verified/r12/provenance.json)","",
       "## R11 — measured native FireRed CPU-frame throughput (not GUI FPS)","",
       "[Complete measured benchmark summary](verified/r11/r11-summary.json) · [Frame timings CSV](verified/r11/r11-frame-timings.csv) · ",
       "[Original native CI](https://github.com/"+REPO+"/actions/runs/42959825105)","",
       "## R10 — live native FireRed Pallet Town sprite swap","",
       "![Original native Pallet Town GIF](verified/r10/pallet-town-live-select-swap.gif)","",
       "[Original R10 CI](https://github.com/"+REPO+"/actions/runs/42955838562) · [Comparison](verified/r10/pallet-town-real-engine-comparison.png)","",
       "## R9 — same ROM, two different external graphics packs","",
       row(["Crystal","Magma","Disabled fallback"]),
       row(["---"]*3),
       row([thumb("r9",f,n) for f,n in [
         ("crystal-real-mgba.gif","Crystal"),
         ("magma-real-mgba.gif","Magma"),
         ("fallback-real-mgba.gif","Fallback")]]),
       "",
       "[Original R9 native CI](https://github.com/"+REPO+"/actions/runs/42950960274) · [Three-run comparison](verified/r9/r9-three-runs-comparison.png)","",
       "## Permanent integrity and attribution","",
       "For every milestone, its provenance.json links to the passing source workflow",
       "and the exact executable commit, and records the original artifact SHA-256",
       "and per-file hashes. Original screenshots and GIFs are byte-for-byte preserved.",
       "Compact proof summaries are clearly marked by unaltered=false and retain",
       "the original document SHA-256. Repository history preserves these selected",
       "documentation assets even after GitHub Actions download links expire.",""]
    return "\n".join(x)
def main():
    token=os.getenv("GITHUB_TOKEN")
    if not token:raise ValueError("GITHUB_TOKEN missing")
    if os.getenv("GITHUB_REPOSITORY",REPO)!=REPO:raise ValueError("Unexpected repository")
    count=0
    for name,info in SOURCES.items():count+=archive_one(name,info,token)
    if count<40:raise ValueError("Incomplete evidence collection")
    (ROOT/"evidence"/"README.md").write_text(gallery())
    readme=ROOT/"README.md"
    text=readme.read_text()
    anchor="## Verified evidence — screenshots, animations and executable results\n"
    addition="\n**[Browse the permanent evidence gallery: original FireRed screenshots, GIFs and SHA-256 manifests](evidence/README.md)**\n"
    if text.count(anchor)!=1:raise ValueError("README anchor changed")
    if addition not in text:text=text.replace(anchor,anchor+addition,1)
    readme.write_text(text)
    print("PASS_XGBA_PERMANENT_EVIDENCE_ARCHIVE",count,"source files")
if __name__=="__main__":main()
