/* SPDX-License-Identifier: MIT
 * AArch64 Image framing follows dipa-studio/ios-sweet (see CREDITS.md).
 * Diagnostic entry accepts EL1 or EL2; EL2 transition is an explicit helper.
 */
.section .text.head, "ax"
.global _head
_head:
    b _start
    .long 0
    .quad 0
    .quad _end
    .quad 0xa
    .quad 0, 0, 0
    .ascii "ARM\\x64"
    .long 0
.text
.global _start
_start:
    msr daifset, #0xf
    mov x19, x0
    mov x20, x1
    mov x21, x2
    mov x22, x3
    mov x23, sp
    msr spsel, #1
    adr x1, _stack_top
    mov sp, x1
    adr x1, vectors
    mrs x2, CurrentEL
    cmp x2, #8
    b.eq 1f
    cmp x2, #4
    b.ne halt
    msr vbar_el1, x1
    b 2f
1:  msr vbar_el2, x1
2:  isb
    adr x1, _bss_start
    adr x2, _bss_end
3:  cmp x1, x2
    b.hs 4f
    str xzr, [x1], #8
    b 3b
4:  mov x0, x19
    mov x1, x20
    mov x2, x21
    mov x3, x22
    mov x4, x23
    bl shim_main
halt:
    wfe
    b halt

/*
 * void el2_to_el1(void (*entry)(uint64_t, uint64_t, uint64_t),
 *                 uint64_t arg0, uint64_t arg1,
 *                 uint64_t el1_stack_top, void *el1_vectors);
 *
 * Entry contract (AArch64 PCS):
 *   x0 = EL1 entry address
 *   x1 = entry argument 0
 *   x2 = entry argument 1
 *   x3 = 16-byte-aligned EL1 stack top
 *   x4 = 2-KiB-aligned EL1 exception-vector base
 *
 * This is a one-way exception-level transition, not a normal C call:
 * it never returns to EL2. It deliberately does not configure translation
 * tables or SCTLR_EL1; the caller must ensure the EL1 address-space and
 * inherited MMU/cache state are compatible before invoking it.
 */
.section .text, "ax"
.align 4
.global el2_to_el1
.type el2_to_el1, %function
el2_to_el1:
    msr     daifset, #0xf

    /* This helper is valid only when called from AArch64 EL2. */
    mrs     x9, CurrentEL
    cmp     x9, #0x8
    b.ne    halt

    /* Retain the target state while setting up EL1 system registers. */
    mov     x19, x0                  /* EL1 entry */
    mov     x20, x1                  /* argument 0 */
    mov     x21, x2                  /* argument 1 */
    mov     x22, x3                  /* EL1 stack */
    mov     x23, x4                  /* EL1 vectors */

    /* EL1 execution state must be AArch64 (HCR_EL2.RW = 1). */
    mrs     x9, hcr_el2
    orr     x9, x9, #(1 << 31)
    msr     hcr_el2, x9

    /* Install EL1 exception vectors and stack before exception return. */
    msr     vbar_el1, x23
    msr     sp_el1, x22

    /* EL1h, AArch64, with D/A/I/F masked while early boot runs. */
    mov     x9, #0x3c5
    msr     spsr_el2, x9
    msr     elr_el2, x19
    isb

    /* Pass the entry arguments using the AArch64 procedure-call convention. */
    mov     x0, x20
    mov     x1, x21
    eret
.size el2_to_el1, . - el2_to_el1

/* Exception vectors used by the diagnostic milestone. */
.macro vector slot
    .balign 128
    mov x0, #\slot
    b exception_report
.endm
.balign 2048
.global vectors
vectors:
    vector 0
    vector 1
    vector 2
    vector 3
    vector 4
    vector 5
    vector 6
    vector 7
    vector 8
    vector 9
    vector 10
    vector 11
    vector 12
    vector 13
    vector 14
    vector 15
