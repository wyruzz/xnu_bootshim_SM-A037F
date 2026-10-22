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

    /* Fail the link if architectural alignment assumptions regress. */
    ASSERT((vectors & 0x7ff) == 0,
           "AArch64 exception vector table must be 2 KiB aligned")
    ASSERT((_stack_top & 0xf) == 0,
           "AArch64 stack top must be 16-byte aligned")
    ASSERT(_bss_end <= _stack_top,
           "BSS must end before the diagnostic stack")

    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
