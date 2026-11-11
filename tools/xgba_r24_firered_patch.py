"""Opt-in source-built original FireRed R24 guest MMIO boundary fixture.

This uses the *same* R24 ARM guest request matrix as Emerald; only the
resource identifiers and original engine entry hook differ. Upstream files
are restored after the native build. No ROMs are committed.
"""
from __future__ import annotations
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class FireRedR24AdapterDrift(RuntimeError):
    pass

def patch_firered_r24(firered:Path)->dict[Path,str]:
    root=Path(firered)
    main=root/"src/main.c"
    before=main.read_text(encoding="utf-8")
    if "XgbaR24Run" in before or "gXgbaR24Proof" in before:
        raise FireRedR24AdapterDrift("Refusing doubly instrumented FireRed source")
    include=(ROOT/"integration/emerald/xgba_r24_boundary.inc").read_text(encoding="utf-8")
    include=include.replace("emerald.r24.","firered.r24.")
    # Original FireRed main.c doesn't include malloc.h itself; original
    # InitHeap is already called at the point where the guest fixture runs.
    injected=(
        '#include "malloc.h"\n'
        '#include "'+(ROOT/"integration/fire_red/xgba_guest.h").resolve().as_posix()+'"\n'
        +include+"\n"
    )
    declaration="void AgbMain()\n{"
    startup="    gLinkTransferringData = FALSE;\n\n    for (;;)"
    loop="    for (;;)\n    {\n        ReadKeys();"
    for label,needle in (("declaration",declaration),("startup",startup),
                         ("original frame callback",loop)):
        if before.count(needle)!=1:
            raise FireRedR24AdapterDrift(
                f"Pinned original FireRed {label} drift: {before.count(needle)}")
    after=before.replace(declaration,injected+"\n"+declaration,1)
    after=after.replace(startup,
       "    gLinkTransferringData = FALSE;\n"
       "    /* Original InitHeap/graphics callbacks already initialized. */\n"
       "    XgbaR24Run();\n\n    for (;;)",1)
    after=after.replace(loop,
       "    for (;;)\n    {\n"
       "        ++gXgbaR24Proof.main_ticks_at_end;\n"
       "        ReadKeys();",1)
    main.write_text(after,encoding="utf-8")
    return {main:before}

def restore_firered_r24(backups:dict[Path,str])->None:
    for path,contents in backups.items():
        path.write_text(contents,encoding="utf-8")
