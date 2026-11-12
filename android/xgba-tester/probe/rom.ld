/* R43 wholly-authored freestanding ARM7TDMI cartridge.
 * The GBA header's entry branch always lands at 0x080000C0.
 * Do NOT let the default GNU ARM linker reorder .text.start behind
 * ordinary functions or place orphan ELF sections before the entry. */
ENTRY(_start)
SECTIONS
{
    . = 0x080000C0;
    .text : ALIGN(4)
    {
        KEEP(*(.text.start))
        *(.text .text.*)
        *(.glue_7t) *(.glue_7)
        *(.rodata .rodata.*)
        *(.init)
        *(.fini)
    }
    . = ALIGN(4);
    .data : { *(.data .data.*) }
    . = ALIGN(4);
    .bss (NOLOAD) : { *(.bss .bss.*) *(COMMON) }
    /DISCARD/ : { *(.comment) *(.note*) *(.ARM.attributes) *(.eh_frame*) }
}
