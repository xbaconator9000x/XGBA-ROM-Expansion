#!/usr/bin/env python3
"""Fail-closed native mGBA regression EVIDENCE gate; NOT an XGBA runtime certification."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PIN="fd9dc5c2cbf234365068855851107e762fc6211b"
REQUIRED_TESTS=frozenset("""
vanilla_non_M_does_not_select_matrix
vanilla_ARM_fetch_data_consistency
vanilla_Thumb_fetch_data_consistency
native_ROM2_EX_without_EEPROM_reads_ROM
native_ROM2_EX_16bit_EEPROM_overrides_ROM
native_ROM2_EX_32bit_EEPROM_not_16bit_override
native_ROM2_EX_eReader_register_overrides_ROM
native_EEPROM_priority_over_eReader_on_16bit_ROM2_EX
native_DMA3_16bit_ROM2_EX_reads_EEPROM
native_DMA3_immediate_one_unit_completes
matrix_M_signature_and_16MiB_aperture
matrix_bank_A_ARM_fetch_data
matrix_bank_B_ARM_fetch_data_after_refetch
matrix_bank_A_Thumb_fetch_data
matrix_bank_B_Thumb_fetch_data
matrix_reset_does_not_preserve_alternate_bank
matrix_savestate_16slot_metadata_roundtrip
matrix_savestate_reloads_ARM_physical_bank
matrix_savestate_reloads_Thumb_physical_bank
matrix_pre_full_state_mutation_bank_A
matrix_full_emulator_state_deserialize_success
matrix_full_state_restores_ARM_bank_B
matrix_full_state_restores_Thumb_bank_B
native_savestate_rejects_changed_game_code
native_savestate_rejects_changed_game_title
native_savestate_restores_original_backing_after_fixture_mutation
native_matrix_rejects_outside_8KiB_window
native_matrix_rejects_zero_size
native_oversize_nonM_keeps_32MiB_visible_aperture
native_oversize_nonM_keeps_full_VFile_backing_length
native_oversize_nonM_does_not_activate_Matrix
native_oversize_nonM_ARM_visible_bytes
native_oversize_nonM_ROM_end_access
native_oversize_nonM_has_no_extra_CPU_address_window
""".split())
REQUIRED_NATIVE_GAPS=frozenset("""
native_remap_leaves_prefetch_stale_until_refetch=true
native_savestate_CRC_mismatch_only_warns=true
native_savestate_external_bank_payload_change_unverified=true
native_matrix_accepts_physical_range_past_end=true
""".split())

class EvidenceRejected(RuntimeError):
    pass

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def extract(log:str,marker:str)->list[str]:
    return re.findall(r"^"+re.escape(marker)+r" ([^\r\n]+)$",log,re.M)

def check(log:str,record:dict,source_bytes:bytes)->dict:
    if not isinstance(record,dict):
        raise EvidenceRejected("Missing machine-readable summary")
    if record.get("source_revision")!=PIN:
        raise EvidenceRejected("Pinned mGBA revision mismatch")
    if record.get("test_source_sha256")!=sha(source_bytes):
        raise EvidenceRejected("Test fixture source differs from executed SHA-256")
    if record.get("run_kind")!="NATIVE_MGBA_SYNTHETIC_CARTRIDGE_ONLY":
        raise EvidenceRejected("Wrong runtime context")
    if record.get("native_probe_exit_code")!=0:
        raise EvidenceRejected("Native test exited nonzero")
    if record.get("external_XGBA_banking_implemented") is not False:
        raise EvidenceRejected("Test is not an XGBA implementation")
    if record.get("phase1_mapping_complete") is not False:
        raise EvidenceRejected("Unsupported Phase 1 pass claim")
    if record.get("independent_semantic_reviews_approved")!=0:
        raise EvidenceRejected("Unsubstantiated semantic review approvals")
    passed=extract(log,"PASS")
    failed=extract(log,"FAIL")
    gaps=extract(log,"OBSERVATION")
    if failed:raise EvidenceRejected("Native test has failed assertions")
    if len(set(passed))!=len(passed):raise EvidenceRejected("Duplicate PASS assertion name")
    if len(set(gaps))!=len(gaps):raise EvidenceRejected("Duplicate observation name")
    missing=REQUIRED_TESTS-set(passed)
    if missing:raise EvidenceRejected("Required assertions missing: "+",".join(sorted(missing)))
    if set(gaps)!=REQUIRED_NATIVE_GAPS:
        raise EvidenceRejected("Native hazard observations changed: "+str(sorted(set(gaps)^REQUIRED_NATIVE_GAPS)))
    if (record.get("positive_checks_passed")!=len(passed)
        or record.get("positive_checks_failed")!=0):
        raise EvidenceRejected("Runtime counts differ from saved result metadata")
    if record.get("native_gap_observations")!=gaps:
        raise EvidenceRejected("Runtime observations differ from saved result metadata")
    if "SUMMARY hard_failures=0 native_gap_observations=4 " not in log:
        raise EvidenceRejected("Missing native executable termination summary")
    return {
        "decision":"PASS_PINNED_NATIVE_MGBA_REGRESSION_ONLY",
        "source_revision":PIN,
        "test_source_sha256":sha(source_bytes),
        "runtime_stdout_sha256":sha(log.encode()),
        "assertions_verified":len(passed),
        "required_assertions_preserved":len(REQUIRED_TESTS),
        "native_gap_observations":gaps,
        "native_XGBA_runtime_verified":False,
        "independent_semantic_dispositions_approved":0,
        "phase1_mapping_complete":False,
        "notice":"Native source-pinned behavior only; 4 hazardous native behaviors remain XGBA design obligations."
    }

def self_test()->None:
    source=b"pinned-fixture-for-unit-test"
    passed="\n".join("PASS "+name for name in sorted(REQUIRED_TESTS))
    obs="\n".join("OBSERVATION "+name for name in sorted(REQUIRED_NATIVE_GAPS))
    # Sort order is persisted in metadata; actual runner uses chronological order.
    data=passed+"\n"+obs+"\nSUMMARY hard_failures=0 native_gap_observations=4 xgba_runtime_implemented=false phase1_mapping_complete=false\n"
    rec={"source_revision":PIN,"test_source_sha256":sha(source),
         "run_kind":"NATIVE_MGBA_SYNTHETIC_CARTRIDGE_ONLY",
         "native_probe_exit_code":0,"external_XGBA_banking_implemented":False,
         "phase1_mapping_complete":False,"independent_semantic_reviews_approved":0,
         "positive_checks_passed":len(REQUIRED_TESTS),"positive_checks_failed":0,
         "native_gap_observations":sorted(REQUIRED_NATIVE_GAPS)}
    assert check(data,rec,source)["assertions_verified"]==34
    negatives=[
        (data.replace("PASS "+sorted(REQUIRED_TESTS)[0]+"\n",""),rec,source),
        ("PASS duplicate\n"+data.replace("PASS duplicate\n",""),{**rec,"positive_checks_passed":35},source),
        ("FAIL injected\n"+data,rec,source),
        (data.replace("OBSERVATION "+sorted(REQUIRED_NATIVE_GAPS)[0],
                      "OBSERVATION "+sorted(REQUIRED_NATIVE_GAPS)[0].replace("=true","=false")),rec,source),
        (data,{**rec,"test_source_sha256":"0"*64},source),
        (data,{**rec,"source_revision":"wrong"},source),
        (data,{**rec,"native_probe_exit_code":139},source),
        (data,{**rec,"positive_checks_passed":33},source),
        (data,{**rec,"phase1_mapping_complete":True},source),
        (data,{**rec,"native_gap_observations":[]},source),
    ]
    for i,(logs,record,blob) in enumerate(negatives,1):
        try:check(logs,record,blob)
        except EvidenceRejected:continue
        raise AssertionError("Fail-open negative fixture "+str(i))
    print("Native mGBA evidence gate: 1 positive +",len(negatives),"negative controls PASS")

def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--log",type=Path,default=Path("compiler-evidence/mgba-boundary-runtime.log"))
    parser.add_argument("--summary",type=Path,default=Path("compiler-evidence/mgba-native-boundary-result.json"))
    parser.add_argument("--source",type=Path,default=Path("tests/mgba_bank_boundary.c"))
    parser.add_argument("--out",type=Path,default=Path("compiler-evidence/mgba-native-regression-gate.json"))
    args=parser.parse_args()
    if args.self_test:
        self_test()
        return
    try:
        log=args.log.read_text(encoding="utf-8")
        record=json.loads(args.summary.read_text(encoding="utf-8"))
        result=check(log,record,args.source.read_bytes())
    except (OSError,ValueError,EvidenceRejected) as ex:
        result={"decision":"FAIL_CLOSED","error":str(ex),
                "native_XGBA_runtime_verified":False,
                "phase1_mapping_complete":False}
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        print("Evidence gate rejected:",ex,file=sys.stderr)
        sys.exit(2)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
