#!/usr/bin/env python3
"""R95: extract the genuine Goldenrod Boy2 HnS OBJ from the official source build.

The OBJ graphics, palette, eight-byte OAM, and FIRST native animation are
copied from the exact compiled upstream HnS GBA; no owner ROM or art is
published. The first animation is not the complete directional animation set.
"""
from __future__ import annotations
import hashlib
import re
import struct
import zlib
from pathlib import Path

WORLD=2
GFX_ID=406  # OBJ_EVENT_GFX_BOY_2_HNS, official v2.0.6 constants
FRAMES=9
WIDTH=16
HEIGHT=32
FRAME_BYTES=WIDTH*HEIGHT//2
BASE=0x08000000
PAGE=16384
SOURCE_OBJECT="gObjectEventGraphicsInfo_Boy2_hns"
PIC_TABLE="sPicTable_Boy2_hns"
PIC_BYTES="gObjectEventPic_Boy2_hns"
PAL_BYTES="gObjectEventPal_Npc4_hns"
OAM_BYTES="gObjectEventBaseOam_16x32"
ANIM_TABLE="sAnimTable_Standard"
FIRST_ANIM="sAnim_FaceSouth"
class HnsOriginalObjectError(ValueError):pass

def _symbol_offset(symbols,rom,symbol,size):
    address=symbols.get(symbol)
    if type(address) is not int or address<BASE or address+size>BASE+len(rom):
        raise HnsOriginalObjectError("Missing or out-of-ROM original linked HnS symbol: "+symbol)
    return address-BASE

def _assert_source_declarations(root):
    root=Path(root)
    paths={
        "constants":root/"include/constants/event_objects.h",
        "info":root/"src/data/object_events/object_event_graphics_info.h",
        "pics":root/"src/data/object_events/object_event_pic_tables.h",
        "graphics":root/"src/data/object_events/object_event_graphics.h",
        "anims":root/"src/data/object_events/object_event_anims.h"}
    texts={key:path.read_text() for key,path in paths.items()}
    if not re.search(r"#define\s+OBJ_EVENT_GFX_BOY_2_HNS\s+406\b",texts["constants"]):
        raise HnsOriginalObjectError("Official HnS original 16-bit Boy2 graphics ID drifted")
    # Bind the linked object to its exact official source-defined assets,
    # not a coincidentally named symbol in a different build.
    expected=(
        (texts["info"],r"gObjectEventGraphicsInfo_Boy2_hns\s*=\s*\{[^;]*sPicTable_Boy2_hns"),
        (texts["info"],r"gObjectEventGraphicsInfo_Boy2_hns\s*=\s*\{[^;]*OBJ_EVENT_PAL_TAG_NPC_4_HNS"),
        (texts["pics"],r"sPicTable_Boy2_hns\[\]\s*=\s*\{"),
        (texts["graphics"],r"gObjectEventPic_Boy2_hns\[\]\s*=\s*INCBIN_U32\(\"graphics/object_events/pics/people/boy_2_hns\.4bpp\"\)"),
        (texts["graphics"],r"gObjectEventPal_Npc4_hns\[\]\s*=\s*INCBIN_U16\(\"graphics/object_events/palettes/npc_green_hns\.gbapal\"\)"),
        (texts["anims"],r"sAnimTable_Standard\[\]\s*=\s*\{[^;]*sAnim_FaceSouth")
    )
    for source,pattern in expected:
        if not re.search(pattern,source,re.DOTALL):
            raise HnsOriginalObjectError("Official original Boy2 asset declaration changed: "+pattern)
    block=re.search(r"sPicTable_Boy2_hns\[\]\s*=\s*\{([^}]*)\}",texts["pics"])
    if block is None:
        raise HnsOriginalObjectError("Boy2 original compiled frame table declaration missing")
    indices=[int(x) for x in re.findall(
        r"overworld_frame\(gObjectEventPic_Boy2_hns,\s*2,\s*4,\s*(\d+)\)",
        block.group(1))]
    if indices!=list(range(FRAMES)):
        raise HnsOriginalObjectError("Original HnS Boy2 nine-frame sequence changed")
    if not (root/"graphics/object_events/pics/people/boy_2_hns.png").is_file():
        raise HnsOriginalObjectError("Original Boy2 source sprite PNG absent")
    return indices

