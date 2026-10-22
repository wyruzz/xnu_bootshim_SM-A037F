/* SPDX-License-Identifier: MIT */
ENTRY(_head)

/* Keep executable code RX and writable state RW; never emit an RWX LOAD. */
PHDRS {
    text PT_LOAD FLAGS(5);
    data PT_LOAD FLAGS(6);
}

SECTIONS {
    . = 0;
    .text : { *(.text.head) *(.text*) } :text
    .rodata : { *(.rodata*) } :text

    /* Separate permissions at a page boundary so MMU page permissions can
       match the ELF segment permissions instead of sharing an RWX page. */
    . = ALIGN(0x1000);
    .data : { *(.data*) } :data
    . = ALIGN(16);
    _bss_start = .;
    .bss : { *(.bss*) *(COMMON) } :data
    . = ALIGN(16);
    _bss_end = .;
    . += 0x4000;
    . = ALIGN(16);
    _stack_top = .;
    _end = .;
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
