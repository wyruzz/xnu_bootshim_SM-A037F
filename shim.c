/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 yuma shimizu
 * Diagnostic stage only: no kernel launch, storage access or power changes.
 */
#include <stdint.h>
#include "fdt.h"
#include "handoff.h"

static struct fdt_info observed_fdt;

#define FDT_PROBE_MAX 0x100000UL
/* Temporary diagnostic window: 0x40000000 + 0x100000000 bytes of DRAM.
 * Leave a full FDT_PROBE_MAX window before the end to bound parser reads. */
#define DRAM_START 0x40000000ULL
#define DRAM_END   0x140000000ULL

#define READ_SYSREG(reg) ({ uint64_t v; __asm__ volatile("mrs %0, " #reg : "=r"(v)); v; })
/* SM-A037F DT reg and Linux sysfs both identify UART0 at 0x11002000. */
#define UART_BASE ((uintptr_t)0x11002000)
#define UART_LSR (UART_BASE + 0x14)
#define UART_TX_READY (1u << 5)

static void putc_uart(char c)
{
    /* Preserve the UART setup inherited from LK, including its baud rate. */
    for (unsigned int n = 0; n < 1000000; n++) {
        if (*(volatile uint32_t *)UART_LSR & UART_TX_READY) {
            *(volatile uint32_t *)UART_BASE = (uint8_t)c;
            return;
        }
    }
}

static void puts_uart(const char *s)
{
    while (*s) {
        if (*s == '\n') putc_uart('\r');
        putc_uart(*s++);
    }
}

static void value(const char *label, uint64_t v)
{
    puts_uart(label);
    puts_uart("=0x");
    for (int shift = 60; shift >= 0; shift -= 4) {
        unsigned int digit = (unsigned int)(v >> shift) & 15;
        putc_uart((char)(digit < 10 ? '0' + digit : 'a' + digit - 10));
    }
    puts_uart("\n");
}

void handoff_trace(const char *label, uint64_t v) { value(label, v); }
void handoff_message(const char *message) { puts_uart(message); }

__attribute__((noreturn)) static void stop(void)
{
    for (;;) __asm__ volatile("wfe");
}

__attribute__((noreturn)) void exception_report(uint64_t slot)
{
    uint64_t el = READ_SYSREG(CurrentEL);
    puts_uart("XNU_SHIM_EXCEPTION\n");
    value("vector", slot);
    value("CurrentEL", el);
    if (el == 8) {
        value("ESR_EL2", READ_SYSREG(ESR_EL2));
        value("ELR_EL2", READ_SYSREG(ELR_EL2));
        value("FAR_EL2", READ_SYSREG(FAR_EL2));
    } else {
        value("ESR_EL1", READ_SYSREG(ESR_EL1));
        value("ELR_EL1", READ_SYSREG(ELR_EL1));
        value("FAR_EL1", READ_SYSREG(FAR_EL1));
    }
    stop();
}

