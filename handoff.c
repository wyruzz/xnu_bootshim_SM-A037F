/* SPDX-License-Identifier: MIT
 *
 * XNU handoff entry point for SM-A037F.
 *
 * Deliberately refuses to transfer control until the target-specific
 * physical memory map, translation regime, and XNU boot ABI are defined.
 * An arbitrary MMU setup here could invalidate current mappings or make
 * the kernel entry and ADT inaccessible.
 */
#include "handoff.h"

const char *handoff_boot(const struct fdt_info *fdt, uint64_t fdt_pa)
{
    (void)fdt;
    (void)fdt_pa;

    return "XNU_HANDOFF_DISABLED_UNTIL_MMU_AND_BOOT_ABI_ARE_DEFINED";
}
