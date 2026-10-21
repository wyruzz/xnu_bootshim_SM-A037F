/* SPDX-License-Identifier: MIT
 * Diagnostic milestone for Samsung Galaxy A03s SM-A037F.
 *
 * The donor ADT describes a different MediaTek board and must not be reused.
 * A target-specific Apple device tree is intentionally not implemented yet.
 */
#include "handoff.h"

size_t xnu_make_adt_seeded(void *buffer, size_t capacity,
                           const struct xnu_payload *payload,
                           uint32_t timebase,
                           const unsigned char *seed, size_t seed_bytes)
{
    (void)buffer;
    (void)capacity;
    (void)payload;
    (void)timebase;
    (void)seed;
    (void)seed_bytes;
    return 0;
}

size_t xnu_make_adt(void *buffer, size_t capacity,
                    const struct xnu_payload *payload, uint32_t timebase)
{
    (void)buffer;
    (void)capacity;
    (void)payload;
    (void)timebase;
    return 0;
}
