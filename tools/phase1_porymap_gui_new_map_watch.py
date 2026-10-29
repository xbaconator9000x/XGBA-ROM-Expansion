#!/usr/bin/env python3
"""Fail-closed verifier for original Porymap MainWindow native GUI new-map experiment."""
import argparse,hashlib,json,subprocess
from pathlib import Path
PIN_P="26b919d7ff4b54152de010abd5bf344af2ebe116"
PIN_F="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={"src/mainwindow.cpp":"08ce1a7a599ef825967717b69626984cdc6d772b",
"src/project.cpp":"d43b0949303433111d4478ad76117c2b3445dd13",
"src/ui/newmapdialog.cpp":"c8a028025bf1a9aabb8fd96cccf3d0a76214bb0e"}
TRUE=("original_mainwindow_qaction","original_newmapdialog_accept","new_map_unpersisted_until_save",
"matched_qfile_enospc","gui_false_clean_missing_script_on_retry","watch_missing_before_save",
"watch_not_auto_rearmed_after_save","manual_watch_recovery","native_qt6","synthetic_new_map","file_changed_signal_tested")
FALSE=("stock_gameplay",)
def need(ok,msg):
    if not ok: raise ValueError(msg)
def git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()
def verify(log):
    need("FAIL " not in log,"native failure")
    lines=[x.split("=",1)[1] for x in log.splitlines() if x.startswith("PHASE1_GUI_NEWMAP=")]
    need(len(lines)==1,"exactly one GUI evidence line")
    o=json.loads(lines[0])
    need(set(o)==set(TRUE)|set(FALSE)|{"phase1_gate","independent_approvals"},"evidence field set")
    need(all(o[x] is True for x in TRUE),"native positive assertion")
    need(all(o[x] is False for x in FALSE),"negative scope")
    need(o["phase1_gate"]=="FAIL_INCOMPLETE" and o["independent_approvals"]==0,"gate/approvals")
    return o
def negatives(log):
    base=verify(log); n=0
    for key in list(TRUE)+list(FALSE)+["phase1_gate","independent_approvals"]:
        changed=dict(base)
        changed[key]= (not base[key]) if isinstance(base[key],bool) else ("PASS" if key=="phase1_gate" else 1)
        marker="PHASE1_GUI_NEWMAP="+json.dumps(changed,separators=(",",":"))
        for line in log.splitlines():
            if line.startswith("PHASE1_GUI_NEWMAP="): break
        mutated=log.replace(line,marker,1)
        need(mutated!=log,"ineffective negative")
        try: verify(mutated)
        except ValueError: n+=1
        else: raise AssertionError("negative escaped "+key)
    return n
def main():
    p=argparse.ArgumentParser()
    for x in ("porymap","firered","log","output"):p.add_argument("--"+x,required=True,type=Path)
    a=p.parse_args()
    need(git(a.porymap,"rev-parse","HEAD")==PIN_P,"porymap pin")
    need(git(a.firered,"rev-parse","HEAD")==PIN_F,"firered pin")
    for path,sha in BLOBS.items():need(git(a.porymap,"hash-object",path)==sha,"source drift "+path)
    log=a.log.read_text()
    result=verify(log); n=negatives(log)
    out={"evidence_class":"NATIVE_ORIGINAL_MAINWINDOW_NEWMAP_QT",
         "porymap_pin":PIN_P,"firered_pin":PIN_F,"source_blobs":BLOBS,
         "native_transcript_sha256":hashlib.sha256(log.encode()).hexdigest(),
         "assertions":result,"transcript_mutations_rejected":n,
         "phase1_gate":"FAIL_INCOMPLETE","independent_approvals":0}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("PORYMAP_GUI_NEWMAP_NATIVE_PASS negatives=%d gate=FAIL_INCOMPLETE approvals=0"%n)
if __name__=="__main__":main()
