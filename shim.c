/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 yuma shimizu
 * Diagnostic stage only: no kernel launch, storage access or power changes.
 */
#include <stdint.h>
#include "fdt.h"
#include "handoff.h"

static struct fdt_info observed_fdt;

/*
 * Optional physical-RAM diagnostic log.
 *
 * Define SHIM_RAM_LOG_PHYS_ADDR only after reserving and validating the
 * range for this board. It is intentionally disabled by default: an
 * arbitrary physical address can corrupt live firmware/kernel data.
 */
#ifdef SHIM_RAM_LOG_PHYS_ADDR
#define SHIM_LOG_MAGIC 0x474F4C58u /* "XLOG" */
#define SHIM_LOG_VERSION 1u
#define SHIM_LOG_CAPACITY 32u

enum shim_log_event {
    SHIM_LOG_START = 1,
    SHIM_LOG_EXCEPTION = 2,
    SHIM_LOG_FDT_CHECK = 3,
    SHIM_LOG_FDT_INVALID = 4,
    SHIM_LOG_DIAGNOSTIC_STOP = 5
};

struct shim_log_entry {
    uint32_t event;
    uint32_t detail;
};

struct shim_log_buffer {
    uint32_t magic;
    uint32_t version;
    uint32_t count;
    uint32_t reserved;
    struct shim_log_entry entries[SHIM_LOG_CAPACITY];
};

static volatile struct shim_log_buffer *const shim_log =
    (volatile struct shim_log_buffer *)(uintptr_t)SHIM_RAM_LOG_PHYS_ADDR;

static void shim_log_init(void)
{
    shim_log->magic = SHIM_LOG_MAGIC;
    shim_log->version = SHIM_LOG_VERSION;
    shim_log->count = 0;
    shim_log->reserved = 0;
    __asm__ volatile("dsb sy" ::: "memory");
}

static void shim_log_event(uint32_t event, uint32_t detail)
{
    uint32_t i;

    if (shim_log->magic != SHIM_LOG_MAGIC ||
        shim_log->version != SHIM_LOG_VERSION)
        return;

    i = shim_log->count;
    if (i >= SHIM_LOG_CAPACITY)
        return;

    shim_log->entries[i].event = event;
    shim_log->entries[i].detail = detail;
    __asm__ volatile("dsb sy" ::: "memory");
    shim_log->count = i + 1;
    __asm__ volatile("dsb sy" ::: "memory");
}
#else
#define shim_log_init() ((void)0)
#define shim_log_event(event, detail) ((void)0)
enum {
    SHIM_LOG_START = 1,
    SHIM_LOG_EXCEPTION = 2,
    SHIM_LOG_FDT_CHECK = 3,
    SHIM_LOG_FDT_INVALID = 4,
    SHIM_LOG_DIAGNOSTIC_STOP = 5
};
#endif

#define MTK_WDT_MODE_REG ((volatile uint32_t *)0x10007000u)
#define WDT_MODE_EN      (1u << 0)
#define WDT_MODE_KEY     (0x22u << 24)

static void watchdog_disable(void)
{
    uint32_t mode = *MTK_WDT_MODE_REG;
    mode &= ~WDT_MODE_EN;
    mode = (mode & 0x00FFFFFFu) | WDT_MODE_KEY;
    *MTK_WDT_MODE_REG = mode;
    __asm__ volatile("dsb sy" ::: "memory");
}

#define READ_SYSREG(reg) ({ uint64_t v; __asm__ volatile("mrs %0, " #reg : "=r"(v)); v; })
/* A03s live Device Tree: serial@11020000 has reg = <0 0x11002000 0 0x1000>. */
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
    shim_log_event(SHIM_LOG_EXCEPTION, (uint32_t)slot);
    watchdog_disable();
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
    shim_log_init();
    shim_log_event(SHIM_LOG_START, 0);
    uint64_t el = READ_SYSREG(CurrentEL);
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
        /* AArch64 Linux Image boot protocol passes the FDT address in x2. */
        shim_el1(x2);
    }
    /* Watchdog disable is attempted at shim entry for diagnostics. */
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
    value("SCTLR_EL1", READ_SYSREG(SCTLR_EL1));
    value("CNTFRQ_EL0", READ_SYSREG(CNTFRQ_EL0));
    value("CNTVCT_EL0", READ_SYSREG(CNTVCT_EL0));
    value("DTB", dtb);
    /* Keep the entire 1 MiB parser window inside the captured DRAM span. */
    shim_log_event(SHIM_LOG_FDT_CHECK, 0);
    if (dtb < 0x40000000 || dtb > 0x13ff00000ULL || (dtb & 7) ||
        fdt_inspect((const void *)(uintptr_t)dtb, 0x100000, &observed_fdt)) {
        shim_log_event(SHIM_LOG_FDT_INVALID, 0);
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
    value("FDT_dynamic_reserved_count", observed_fdt.dynamic_reserved_count);
    for (unsigned i = 0; i < observed_fdt.reserved_count; i++) {
        value("FDT_reserved_base", observed_fdt.reserved[i].base);
        value("FDT_reserved_size", observed_fdt.reserved[i].size);
    }
    for (unsigned i = 0; i < observed_fdt.dynamic_reserved_count; i++) {
        value("FDT_dynamic_reserved_size", observed_fdt.dynamic_reserved[i].size);
        value("FDT_dynamic_reserved_alignment", observed_fdt.dynamic_reserved[i].alignment);
        value("FDT_dynamic_reserved_alloc_range_count", observed_fdt.dynamic_reserved[i].alloc_range_count);
        for (unsigned j = 0; j < observed_fdt.dynamic_reserved[i].alloc_range_count; j++) {
            value("FDT_dynamic_reserved_alloc_base", observed_fdt.dynamic_reserved[i].alloc_ranges[j].base);
            value("FDT_dynamic_reserved_alloc_size", observed_fdt.dynamic_reserved[i].alloc_ranges[j].size);
        }
    }
    value("FDT_initrd_start", observed_fdt.initrd_start);
    value("FDT_initrd_end", observed_fdt.initrd_end);
    puts_uart("SHIM_EL1_DIAGNOSTIC_DONE\n");
    puts_uart("DIAGNOSTIC_ONLY_HANDOFF_DISABLED\n");
    shim_log_event(SHIM_LOG_DIAGNOSTIC_STOP, 0);
    stop();
}
