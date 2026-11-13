#!/usr/bin/env python3
"""Independent golden Smol-decoder check with no copyrighted asset in XGBA.

Download one publicly published Heart & Soul v2.0.6 *test fixture*
from pinned PokeDaisy commit. Verify Git's byte-exact blob SHA before use.
This only runs inside GitHub CI (network); no source binary, PNG or
copyrighted asset is saved in XGBA source/artifacts. Test exact decoded
288-byte output SHA-1 previously checked against an independent port.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
import sys
from urllib.request import urlopen

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/"tools"))
import xgba_r53_smol as smol

UPSTREAM="https://raw.githubusercontent.com/lidor30/pokedaisy/0040e61fcb129d7313e3941771572c93d6722816/app/src/test/kotlin/com/pokedaisy/app/companion/data/SmolTest.kt"
GIT_BLOB_SHA="1930cb31eb6fe2f55f8013b83f675911dfe7c200"
GOLDEN_SHA1="aad01e66e3584419de4dd0861877b3cade39268e"

def verify_public_witness():
    with urlopen(UPSTREAM,timeout=20) as response:
        source=response.read(16384)
    digest=hashlib.sha1(f"blob {len(source)}\0".encode()+source).hexdigest()
    if digest!=GIT_BLOB_SHA:
        raise AssertionError("Pinned independent source witness changed")
    s=source.decode("utf-8")
    marked=s.split("private val potion = hex(",1)[1].split("\n    )",1)[0]
    words=re.findall(r'"([0-9a-f]{16,})"',marked)
    if not words:
        raise AssertionError("Pinned HnS compressed witness missing")
    data=bytes.fromhex("".join(words))
    if data[0]&15!=3:
        raise AssertionError("Original source compression mode changed")
    decoded=smol.decode(data)
    if len(decoded)!=288 or hashlib.sha1(decoded).hexdigest()!=GOLDEN_SHA1:
        raise AssertionError("R53 Smol disagrees with independent original game graphics")
    return {"status":"PASS_R53_HEART_SOUL_REAL_SMOL_GOLDEN",
            "source":"pinned-public-independently-decoded-HnS-v2.0.6-fixture",
            "compression_mode":3,"decoded_bytes":288,
            "original_rom_data_committed":False}

if __name__=="__main__":
    import json
    print(json.dumps(verify_public_witness(),sort_keys=True))
