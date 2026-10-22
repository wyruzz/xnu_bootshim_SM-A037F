/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include "fdt.h"

int main(void)
{
    struct fdt_info info;
    unsigned char invalid_header[40] = {0};

    /* Public parser API must fail closed on invalid pointers and headers. */
    assert(fdt_inspect(NULL, sizeof invalid_header, &info) == -1);
    assert(fdt_inspect(invalid_header, sizeof invalid_header, NULL) == -1);
    assert(fdt_inspect(invalid_header, sizeof invalid_header, &info) == -1);
    assert(fdt_inspect(invalid_header, 0, &info) == -1);
    return 0;
}