__attribute__((noreturn)) void shim_main(uint64_t x0, uint64_t x1,
                                        uint64_t x2, uint64_t x3, uint64_t old_sp)
{
    uint64_t el = READ_SYSREG(CurrentEL);
    /* UART_BASE is a physical MMIO address. Do not touch it before proving
     * the active exception level has its MMU disabled; this prototype has no
     * verified virtual mapping for UART. Fail silently if that prerequisite
     * is not met, because printing the reason would itself access the UART. */
    uint64_t sctlr = el == 8 ? READ_SYSREG(SCTLR_EL2) : READ_SYSREG(SCTLR_EL1);
    if ((el != 8 && el != 4) || (sctlr & 1U)) stop();

    puts_uart("\nXNU_SM_A037F_SHIM_DIAGNOSTIC_V1\n");
    value("CurrentEL", el);
    value("entry_x0", x0);
    value("entry_x1", x1);
    value("entry_x2", x2);
    value("entry_x3", x3);
    value("entry_sp", old_sp);
    value("MIDR_EL1", READ_SYSREG(MIDR_EL1));
    value("MPIDR_EL1", READ_SYSREG(MPIDR_EL1));
    value("ID_AA64ISAR0_EL1", READ_SYSREG(ID_AA64ISAR0_EL1));
    value("ID_AA64PFR0_EL1", READ_SYSREG(ID_AA64PFR0_EL1));
    value("ID_AA64MMFR0_EL1", READ_SYSREG(ID_AA64MMFR0_EL1));
    value("CNTFRQ_EL0", READ_SYSREG(CNTFRQ_EL0));
    value("CNTVCT_EL0", READ_SYSREG(CNTVCT_EL0));
    if (el == 8) value("SCTLR_EL2", READ_SYSREG(SCTLR_EL2));
    else value("SCTLR_EL1", READ_SYSREG(SCTLR_EL1));
    puts_uart("SHIM_DIAGNOSTIC_DONE\n");
    if (el == 8) {
        /* Stage 1 is observational only: do not change exception level or
         * inherited MMU, cache, timer, interrupt, or clock state. */
        value("HCR_EL2", READ_SYSREG(HCR_EL2));
        value("CNTHCTL_EL2", READ_SYSREG(CNTHCTL_EL2));
        puts_uart("EL2_DIAGNOSTIC_ONLY_STOP\n");
        stop();
    }
    if (el == 4) {
        extern void shim_el1(uint64_t dtb);
        shim_el1(x0);
    }
    /* Leave the inherited watchdog untouched. A later reset is possible. */
    stop();
}

__attribute__((noreturn)) void shim_el1(uint64_t dtb)
{
    puts_uart("XNU_SM_A037F_EL1_DIAGNOSTIC_V1\n");
    value("CurrentEL", READ_SYSREG(CurrentEL));
    if (READ_SYSREG(CurrentEL) != 4) {
        puts_uart("EL1_DIAGNOSTIC_WRONG_EXCEPTION_LEVEL\n");
        stop();
    }
    uint64_t sctlr_el1 = READ_SYSREG(SCTLR_EL1);
    value("SCTLR_EL1", sctlr_el1);
    if (sctlr_el1 & 1U) {
        /* x0 is expected to be a physical DTB address. Without a known
         * identity mapping, dereferencing it while the MMU is enabled is
         * unsafe; report the condition and fail closed. */
        puts_uart("FDT_SKIP_MMU_ENABLED\n");
        stop();
    }
    value("CNTFRQ_EL0", READ_SYSREG(CNTFRQ_EL0));
    value("CNTVCT_EL0", READ_SYSREG(CNTVCT_EL0));
    value("DTB", dtb);
    /* Restrict all speculative input parsing to the known low DRAM window. */
    if (dtb < DRAM_START || dtb > DRAM_END - FDT_PROBE_MAX || (dtb & 7) ||
        fdt_inspect((const void *)(uintptr_t)dtb, FDT_PROBE_MAX, &observed_fdt)) {
        puts_uart("FDT_INVALID\n");
        stop();
    }
    value("FDT_bytes", observed_fdt.bytes);
    value("FDT_memory_count", observed_fdt.memory_count);
    for (unsigned i = 0; i < observed_fdt.memory_count; i++) {
        value("FDT_memory_base", observed_fdt.memory[i].base);
        value("FDT_memory_size", observed_fdt.memory[i].size);
    }
    value("FDT_reserved_count", observed_fdt.reserved_count);
    for (unsigned i = 0; i < observed_fdt.reserved_count; i++) {
        value("FDT_reserved_base", observed_fdt.reserved[i].base);
        value("FDT_reserved_size", observed_fdt.reserved[i].size);
    }
    value("FDT_initrd_start", observed_fdt.initrd_start);
    value("FDT_initrd_end", observed_fdt.initrd_end);
    puts_uart("SHIM_EL1_DIAGNOSTIC_DONE\n");
    puts_uart("DIAGNOSTIC_ONLY_HANDOFF_DISABLED\n");
    stop();
}
