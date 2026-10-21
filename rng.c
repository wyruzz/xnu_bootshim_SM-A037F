/* SPDX-License-Identifier: MIT
 * Diagnostic milestone for Samsung Galaxy A03s SM-A037F.
 *
 * The previous implementation accessed MT8167-only registers. Until the
 * MT6765 RNG and clock tree are verified, fail closed without MMIO access.
 */
#include "handoff.h"

int mt8167_random_seed(unsigned char seed[64], uint32_t timebase)
{
    (void)timebase;
    if (seed) {
        for (unsigned i = 0; i < 64; i++) seed[i] = 0;
    }
    return -1;
}