def extract_original_boy2(root,rom,symbols):
    """Return native R56 owner-authenticated 9-frame sections and provenance.

    Source declarations bind each symbol to original upstream artwork. The
    built ROM validates all nine actual frame pointers, real graphics-info
    pointers, the first native animation and OAM, without fabricated defaults.
    """
    _assert_source_declarations(root)
    rom=bytes(rom)
    frames_offset=_symbol_offset(symbols,rom,PIC_BYTES,FRAMES*FRAME_BYTES)
    pic_offset=_symbol_offset(symbols,rom,PIC_TABLE,FRAMES*8)
    desc_offset=_symbol_offset(symbols,rom,SOURCE_OBJECT,48)
    palette_offset=_symbol_offset(symbols,rom,PAL_BYTES,32)
    oam_offset=_symbol_offset(symbols,rom,OAM_BYTES,8)
    anim_table_offset=_symbol_offset(symbols,rom,ANIM_TABLE,4)
    anim_offset=_symbol_offset(symbols,rom,FIRST_ANIM,8)
    for i in range(FRAMES):
        pointer,bytes_per_frame=struct.unpack_from("<IH",rom,pic_offset+8*i)
        if pointer!=BASE+frames_offset+i*FRAME_BYTES or bytes_per_frame!=FRAME_BYTES:
            raise HnsOriginalObjectError("Original Boy2 linked SpriteFrameImage table differs from source")
        if rom[pic_offset+8*i+6:pic_offset+8*i+8]!=b"\0\0":
            raise HnsOriginalObjectError("Original Boy2 frame stride unsupported")
    desc=rom[desc_offset:desc_offset+64]
    for symbol in (PIC_TABLE,OAM_BYTES,ANIM_TABLE):
        if struct.pack("<I",symbols[symbol]) not in desc:
            raise HnsOriginalObjectError("Original HnS graphics descriptor pointer not connected: "+symbol)
    if struct.unpack_from("<I",rom,anim_table_offset)[0]!=symbols[FIRST_ANIM]:
        raise HnsOriginalObjectError("Original first animation not connected to official table")
    f=rom[frames_offset:frames_offset+FRAMES*FRAME_BYTES]
    p=rom[palette_offset:palette_offset+32]
    o=rom[oam_offset:oam_offset+8]
    a=rom[anim_offset:anim_offset+8]
    # The actual GBA OAM and FIRST animation must be natively admissible.
    attr0,attr1,attr2,attr3=struct.unpack("<4H",o)
    shape=(attr0>>14)&3;size=(attr1>>14)&3
    if shape!=2 or size!=2 or (attr0&0x3f00) or (attr1&0x3c00) or (attr2&0xf3ff) or attr3:
        raise HnsOriginalObjectError("Original Boy2 OAM incompatible with R66 native 16x32")
    image,delay,jump,argument=struct.unpack("<4H",a)
    if image!=0 or not 1<=delay<=255 or jump!=0xfffd or argument!=0:
        raise HnsOriginalObjectError("Original Boy2 first animation incompatible with native R66")
    parts=(f,p,o,a)
    meta=bytearray(64)
    meta[:4]=b"X56S"
    meta[4:6]=bytes((1,WORLD))
    struct.pack_into("<H",meta,6,GFX_ID)
    struct.pack_into("<I",meta,8,desc_offset)
    for i,part in enumerate(parts):
        struct.pack_into("<I",meta,12+i*4,len(part))
        struct.pack_into("<I",meta,28+i*4,zlib.crc32(part)&0xffffffff)
        meta[44+i]=(len(part)+PAGE-1)//PAGE
    meta[48:52]=bytes((0,1,WIDTH,HEIGHT))
    struct.pack_into("<H",meta,52,FRAMES)
    struct.pack_into("<I",meta,60,zlib.crc32(meta[:60])&0xffffffff)
    name=f"r56.w{WORLD}.s{GFX_ID:04x}"
    resources=[(name+".meta",bytes(meta))]
    resources.extend((name+"."+suffix+"00",part.ljust(PAGE,b"\0"))
                     for suffix,part in zip("fpoa",parts))
    evidence={
        "id":name,"original_graphics_id":GFX_ID,"world":WORLD,
        "npc_source_symbol":SOURCE_OBJECT,"source_graphics_info_offset":desc_offset,
        "linked_pic_table_offset":pic_offset,"linked_frame_data_offset":frames_offset,
        "linked_palette_offset":palette_offset,"linked_oam_offset":oam_offset,
        "linked_first_animation_offset":anim_offset,
        "frame_count":FRAMES,"frame_shape":[WIDTH,HEIGHT],
        "exact_source_sections_sha256":[hashlib.sha256(part).hexdigest() for part in parts],
        "original_directional_animations_complete":False,
        "real_gameplay_fly_passed":False
    }
    return resources,evidence
