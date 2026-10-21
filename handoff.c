/* SPDX-License-Identifier: MIT
 * Diagnostic milestone for Samsung Galaxy A03s SM-A037F.
 *
 * The former implementation contains A04BR3-specific memory assumptions,
 * payload policy and framebuffer addresses. Keep the build interfaces intact,
 * but reject handoff until the SM-A037F memory map and ABI are implemented.
 */
#include "handoff.h"

int handoff_sparse(void *destination, const unsigned char *source,
                   uint64_t length, uint64_t memory)
{
    (void)destination;
    (void)source;
    (void)length;
    (void)memory;
    return -1;
}

int handoff_validate(const void *payload, size_t length, uint64_t payload_pa,
                     const struct fdt_info *fdt, uint64_t fdt_pa,
                     uint64_t shim_start, uint64_t shim_end,
                     struct handoff_plan *plan)
{
    (void)payload;
    (void)length;
    (void)payload_pa;
    (void)fdt;
    (void)fdt_pa;
    (void)shim_start;
    (void)shim_end;
    (void)plan;
    return -1;
}

int handoff_video_setup(struct xnu_video *video, const struct fdt_info *fdt,
                        const struct xnu_payload *payload)
{
    (void)fdt;
    (void)payload;
    if (video) *video = (struct xnu_video){0};
    return 0;
}

const char *handoff_boot(const struct fdt_info *fdt, uint64_t fdt_pa)
{
    (void)fdt;
    (void)fdt_pa;
    return "XNU_HANDOFF_DISABLED_TARGET_PORT_INCOMPLETE";
}
