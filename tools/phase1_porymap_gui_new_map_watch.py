#!/usr/bin/env python3
"""Fail-closed verifier for original Porymap MainWindow native GUI new-map experiment."""
import argparse,hashlib,json,subprocess
from pathlib import Path
PIN_P="26b919d7ff4b54152de010abd5bf344af2ebe116"
PIN_F="ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS={"src/mainwindow.cpp":"08ce1a7a599ef825967717b69626984cdc6d772b",
"src/project.cpp":"d43b0949303433111d4478ad76117c2b3445dd13",
"src/ui/newmapdialog.cpp":"c8a028025bf1a9aabb8fd96cccf3d0a76214bb0e",
"src/ui/message.cpp":"8dfe553c2794370b210ac09aebfc7c42c03a080b",
"src/log.cpp":"d2cde0a452c6bcb61d72e6ec669082d50d7ee283"}
TRUE=("original_mainwindow_qaction","original_newmapdialog_accept","new_map_unpersisted_until_save",
"matched_qfile_enospc","gui_false_clean_missing_script_on_retry","watch_missing_before_save",
"watch_not_auto_rearmed_after_save","manual_watch_recovery","native_qt6","synthetic_new_map",
"actual_modal_newmap_cancel_preserved_editor","actual_modal_newmap_accept_selected_map",
"atomic_replace_committed","atomic_replace_file_changed_signal",
"watcher_rearmed_after_atomic_replace","post_replace_file_changed_signal",
"permission_denied_first_save_rejected","permission_failure_preserved_unpersisted_editor_map",
"permission_test_unprivileged","permission_os_denial_eacces","permission_qfile_open_denied",
"save_error_dialog_reported","failed_commit_rejected","failed_commit_old_bytes_preserved",
"watcher_retained_after_failed_commit","post_failure_watch_signal","file_changed_signal_tested",
"permission_failure_injected")
FALSE=("stock_gameplay","human_modal_interaction","fsync_failure_injected",
       "physical_durability_tested")
COLD_TRUE=("fresh_process","original_mainwindow_project_reopened","new_map_reloaded",
           "map_json_valid","watcher_registered_on_reopen")
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
def verify_cold(log):
    rows=[x.split("=",1)[1] for x in log.splitlines()
          if x.startswith("PHASE1_GUI_NEWMAP_COLD=")]
    need(len(rows)==1,"exactly one cold-reopen evidence line")
    o=json.loads(rows[0])
    need(set(o)==set(COLD_TRUE)|{"phase1_gate","independent_approvals"},"cold evidence field set")
    need(all(o[x] is True for x in COLD_TRUE),"fresh-process reopen assertion")
    need(o["phase1_gate"]=="FAIL_INCOMPLETE" and o["independent_approvals"]==0,
         "cold gate/approvals")
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
def cold_negatives(log):
    base=verify_cold(log); n=0
    for key in list(COLD_TRUE)+["phase1_gate","independent_approvals"]:
        changed=dict(base)
        changed[key]=(not base[key]) if isinstance(base[key],bool) else (
            "PASS" if key=="phase1_gate" else 1)
        marker="PHASE1_GUI_NEWMAP_COLD="+json.dumps(changed,separators=(",",":"))
        line=next(x for x in log.splitlines() if x.startswith("PHASE1_GUI_NEWMAP_COLD="))
        mutated=log.replace(line,marker,1)
        need(mutated!=log,"ineffective cold negative")
        try: verify_cold(mutated)
        except ValueError: n+=1
        else: raise AssertionError("cold transcript mutation escaped "+key)
    return n
def main():
    p=argparse.ArgumentParser()
    for x in ("porymap","firered","log","cold-log","output"):
        p.add_argument("--"+x,required=True,type=Path)
    a=p.parse_args()
    need(git(a.porymap,"rev-parse","HEAD")==PIN_P,"porymap pin")
    need(git(a.firered,"rev-parse","HEAD")==PIN_F,"firered pin")
    for path,sha in BLOBS.items():need(git(a.porymap,"hash-object",path)==sha,"source drift "+path)
    log=a.log.read_text()
    result=verify(log); n=negatives(log)
    cold_log=a.cold_log.read_text()
    cold=verify_cold(cold_log); cold_n=cold_negatives(cold_log)
    out={"evidence_class":"NATIVE_ORIGINAL_MAINWINDOW_NEWMAP_QT",
         "porymap_pin":PIN_P,"firered_pin":PIN_F,"source_blobs":BLOBS,
         "native_transcript_sha256":hashlib.sha256(log.encode()).hexdigest(),
         "cold_reopen_transcript_sha256":hashlib.sha256(cold_log.encode()).hexdigest(),
         "assertions":result,"transcript_mutations_rejected":n,
         "cold_reopen_assertions":cold,"cold_transcript_mutations_rejected":cold_n,
         "phase1_gate":"FAIL_INCOMPLETE","independent_approvals":0}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print("PORYMAP_GUI_NEWMAP_NATIVE_PASS negatives=%d cold_negatives=%d gate=FAIL_INCOMPLETE approvals=0"%
          (n,cold_n))
if __name__=="__main__":main()
