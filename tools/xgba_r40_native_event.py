"""R40 original Emerald event-script fixture builder.

The nine bytes are original *test-authored* command data for the pinned Emerald
interpreter. They never contain or imply extracted code from the user's ROM.
Private actual game script compatibility remains a separate three-ROM test.
"""
from __future__ import annotations
import hashlib
import struct

RESOURCE_ID="emerald.r40.script"
VAR_ID=0x40FE      # pinned original Emerald unused saveblock variable
FLAG_ID=0x08F0    # pinned original Emerald unused system flag
VALUE=0x5A39
RESOURCE_SIZE=9
SCRIPT_OFFSET=32*1024*1024+524288


def script_bytes():
    payload=(bytes([0x16])+struct.pack("<HH",VAR_ID,VALUE)
             +bytes([0x29])+struct.pack("<H",FLAG_ID)+bytes([0x02]))
    if len(payload)!=RESOURCE_SIZE:
        raise ValueError("Script fixture length drift")
    return payload


def audit_script(data):
    """Reject any non-fixture opcode/operand before enabling native execution."""
    if type(data) is not bytes or data!=script_bytes():
        raise ValueError("R40 only supports the bounded test-authored script")
    return {"id":RESOURCE_ID,"length":len(data),
            "sha256":hashlib.sha256(data).hexdigest(),
            "uses_original_native_emerald_script_interpreter":True,
            "private_game_script_executed":False,
            "script_origin":"authored_synthetic_fixture"}
