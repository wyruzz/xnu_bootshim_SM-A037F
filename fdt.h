/* SPDX-License-Identifier: MIT */
#ifndef XNU_BOOTSHIM_FDT_H
#define XNU_BOOTSHIM_FDT_H
#include <stddef.h>
#include <stdint.h>
#define FDT_MAX_MEMORY 8
#define FDT_MAX_RESERVED 64
#define FDT_MAX_DYNAMIC_RESERVED 16
#define FDT_MAX_ALLOC_RANGES 8
struct fdt_range { uint64_t base, size; };
struct fdt_dynamic_reservation {
    uint64_t size, alignment;
    unsigned alloc_range_count;
    struct fdt_range alloc_ranges[FDT_MAX_ALLOC_RANGES];
};
struct fdt_info {
    uint32_t bytes;
    unsigned memory_count, reserved_count, dynamic_reserved_count;
    struct fdt_range memory[FDT_MAX_MEMORY], reserved[FDT_MAX_RESERVED];
    struct fdt_dynamic_reservation dynamic_reserved[FDT_MAX_DYNAMIC_RESERVED];
    uint64_t initrd_start, initrd_end;
};
/* Read-only, bounded inspection. Does not allocate or authorize a memory map. */
int fdt_inspect(const void *data, size_t available, struct fdt_info *info);
#endif
