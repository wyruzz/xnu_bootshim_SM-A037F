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
register properties, or prove that an FDT pointer is mapped and safe to read.
Dynamic `/reserved-memory` children with `size` and no `reg` are now reported
separately with their size, alignment, and allocation constraints; they are not
converted into fixed address ranges because their actual allocated bases are
not encoded by those properties.

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

## Findings from the uploaded A03s diagnostic archive

The archive contains `root/a03s-dt.tar`, a snapshot of Device Tree property
files, while `fdt-path.txt` reports `/sys/firmware/fdt` as a 195626-byte file.
The raw FDT binary is not separately included, so the captured property tree
should not be assumed byte-for-byte identical to the pointer passed to the shim.

Decoded values from the property snapshot:

- Root `#address-cells = 2`, `#size-cells = 2`.
- `/memory/reg = <0 0x40000000 1 0>`: base `0x40000000`, size `0x100000000` (4 GiB).
- `/chosen/linux,initrd-start = 0x51b00000`; `linux,initrd-end = 0x51c61b0d`.
- Node `serial@11020000` has `reg = <0 0x11002000 0 0x1000>`; node `serial@11030000` has `reg = <0 0x11003000 0 0x1000>`. The first node's name and register base differ; use `reg` as the register-bank address.
- UART clock names are `baud`, `bus`; node 1 has `clocks = <0x24 0x25 0x16>`, node 2 has `clocks = <0x24 0x25 0x17>`. The provider properties show `clk26m` (`0x24`) has `#clock-cells = 0`, while `infracfg_ao` (`0x25`) has `#clock-cells = 1`; therefore `0x16` / `0x17` are clock-index arguments for `infracfg_ao`, not separate phandles.
- The UART nodes in this snapshot have no `status` or `pinctrl-0` property. Absence of `status` normally means enabled under DT conventions, but does not prove the UART pins are routed or that the early shim inherits working UART state.
- `/reserved-memory` contains numerous fixed `reg` reservations, including regions for ATF, TEE, framebuffer, boot arguments, logs, modem and SCP. These must be treated as unavailable unless a later design explicitly proves otherwise.
- Six children use dynamic `size` requests without `reg`: SSMR/CMA (`0x18000000`), Wi-Fi (`0x300000`), SSPM share (`0x510000`), connectivity (`0x440000`), SCP share (`0x300000`), and ION heap (`0x5000`). Their `alignment` and `alloc-range`/`alloc-ranges` properties constrain allocation, but the snapshot does not give actual assigned bases. The parser now reports these separately and does not treat them as fixed ranges.

The diagnostic source previously used `UART_BASE = 0x11020000`, which conflicts
with the captured first UART node's `reg` base. It has been corrected to
`0x11002000`; hardware output still needs to be checked on the device.

## Safety note

The parser's structural checks are not a proof that an arbitrary pointer is
mapped, readable, or within RAM. The caller must establish a trustworthy
accessible range before dereferencing the supplied FDT. Likewise, successfully
parsing memory ranges does not make them safe destinations for a payload:
overlaps, integer overflow, reservations, and image bounds still need separate
validation before any future handoff code is enabled.
