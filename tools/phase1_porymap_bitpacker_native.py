#!/usr/bin/env python3
"""Execute unchanged pinned Porymap BitPacker under native Qt6 UBSan; source/host only."""
import argparse, copy, hashlib, json, os, pathlib, re, shlex, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]
CPP_SHA = "34f86b4e3910021613a1d090746ae53a1c6782a2"
HDR_SHA = "4e3767e48449a974bfe1d9c63c5bf63dd2826fe9"
def git_blob(b):
    return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
def verify_source(cpp, header):
    assert git_blob(cpp) == CPP_SHA and git_blob(header) == HDR_SHA
    for needle in (b"m_setBits.append(1 << i);", b"(1 << m_setBits.length()) - 1", b"value |= (1 << i);", b"return (m_maxValue == UINT_MAX)", b"uint32_t BitPacker::pack"):
        assert needle in cpp
    assert b"class BitPacker" in header and b"uint32_t unpack(uint32_t data) const;" in header
def reject_source(cpp, hdr):
    try: verify_source(cpp, hdr)
    except (AssertionError, KeyError): return
    raise AssertionError("source mutation accepted")
DEPS = {
    "src/core/metatile.cpp": ("00fff2ba4bd1f3d85c7be3356fa6bf0bb0d8fc70", b"packer.setMask(behaviorMask);"),
    "src/core/block.cpp": ("fc4fe774ccd75673c549734055907eb7c79c0fc2", b"bitsMetatileId.setMask(projectConfig.blockMetatileIdMask);"),
    "src/config.cpp": ("9264f99bb18e0a725ef023f514c00df529d1d28d", b"this->metatileBehaviorMask = getConfigUint32(key, value);"),
    "include/config.h": ("539c5f3d416d22d847020cd324726b33725e5437", b"uint32_t metatileBehaviorMask;"),
    "src/ui/projectsettingseditor.cpp": ("0df96149b86694d5c95e1489493b91d646b99b98", b"projectConfig.metatileBehaviorMask = ui->spinBox_BehaviorMask->value();"),
}
def verify_dependency(raw, sha, anchor):
    assert git_blob(raw) == sha and anchor in raw
def reject_dependency(raw, sha, anchor):
    try: verify_dependency(raw, sha, anchor)
    except AssertionError: return
    raise AssertionError("source dependency mutation accepted")
def validate_evidence(e):
    assert e["source_cpp_sha"] == CPP_SHA and e["source_header_sha"] == HDR_SHA
    assert e["compiler"] == "g++" and e["sanitizer"] == "undefined,signed-integer-overflow"
    assert e["source_dependencies"] == {path: sha for path, (sha, _) in DEPS.items()}
    assert sorted(e["cases"]) == ["allbits","highbit","small","width31"]
    for mode in ("small","highbit","allbits"):
        case=e["cases"][mode]
        assert case["returncode"] == 0
        assert "BITPACKER_POSITIVE_" in case["stdout"]
        assert "runtime error" not in case["stderr"]
    bad=e["cases"]["width31"]
    assert bad["returncode"] != 0
    assert "bitpacker.cpp:21" in bad["stderr"]
    assert "signed integer overflow" in bad["stderr"]
    assert bad["stdout"] == ""
    assert e["independent_approvals"] == 0 and e["gate"] == "FAIL_INCOMPLETE"
def reject_evidence(e):
    try: validate_evidence(e)
    except (AssertionError, KeyError, TypeError): return
    raise AssertionError("forged UBSan evidence accepted")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--porymap",required=True)
    ap.add_argument("--output",required=True)
    args=ap.parse_args()
    upstream=pathlib.Path(args.porymap)
    cpp=(upstream/"src/core/bitpacker.cpp").read_bytes()
    hdr=(upstream/"include/core/bitpacker.h").read_bytes()
    verify_source(cpp,hdr)
    source_negatives=0
    dependency_shas={}
    for path,(sha,anchor) in DEPS.items():
        raw=(upstream/path).read_bytes()
        verify_dependency(raw,sha,anchor)
        dependency_shas[path]=sha
        changed=raw.replace(anchor,b"XGBA_DEPENDENCY_NEGATIVE",1)
        assert changed != raw
        reject_dependency(changed,sha,anchor)
        source_negatives+=1
    for needle in (b"m_setBits.append(1 << i);",b"(1 << m_setBits.length()) - 1",b"value |= (1 << i);",b"return (m_maxValue == UINT_MAX)",b"uint32_t BitPacker::pack"):
        mutated=cpp.replace(needle,b"XGBA_SOURCE_NEGATIVE",1)
        assert mutated!=cpp
        reject_source(mutated,hdr);source_negatives+=1
    reject_source(cpp,hdr.replace(b"class BitPacker",b"class FakePacker",1));source_negatives+=1
    out=pathlib.Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    binary=out.parent/"bitpacker-native-ubsan"
    flags=shlex.split(subprocess.check_output(["pkg-config","--cflags","--libs","Qt6Core"],text=True).strip())
    cmd=["g++","-std=c++17","-O0","-g","-fPIC","-fsanitize=undefined,signed-integer-overflow","-fno-sanitize-recover=all","-I"+str(upstream/"include/core"),str(ROOT/"tests/phase1_porymap_bitpacker_native.cpp"),str(upstream/"src/core/bitpacker.cpp"),"-o",str(binary),*flags]
    subprocess.run(cmd,check=True)
    evidence={"source_cpp_sha":CPP_SHA,"source_header_sha":HDR_SHA,"compiler":"g++","sanitizer":"undefined,signed-integer-overflow","gate":"FAIL_INCOMPLETE","independent_approvals":0,"source_dependencies":dependency_shas,"cases":{}}
    for mode in ("small","highbit","allbits","width31"):
        run=subprocess.run([str(binary),mode],capture_output=True,text=True,env={**os.environ,"UBSAN_OPTIONS":"halt_on_error=1:print_stacktrace=1"},timeout=30)
        evidence["cases"][mode]={"returncode":run.returncode,"stdout":run.stdout,"stderr":run.stderr}
    validate_evidence(evidence)
    negatives=0
    for mode in ("small","highbit","allbits"):
        bad=copy.deepcopy(evidence);bad["cases"][mode]["returncode"]=17
        reject_evidence(bad);negatives+=1
    for field,value in (("returncode",0),("stderr",""),("stdout","BITPACKER_WIDTH31_MAX=2147483647")):
        bad=copy.deepcopy(evidence);bad["cases"]["width31"][field]=value
        reject_evidence(bad);negatives+=1
    for field,value in (("source_cpp_sha","0"*40),("source_header_sha","0"*40),("compiler","fake"),("sanitizer","none"),("gate","PASS"),("independent_approvals",1)):
        bad=copy.deepcopy(evidence);bad[field]=value
        reject_evidence(bad);negatives+=1
    bad=copy.deepcopy(evidence);bad["source_dependencies"]["src/config.cpp"]="0"*40
    reject_evidence(bad);negatives+=1
    assert source_negatives==11 and negatives==13
    evidence["source_negatives"]=source_negatives
    evidence["evidence_negatives"]=negatives
    out.write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8")
    print("BITPACKER_NATIVE_UBSAN_PASS positives=3 width31_overflow=1 source_negatives=11 evidence_negatives=13 approvals=0 gate=FAIL_INCOMPLETE")
if __name__=="__main__":
    main()
