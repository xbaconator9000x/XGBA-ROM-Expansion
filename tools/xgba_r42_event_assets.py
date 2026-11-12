"""R42 two independently addressed, original Emerald format EVENT assets.

These are test-authored compatibility translations of source concepts, not
original Team Rocket Edition or Heart & Soul binary script extraction.
ROM/Flash/game data and native guest EWRAM must never be committed.
"""
from __future__ import annotations
import hashlib
import struct

SCRIPT_SIZE=96
TEXT_OFFSET=22
ROCKET_ID="rocket.r42.event"
JOHTO_ID="heart_soul.r42.event"
ROCKET_OFFSET=32*1024*1024+655360
JOHTO_OFFSET=32*1024*1024+671744
ROCKET_VAR=0x40FD
JOHTO_VAR=0x40FC
ROCKET_FLAG=0x08F1
JOHTO_FLAG=0x08F2
ROCKET_VALUE=0x524B
JOHTO_VALUE=0x484E
ROCKET_ITEM=110   # original Emerald ITEM_NUGGET
JOHTO_ITEM=217    # original Emerald ITEM_SILK_SCARF

# Original Emerald charmap A=0xBB .. Z=0xD4, 0x00 space, 0xAB !, 0xFF end.
ALPHABET={chr(65+i):0xBB+i for i in range(26)}
ALPHABET.update({" ":0x00,"!":0xAB,".":0xAD,"?":0xAC})


def text_bytes(message):
    if type(message) is not str or not 1<=len(message)<=60:
        raise ValueError("R42 message length")
    try:
        return bytes(ALPHABET[char] for char in message.upper())+b"\xff"
    except KeyError as exc:
        raise ValueError("R42 unsupported original Emerald text glyph") from exc


def event_bytes(var, value, flag, item, message):
    body=(bytes([0x16])+struct.pack("<HH",var,value)
          +bytes([0x29])+struct.pack("<H",flag)
          +bytes([0x44])+struct.pack("<HH",item,1)
          +bytes([0x0F,0])+b"\0\0\0\0"
          +bytes([0x09,0x04,0x02]))
    if len(body)!=TEXT_OFFSET:
        raise AssertionError("R42 original opcode alignment drift")
    message_data=text_bytes(message)
    if len(body)+len(message_data)>SCRIPT_SIZE:
        raise ValueError("R42 original message exceeds allocated sidecar asset")
    return body+message_data+bytes([0xFF])*(SCRIPT_SIZE-len(body)-len(message_data))


def rocket_event():
    return event_bytes(ROCKET_VAR,ROCKET_VALUE,ROCKET_FLAG,ROCKET_ITEM,
                       "ROCKET CACHE FOUND!")


def johto_event():
    return event_bytes(JOHTO_VAR,JOHTO_VALUE,JOHTO_FLAG,JOHTO_ITEM,
                       "JOHTO SIGNAL ONLINE!")


def audit_assets():
    a=rocket_event()
    b=johto_event()
    assert len(a)==len(b)==SCRIPT_SIZE
    assert a!=b
    return {ROCKET_ID:{"offset":ROCKET_OFFSET,"length":len(a),
                       "sha256":hashlib.sha256(a).hexdigest(),
                       "authored_translation_not_original_rom":True},
            JOHTO_ID:{"offset":JOHTO_OFFSET,"length":len(b),
                      "sha256":hashlib.sha256(b).hexdigest(),
                      "authored_translation_not_original_rom":True}}
