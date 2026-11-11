#!/usr/bin/env python3
"""Preserve selected byte-identical native screenshots and report summaries from verified CI."""
import hashlib, io, json, os, struct, time, zipfile
from pathlib import Path
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from urllib.parse import urlsplit

class DropAuthOnCrossHostRedirect(HTTPRedirectHandler):
    # GitHub artifacts redirect to separately signed Azure object-store URLs.
    # Never forward the GitHub Actions Bearer token to that destination.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected and urlsplit(newurl).hostname != urlsplit(req.full_url).hostname:
            redirected.remove_header("Authorization")
        return redirected

SAFE_OPENER = build_opener(DropAuthOnCrossHostRedirect())

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
 "r15":(42987149871,13840560384,"f5ea62128463272089d66cd2ca13e807b14095ad",60,
  "01-house-before-save.png 02-house-after-flash-save.png 03-cold-boot-house-reloaded.png 04-after-cold-boot-pallet.png proof.json".split()),
 "r16":(42990445836,13840644779,"b182dfa07a45673630c13d234b64a0e3d8e26a66",62,
  "emerald-boot-enabled.png emerald-boot-disabled.png proof.json".split()),
 "r17":(42993487976,13842542465,"1dcb7427edec36110cc894097ea745802b516f72",64,
  "01-littleroot-real-external-map.png 02-littleroot-after-real-dpad.png proof.json".split()),
 "r18":(42995836013,13844226288,"261442f961c9121752f944b0c9fedbfb2999bd7a",65,
  "01-original-emerald-before-flash.png 02-original-emerald-after-flash-write.png 03-cold-emerald-reacquired-littleroot.png proof.json".split()),
 "r19-maps":(43006516293,13848312867,"4e34eb6ea02819e77b5ace2b6113ac2a8fc7360a",67,
  "01-original-littleroot-two-maps-loaded.png 02-real-route101-external-crossing.png 03-return-littleroot-live-packs.png proof.json".split()),
 "r19-battle":(43006516094,13847903781,"4e34eb6ea02819e77b5ace2b6113ac2a8fc7360a",67,
  "01-native-emerald-before-mixed-battle.png 02-original-emerald-local-plus-two-external-opponents.png proof.json".split()),
}
def sha(b): return hashlib.sha256(b).hexdigest()
def fetch(url,token,maxlen):
    for attempt in range(3):
        req=Request("https://api.github.com"+url,headers={"Authorization":"Bearer "+token,
          "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
          "User-Agent":"xgba-verified-evidence"})
        try:
            with SAFE_OPENER.open(req,timeout=90) as response:data=response.read(maxlen+1)
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
        for k in ("native_log","native_logs","native_execution_log","emulator_logs",
                  "native_write_log","native_resume_log","native_corrupt_log"):
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
       "## R19 — original Emerald connected maps and mixed-storage Pokémon battles","",
       "Both native integration suites passed 6/6 tests each at the same commit:",
       "two complete original Emerald maps and secondary tilesets physically traversed,",
       "and a genuine double wild battle using vanilla-ROM Treecko/Torchic plus",
       "Poochyena/Zigzagoon front sprites from different external addresses.",
       "The source-built game, not the host, executed the graphics decompression.",
       "All five original Emerald LCD frames below preserve their CI bytes.",
       "",
       "### Real connected maps: Littleroot Town ↔ Route 101","",
       row(["Littleroot native external","Route 101 native external","Returned to Littleroot"]),
       row(["---"]*3),
       row([thumb("r19-maps","01-original-littleroot-two-maps-loaded.png","Littleroot with both packs resident"),
            thumb("r19-maps","02-real-route101-external-crossing.png","Route 101 via D-pad"),
            thumb("r19-maps","03-return-littleroot-live-packs.png","Returned with live packs")]),
       "",
       "[R19 maps exact-head native CI 6/6](https://github.com/"+REPO+"/actions/runs/43006516293) · "
       "[SHA provenance](verified/r19-maps/provenance.json) · [proof](verified/r19-maps/proof.json)",
       "",
       "### Real mixed-source Emerald double wild battle","",
       row(["Original external-map overworld","Original Emerald battle with ROM + external sprites"]),
       row(["---","---"]),
       row([thumb("r19-battle","01-native-emerald-before-mixed-battle.png","Before battle"),
            thumb("r19-battle","02-original-emerald-local-plus-two-external-opponents.png","ROM player and external opponents")]),
       "",
       "[R19 battle exact-head native CI 6/6](https://github.com/"+REPO+"/actions/runs/43006516094) · "
       "[SHA provenance](verified/r19-battle/provenance.json) · [proof](verified/r19-battle/proof.json) · "
       "[implementation draft PR #67](https://github.com/"+REPO+"/pull/67)",
       "",
       "**Limits:** battle graphics are original front/back sprites: external move",
       "animations, arbitrary multi-file sidecars, trillion-byte logical storage",
       "offsets, production UI and original hardware are not yet verified.",
       "",
       "## R18 — original Emerald Flash save, cold continuation and reloaded external map","",
       "The pinned source-built original Emerald saved to genuine Flash, exited mGBA,",
       "and a fresh process continued from the real save in externally backed Littleroot.",
       "A third process verified corrupt-resource refusal without altering the good save.",
       "Five exact-head native tests passed, including original CPU/EWRAM/BG VRAM checks.",
       "",
       row(["Original Emerald before Flash save","After Flash sector write","Cold-reloaded Littleroot"]),
       row(["---","---","---"]),
       row([thumb("r18","01-original-emerald-before-flash.png","Before original Flash save"),
            thumb("r18","02-original-emerald-after-flash-write.png","After Flash write"),
            thumb("r18","03-cold-emerald-reacquired-littleroot.png","Cold resumed Littleroot Town")]),
       "",
       "[R18 native CI 5/5](https://github.com/"+REPO+"/actions/runs/42995836013) · "
       "[source PR #65](https://github.com/"+REPO+"/pull/65) · "
       "[SHA-verified provenance](verified/r18/provenance.json) · [proof](verified/r18/proof.json)",
       "",
       "**Limits:** actual Emerald Flash was invoked by a test-only SELECT shortcut; this",
       "does not yet demonstrate the graphical Start→Save menu, arbitrary maps,",
       "battle assets, stock mGBA or a production-friendly pack-mismatch UI.",
       "",
       "## R17 — real Emerald Littleroot map and complete secondary tileset from external storage","",
       "The actual source-built Emerald game had its native Littleroot map grid and border,",
       "Petalburg secondary graphics/palettes/metatiles/attributes stripped from the ROM.",
       "The engine fetched the original bytes from beyond 32 MiB, verified its map grid",
       "and native background VRAM, and moved the player by physical D-pad input.",
       "Six genuine native acceptance tests passed at exact head, also independently in PR CI.",
       "",
       row(["Original Emerald with external Littleroot map","Same native game after real D-pad"]),
       row(["---","---"]),
       row([thumb("r17","01-littleroot-real-external-map.png","Littleroot using external map"),
            thumb("r17","02-littleroot-after-real-dpad.png","After physical player movement")]),
       "",
       "[Passing R17 native push CI 6/6](https://github.com/"+REPO+"/actions/runs/42993487976) · "
       "[matching exact-head PR CI](https://github.com/"+REPO+"/actions/runs/42993559059) · "
       "[source PR #64](https://github.com/"+REPO+"/pull/64) · "
       "[SHA-verified provenance](verified/r17/provenance.json) · [proof](verified/r17/proof.json)",
       "",
       "**Limits:** this is one original Emerald external town map and its secondary tileset,",
       "with test-only title/truck-sequence bypass. General map transitions and Emerald",
       "Flash save/cold restart are not part of R17.",
       "",
       "## R16 — original Pokémon Emerald decomp executes XGBA's existing native provider","",
       "Pinned source-built pokeemerald (MODERN=1) issues the same XGBA MMIO resource request",
       "used by FireRed, receives and verifies bytes in the physical GBA's EWRAM, and",
       "continues executing its original game loop. Disabled mode made zero external reads.",
       "This proves engine/guest-ABI portability, **not** Emerald external map, save or battle support.",
       "",
       row(["Emerald with sidecar enabled","Same Emerald ROM, extension disabled"]),
       row(["---"]*2),
       row([thumb("r16","emerald-boot-enabled.png","Emerald guest XGBA enabled"),
            thumb("r16","emerald-boot-disabled.png","Emerald guest XGBA disabled")]),
       "",
       "[R16 exact-head native CI 5/5](https://github.com/"+REPO+"/actions/runs/42990445836) · "
       "[R16 source PR #62](https://github.com/"+REPO+"/pull/62) · "
       "[Provenance](verified/r16/provenance.json) · "
       "[Compact proof](verified/r16/proof.json)",
       "",
       "## R15 — original FireRed Flash save, cold reboot, and reloaded external house","",
       "These are four genuine 240×160 screenshots from two separate native mGBA processes.",
       "FireRed wrote its own Flash sectors, mGBA exited, and a fresh process loaded the saved game.",
       "A third independent process proved corruption refusal without modifying the valid save.",
       "",
       row(["House before save","After original Flash write","Identical house after cold restart","Return to Pallet"]),
       row(["---"]*4),
       row([thumb("r15",f,n) for f,n in [
         ("01-house-before-save.png","Before saving"),
         ("02-house-after-flash-save.png","Saved in FireRed"),
         ("03-cold-boot-house-reloaded.png","Cold boot identical house"),
         ("04-after-cold-boot-pallet.png","Returned to Pallet")]]),
       "",
       "**The original house-before-save and cold-boot screenshots have identical SHA-256 pixel-file bytes.**",
       "[Passing R15 native CI, 4/4](https://github.com/"+REPO+"/actions/runs/42987149871) · "
       "[R15 exact-head source PR #60](https://github.com/"+REPO+"/pull/60) · "
       "[Provenance](verified/r15/provenance.json) · [Compact proof](verified/r15/proof.json)",
       "",
       "Scope: this is the original FireRed Flash engine and cold-game-continue routine,",
       "not the visual Start → Save menu. The deliberately corrupted pack fails closed",
       "inside the bounded test fixture; a user-facing recovery screen remains future work.",
       "",
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
    if count<69:raise ValueError("Incomplete R9–R19 evidence collection")
    (ROOT/"evidence"/"README.md").write_text(gallery())
    readme=ROOT/"README.md"
    text=readme.read_text()
    anchor="## Verified evidence — screenshots, animations and executable results\n"
    addition="\n**[Browse the permanent evidence gallery: original FireRed and Emerald LCD screenshots, GIFs and SHA-256 manifests](evidence/README.md)**\n"
    if text.count(anchor)!=1:raise ValueError("README anchor changed")
    if addition not in text:text=text.replace(anchor,anchor+addition,1)
    readme.write_text(text)
    print("PASS_XGBA_PERMANENT_EVIDENCE_ARCHIVE",count,"source files")
if __name__=="__main__":main()
