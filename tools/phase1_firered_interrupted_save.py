#!/usr/bin/env python3
"""Phase 1: actual third FireRed save interrupted in flight (not hardware power loss)."""
import argparse
import json
import os
import shutil
import struct
import subprocess
from pathlib import Path
from phase1_firered_game_controller import make_schedule
from phase1_firered_repeat_save import TRACE_NAMES, run, verify_game_written_slot, sha

def counter3_ids(flash):
    ids=[]
    for physical in range(14,28):
        sector=flash[physical*4096:(physical+1)*4096]
        ident,chk,sig,ctr=struct.unpack_from("<HHII",sector,0xFF4)
        if ident>=14 or sig!=0x08012025 or ctr!=3:
            continue
        total=sum(struct.unpack_from("<992I",sector))&0xFFFFFFFF
        if chk==(((total>>16)+total)&0xFFFF):
            ids.append(ident)
    assert len(ids)==len(set(ids)),("duplicate counter3 IDs",ids)
    return ids

def main(a):
    root=Path(a.output)
    previous=root/"second_game_save.sav"
    proof=json.loads((root/"second_game_save.json").read_text())
    assert proof["native"]["first_try_saving_data_return_value"]==1
    assert proof["native"]["save_counter"]==2
    original=previous.read_bytes()
    verify_game_written_slot(original,0,2)
    verify_game_written_slot(original,1,1)
    schedule=root/"third_save_interrupt.keys"
    schedule.write_text("".join(f"{f} {k:03x}\n" for f,k in make_schedule("pallet_save_dense_confirm")))
    args=[a.probe,a.rom,str(previous),str(schedule),"3200",
          a.status,a.counter,a.sb2]+[getattr(a,k) for k in TRACE_NAMES]
    env=os.environ.copy()
    env["XGBA_PHASE1_CUT_COUNTER3_AFTER"]="14"
    negative=subprocess.run(args,env=env,capture_output=True,text=True,timeout=60)
    assert negative.returncode!=0 and "invalid in-flight cut threshold" in negative.stderr, (
        "Invalid cut did not fail closed",negative.returncode,negative.stderr[-300:])
    records=[]
    for threshold in (1,7,13):
        sav=root/f"cut_counter3_{threshold}.sav"
        shutil.copyfile(previous,sav)
        env["XGBA_PHASE1_CUT_COUNTER3_AFTER"]=str(threshold)
        cmd=args[:2]+[str(sav)]+args[3:]
        proc=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=900)
        assert proc.returncode==86,(threshold,proc.returncode,proc.stderr[-500:],proc.stdout[-500:])
        lines=[json.loads(x) for x in proc.stdout.splitlines()
               if x.startswith('{"mode":"interrupted_save"')]
        assert len(lines)==1,(threshold,proc.stdout[-500:])
        event=lines[0]
        assert event["cut_threshold"]==threshold
        assert threshold<=event["valid_counter3_sectors"]<14
        assert event["try_save_entries"]>=1 and event["try_save_returns"]==0
        assert event["counter"]==3 and event["no_host_writes"] and event["no_graceful_close"]
        interrupted=sav.read_bytes()
        assert len(interrupted)==131072 and interrupted!=original
        assert interrupted[:14*4096]==original[:14*4096], "Older counter2 slot modified"
        verify_game_written_slot(interrupted,0,2)
        ids=counter3_ids(interrupted)
        assert len(ids)==event["valid_counter3_sectors"], (
            "Physical .sav disagrees with in-flight Flash",threshold,ids,event)
        cold=root/f"cut_counter3_{threshold}_coldboot.sav"
        shutil.copyfile(sav,cold)
        result=run(a,f"cut_counter3_{threshold}_coldboot",cold,"cold_boot",2400)
        n=result["native"]
        assert n["save_counter"]==2,("No older-slot recovery",threshold,n)
        assert (n["saveblock1_map_group"],n["saveblock1_map_num"],
                n["saveblock1_layout_id"])==(3,0,78)
        assert n["saveblock2_player_name_u32"]==0xFFBEBFCD
        assert n["field_get_player_input_hits"]>0
        assert n["try_saving_data_entry_hits"]==0 and n["flash_changed_bytes"]==0
        assert not result["physical_save_changed"]
        record={"threshold":threshold,"cut":event,"persisted_counter3_ids":ids,
                "recovered_counter":n["save_counter"],"recovered_status":n["save_status"],
                "field_input_hits":n["field_get_player_input_hits"],
                "physical_save_sha256":sha(sav),"host_flash_writes":0,
                "physical_power_cut_proven":False,"phase1_gate":"FAIL_INCOMPLETE",
                "independent_approval":False}
        (root/f"cut_counter3_{threshold}.json").write_text(
            json.dumps(record,indent=2,sort_keys=True)+"\n")
        print(json.dumps({"threshold":threshold,"new_sectors":len(ids),
                          "recovered_counter":n["save_counter"],
                          "field_input_hits":n["field_get_player_input_hits"]}),flush=True)
        records.append(record)
    summary={"cases":records,"invalid_threshold_rejected":True,
             "game_save_interrupted_before_return":True,
             "physical_power_cut_proven":False,"independent_approval":False,
             "phase1_gate":"FAIL_INCOMPLETE"}
    (root/"inflight_interrupt_summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,sort_keys=True),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("rom","probe","status","counter","sb2","output"):
        p.add_argument("--"+k,required=True)
    for k in TRACE_NAMES:
        p.add_argument("--"+k.replace("_","-"),required=True)
    main(p.parse_args())
