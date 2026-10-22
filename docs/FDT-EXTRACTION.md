# FDT extraction: current implementation and evidence gaps

This note describes the existing parser in `fdt.c` and separates test data from
actual Galaxy A03s observations.

## What the parser currently extracts

The read-only function `fdt_inspect()` in `fdt.c` reads:

- the FDT header and bounded structure/string blocks;
- the FDT memory-reservation table (`/memreserve/`);
- memory ranges from a root child named `memory` or `memory@...`;
- fixed `reg` ranges from direct children of `/reserved-memory`;
- `linux,initrd-start` and `linux,initrd-end` under `/chosen`.

It does not yet resolve UART `clocks` or `pinctrl-0` phandles, decode UART
register properties, interpret dynamic reserved-memory nodes that use `size`
instead of `reg`, or prove that an FDT pointer is mapped and safe to read.

## Important: test fixture is synthetic

`tests/fdt-fixture.dts` is a parser test fixture. Its example DRAM ranges
(`0x40000000/0x40000000`, `0x80000000/0x3f9c0000`), reserved ranges and initrd
addresses are **not Galaxy A03s measurements**. They must not be copied into a
platform configuration or used as a runtime memory map.

The A03s values should only be added after inspecting the actual device tree
blob passed to the shim, or a verified device-specific DTB extracted from the
device. A DTB found in a firmware partition may differ from the live tree after
the bootloader applies overlays or edits memory reservations.

## Required evidence for the next platform-data update

Record the following from an A03s-specific live or verified tree:

1. Root `#address-cells` and `#size-cells`.
2. Every `/memory` node's `reg` property, decoded using those cell widths.
3. Every `/memreserve/` tuple.
4. Each direct child of `/reserved-memory`, including `reg`, `size`,
   `alignment`, `no-map`, `reusable`, and any allocation constraints.
5. `/chosen` initrd start/end, if present.
6. UART node status, compatible, reg, clock names/phandles, and pinctrl
   references. Resolve phandles to their target nodes instead of guessing
   from the numeric IDs.

For each value, keep the source node/property and whether it came from the
live tree, a partition DTB, a kernel DTB, or a synthetic test fixture.

## Safety note

The parser's structural checks are not a proof that an arbitrary pointer is
mapped, readable, or within RAM. The caller must establish a trustworthy
accessible range before dereferencing the supplied FDT. Likewise, successfully
parsing memory ranges does not make them safe destinations for a payload:
overlaps, integer overflow, reservations, and image bounds still need separate
validation before any future handoff code is enabled.
