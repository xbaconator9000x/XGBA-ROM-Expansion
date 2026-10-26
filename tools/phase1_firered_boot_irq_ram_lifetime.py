#!/usr/bin/env python3
"""Pinned FireRed reset, interrupt-vector relocation and RAM lifetime trace.

Source-only dependency evidence. This does not inspect a linked ELF, run an
emulator, or approve a whole-file semantic disposition.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/rom_header.s": "c98c89992a128b82ef3bc8f75c791cd1c6cbdcb9",
    "src/crt0.s": "a0d8a4b55237b38afc5b69d4e9aad0c2df232e14",
    "constants/gba_constants.inc": "3ff857ee8dfb1f4e2dfaf8ac98373bac5dfdb25c",
    "src/main.c": "542b0f5d16dd93107523d11163bfcb70a42b707a",
    "src/reset_save_heap.c": "745270dc7415b869c302daaa7b9c2b2e5b2865f1",
    "include/gba/defines.h": "5521e942c00cc2c263b842ae7608dfb7ac881a76",
    "include/gba/syscall.h": "22fdf09facfaa812bf11b13d1f3ff86271598511",
    "ld_script.ld": "9a4b45031e93c1e1da8186d8c697332710526048",
    "ld_script_rev10.ld": "4eb3bc2eec749437be5797202442188972ac0693",
    "ld_script_modern.ld": "e930243522bd21da40cc1a05de9a42b8ad409b46",
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def contract(files):
    header, crt, main = (files[p] for p in
                         ("src/rom_header.s", "src/crt0.s", "src/main.c"))
    defines, syscall = files["include/gba/defines.h"], files["include/gba/syscall.h"]
    reload_src = files["src/reset_save_heap.c"]
    gba_constants = files["constants/gba_constants.inc"]

    require(re.search(r"(?m)^Start:\s*\n\s*b start_vector\s*$", header),
            "ROM header entry branch drift")
    startup = re.search(
        r"(?s)\.global start_vector\s*start_vector:.*?"
        r"ldr r1, =INTR_VECTOR\s*adr r0, intr_main\s*str r0, \[r1\]\s*"
        r"ldr r1, =AgbMain\s*mov lr, pc\s*bx r1",
        crt)
    require(startup is not None, "reset vector / early IRQ / AgbMain chain drift")
    require(re.search(r"(?m)^\s*\.global intr_main\s*$", crt)
            and re.search(r"(?m)^intr_main:\s*$", crt),
            "early interrupt handler definition drift")
    require("#define INTR_VECTOR    (*(void **)0x3007FFC)" in defines,
            "IWRAM interrupt-vector slot drift")
    for symbol, value in (("EWRAM_START", "0x02000000"),
                          ("IWRAM_START", "0x03000000"),
                          ("IWRAM_END", "(IWRAM_START + 0x8000)")):
        require(f"#define {symbol}" in defines
                and re.search(rf"(?m)^#define\s+{symbol}\s+{re.escape(value)}\s*$",
                              defines), "RAM address definition drift: " + symbol)
    require("#define COMMON_DATA __attribute__((section(\"common_data\")))" in defines,
            "common data annotation drift")
    require("#define RESET_EWRAM      0x01" in syscall
            and "#define RESET_IWRAM      0x02" in syscall
            and "#define RESET_ALL        0xFF" in syscall,
            "BIOS reset flag contract drift")

    boot_start = main.index("void AgbMain()")
    boot_end = main.index("    InitGpuRegManager();", boot_start)
    boot = main[boot_start:boot_end]
    require(re.search(
        r"(?s)#if MODERN\s*// Modern compilers.*?"
        r"RegisterRamReset\(RESET_ALL & ~RESET_IWRAM\);.*?"
        r"#else\s*RegisterRamReset\(RESET_ALL\);\s*#endif //MODERN",
        boot), "legacy / modern boot RAM-reset branch drift")
    # Modern code manually clears 0x03000000 through 0x03007DFF, not
    # the final 0x200 bytes of IWRAM (which include the IRQ vector slot).
    for token in ("#0xC0", "#0x12", "#0xFC", "#0x7", ".LCU%=",
                  "cmp\\tr1, r2", "bcc\\t.LCU%="):
        require(token in boot, "modern IWRAM clearing loop drift: " + token)
    require(boot.count("stmia") == 8,
            "modern IWRAM clearing stride drift")
    require(boot.index("RegisterRamReset(RESET_ALL & ~RESET_IWRAM)")
            < boot.index("#0xFC")
            < boot.index("RegisterRamReset(RESET_ALL);"),
            "modern IWRAM clear ordering drift")
    require("COMMON_DATA u32 IntrMain_Buffer[0x200] = {0};" in main,
            "IWRAM interrupt handler copy buffer declaration drift")
    require(boot_end < main.index("    InitIntrHandlers();"),
            "interrupt handler setup no longer follows reset")

    init = re.search(r"(?s)void InitIntrHandlers\(void\)\s*\{(?P<body>[^{}]*)\}",
                     main)
    require(init is not None, "InitIntrHandlers function scope drift")
    body = init.group("body")
    sequence = (
        "DmaCopy32(3, intr_main, IntrMain_Buffer, sizeof(IntrMain_Buffer));",
        "INTR_VECTOR = IntrMain_Buffer;",
        "REG_IME = 1;",
        "EnableInterrupts(INTR_FLAG_VBLANK);",
    )
    require(all(item in body for item in sequence)
            and list(map(body.index, sequence)) == sorted(map(body.index, sequence)),
            "IRQ handler ROM-to-RAM copy / vector switch / enable order drift")

    reload = re.search(r"(?s)void ReloadSave\(void\)\s*\{(?P<body>[^{}]*)\}",
                       reload_src)
    require(reload is not None, "ReloadSave function scope drift")
    rb = reload.group("body")
    require("REG_IME = 0;" in rb
            and "RegisterRamReset(RESET_EWRAM);" in rb
            and "REG_IME = imeBackup;" in rb
            and "InitIntrHandlers(" not in rb
            and rb.index("REG_IME = 0;") < rb.index("RegisterRamReset(RESET_EWRAM);")
            < rb.index("REG_IME = imeBackup;"),
            "save reload EWRAM-only reset / IRQ masking contract drift")

    for path in ("ld_script.ld", "ld_script_rev10.ld", "ld_script_modern.ld"):
        script = files[path]
        section = re.search(
            r"(?ms)^\s*\.text\s*:\s*ALIGN\(4\)\s*\{(?P<body>[^{}]*)\}"
            r"\s*>\s*ROM\s*=0", script)
        require(section is not None, "ROM .text output scope drift: " + path)
        section_body = section.group("body")
        ordered = ("src/rom_header.o(", "src/crt0.o(.text);",
                   "src/main.o(.text);")
        require(all(x in section_body for x in ordered)
                and list(map(section_body.index, ordered))
                == sorted(map(section_body.index, ordered)),
                "ROM header / reset / main link ordering drift: " + path)
        require(re.search(
            r"(?ms)^\s*iwram\s+0x3000000\s+\(NOLOAD\)\s*:"
            r"\s*ALIGN\(4\)\s*\{[^{}]*\}\s*>\s*IWRAM\s*$", script),
            "IWRAM NOLOAD output drift: " + path)

    # Inspect the entire crt0 IRQ dispatcher, not just the boot vector.
    # The final GAMEPAK test has a conditional spin; a zero pending mask
    # falls through to callback-table slot 13 with an IF acknowledge of 0.
    irq_match = re.search(r"(?s)(?m)^intr_main:\s*(.*?)^\s*\.pool\s*$", crt)
    require(irq_match is not None, "IRQ handler body/literal-pool scope drift")
    irq = irq_match.group(1)
    flags = re.findall(
        r"(?m)^\s*ands r0, r1, #INTR_FLAG_([A-Z0-9]+)\s*$", irq)
    expected_flags = (
        "VCOUNT", "SERIAL", "TIMER3", "HBLANK", "VBLANK", "TIMER0",
        "TIMER1", "TIMER2", "DMA0", "DMA1", "DMA2", "DMA3",
        "KEYPAD", "GAMEPAK",
    )
    require(tuple(flags) == expected_flags,
            "14-slot IRQ dispatch priority/order drift")
    bit_numbers = {
        "VCOUNT": 2, "SERIAL": 7, "TIMER3": 6, "HBLANK": 1,
        "VBLANK": 0, "TIMER0": 3, "TIMER1": 4, "TIMER2": 5,
        "DMA0": 8, "DMA1": 9, "DMA2": 10, "DMA3": 11,
        "KEYPAD": 12, "GAMEPAK": 13,
    }
    for name, bit in bit_numbers.items():
        require(re.search(
            rf"(?m)^\s*\.set\s+INTR_FLAG_{name},\s*1 << {bit}\s*$",
            gba_constants) is not None, "IRQ flag definition drift: " + name)
    require(len(re.findall(
        r"(?m)^\s*add r12, r12, 0x4\s*$",
        irq.split("ands r0, r1, #INTR_FLAG_GAMEPAK", 1)[0])) == 13,
        "IRQ callback-table byte offset drift")
    require(re.search(
        r"ands r0, r1, #INTR_FLAG_GAMEPAK\s*\n"
        r"\s*strbne r0, \[r3, #REG_SOUNDCNT_X - REG_IE\]\s*\n"
        r"loop:\s*\n\s*bne loop @ spin\s*\n"
        r"jump_intr:\s*\n\s*strh r0, \[r3, #REG_IF - REG_IE\]",
        irq) is not None,
        "GAMEPAK spin / zero-pending fallthrough semantics drift")
    require(re.search(
        r"ldr r1, =gIntrTable\s*\n\s*add r1, r1, r12\s*\n"
        r"\s*ldr r0, \[r1\]\s*\n\s*stmdb sp!, \{lr\}\s*\n"
        r"\s*adr lr, intr_return\s*\n\s*bx r0", irq) is not None,
        "IRQ callback-pointer dispatch drift")
    table = re.search(
        r"const IntrFunc gIntrTableTemplate\[\]\s*=\s*\{(?P<body>[^{}]*)\};",
        main, re.S)
    require(table is not None, "IRQ callback template scope drift")
    callbacks = re.findall(r"(?m)^\s*(\w+),", table.group("body"))
    require(callbacks == [
        "VCountIntr", "SerialIntr", "Timer3Intr", "HBlankIntr",
        "VBlankIntr", *(["IntrDummy"] * 9),
    ], "IRQ priority-to-callback table mapping drift")

    return {
        "boot_entry": "ROM header branch -> start_vector -> AgbMain",
        "initial_irq_vector": "INTR_VECTOR (0x03007FFC) -> intr_main",
        "post_init_irq_vector": "INTR_VECTOR -> IntrMain_Buffer after DMA3 copy",
        "modern_manual_iwram_clear_start": "0x03000000",
        "modern_manual_iwram_clear_end_exclusive": "0x03007E00",
        "modern_iwram_top_bytes_not_in_manual_clear": 512,
        "modern_clear_stride_bytes": 128,
        "legacy_boot_reset": "RESET_ALL",
        "modern_bios_reset": "RESET_ALL & ~RESET_IWRAM",
        "reload_save_reset": "RESET_EWRAM only, with IME masked",
        "all_link_variants_boot_objects_in_rom_text": True,
        "compiled_section_or_runtime_proof": False,
        "irq_dispatch_flags_in_priority_order": list(expected_flags),
        "irq_callback_table_entries": len(callbacks),
        "no_pending_irq_source_falls_through_to_slot_13": True,
        "gamepak_pending_source_enters_spin": True,
        "irq_dispatch_runtime_reachability_proved": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.source.resolve()

    def git(*parts):
        return subprocess.check_output(
            ["git", "-C", str(root), *parts], text=True,
            stderr=subprocess.PIPE).strip()

    require(git("rev-parse", "HEAD") == PIN, "upstream commit drift")
    files = {}
    for path, sha in BLOBS.items():
        require((root / path).is_file() and git("hash-object", path) == sha,
                "pinned upstream Git blob drift: " + path)
        files[path] = (root / path).read_text(encoding="utf-8")
    facts = contract(files)

    mutations = [
        ("src/rom_header.s", "b start_vector", "b intr_main"),
        ("src/crt0.s", "adr r0, intr_main", "adr r0, AgbMain"),
        ("src/crt0.s", "ldr r1, =AgbMain", "ldr r1, =intr_main"),
        ("include/gba/defines.h", "0x3007FFC", "0x3007FF8"),
        ("include/gba/syscall.h", "RESET_IWRAM      0x02", "RESET_IWRAM      0x04"),
        ("src/main.c", "RegisterRamReset(RESET_ALL & ~RESET_IWRAM);",
         "RegisterRamReset(RESET_ALL);"),
        ("src/main.c", '"\\tmov\\tr2, #0xFC\\n"',
         '"\\tmov\\tr2, #0xFD\\n"'),
        ("src/main.c", "INTR_VECTOR = IntrMain_Buffer;",
         "INTR_VECTOR = intr_main;"),
        ("src/main.c", "DmaCopy32(3, intr_main, IntrMain_Buffer,",
         "DmaCopy32(3, gIntrTable, IntrMain_Buffer,"),
        ("src/reset_save_heap.c", "RegisterRamReset(RESET_EWRAM);",
         "RegisterRamReset(RESET_ALL);"),
        ("ld_script.ld", "src/crt0.o(.text);", "src/crt0.o(.data);"),
        ("ld_script_rev10.ld", "src/main.o(.text);", "src/main.o(.data);"),
        ("ld_script_modern.ld", "src/crt0.o(.text);", "src/crt0.o(.data);"),
        ("ld_script_modern.ld", "iwram 0x3000000 (NOLOAD)",
         "iwram 0x3000000"),
        ("src/crt0.s", "ands r0, r1, #INTR_FLAG_VCOUNT",
         "ands r0, r1, #INTR_FLAG_TIMER0"),
        ("src/crt0.s", "add r12, r12, 0x4",
         "add r12, r12, 0x8"),
        ("src/crt0.s", "bne loop @ spin",
         "b loop @ spin"),
        ("src/crt0.s", "strbne r0, [r3, #REG_SOUNDCNT_X - REG_IE]",
         "strb r0, [r3, #REG_SOUNDCNT_X - REG_IE]"),
        ("src/main.c", "VCountIntr, // V-count interrupt",
         "IntrDummy, // V-count interrupt"),
        ("constants/gba_constants.inc", ".set INTR_FLAG_GAMEPAK, 1 << 13",
         ".set INTR_FLAG_GAMEPAK, 1 << 12"),
    ]
    for index, (path, before, after) in enumerate(mutations, 1):
        require(before in files[path], f"mutation fixture {index} missing: {path}")
        modified = dict(files)
        modified[path] = files[path].replace(before, after, 1)
        try:
            contract(modified)
        except RuntimeError:
            continue
        raise RuntimeError(f"negative mutation {index} accepted: {path}")

    output = {
        "evidence_class": "PINNED_FIRERED_BOOT_IRQ_RAM_LIFETIME_SOURCE_ONLY",
        "upstream_commit": PIN,
        "pinned_blobs": BLOBS,
        "facts": facts,
        "negative_controls_passed": len(mutations),
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_whole_file_approvals": 0,
        "unresolved": [
            "Actual linked ROM and IWRAM symbols, copy extents and ELF section ranges",
            "Hardware BIOS reset semantics, interrupt timing and runtime trace",
            "Emulator prefetch and bank remap atomicity at boot and reload",
            "Editor round trip and independent whole-file review",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(f"PINNED_FIRERED_BOOT_IRQ_SOURCE_PASS negative_controls={len(mutations)}")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals=0")


if __name__ == "__main__":
    main()
