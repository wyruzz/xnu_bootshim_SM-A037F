# SM-A037F platform data and MT6765 reference notes

Status: initial data inventory; not a hardware-validated memory map.

This file deliberately separates values observed on the Samsung Galaxy A03s
(SM-A037F) from values used by the Xiaomi MT6765 EDK2 reference port. Do not
treat reference-port constants as Samsung platform constants without checking
the A03s device tree, bootloader behavior, and memory reservations.

## Samsung Galaxy A03s observations

| Item | Value | Evidence / status |
|---|---|---|
| Device codename | `a03s` | Android `ro.product.device` |
| Build display ID | `A037FXXS8CYE1` | Android `ro.build.display.id` |
| Kernel boot-image load address field | `0x40080000` | Android boot image header; not proof of shim entry address |
| Kernel size in boot-image header | `12409268` bytes | Android boot image header |
| Boot partition | `/dev/block/mmcblk0p37` | Device partition symlink dump |
| DTBO partition | `/dev/block/mmcblk0p12` | Device partition symlink dump |
| VBMeta partition | `/dev/block/mmcblk0p13` | Device partition symlink dump |
| Recovery partition | `/dev/block/mmcblk0p38` | Device partition symlink dump |
| DTB serial node 1 | node `serial@11020000`; `reg` base `0x11002000`, size `0x1000` | A03s live device-tree property dump; node label differs from `reg` address |
| DTB serial node 2 | node `serial@11030000`; `reg` base `0x11003000`, size `0x1000` | A03s live device-tree property dump |
| UART clock names | `baud`, `bus` | `clk26m` phandle `0x24` has zero clock cells; `infracfg_ao` phandle `0x25` has one clock cell, so `0x16` / `0x17` are provider arguments, not phandles |
| DRAM base and size | base `0x40000000`, size `0x100000000` (4 GiB) | `/memory/reg` decoded with root `#address-cells = 2`, `#size-cells = 2` |
| Reserved memory ranges | Multiple fixed ranges, including ATF/TEE, framebuffer, boot arguments, logs, modem and SCP regions | `/reserved-memory/*/reg` in captured device-tree property tree; see `docs/FDT-EXTRACTION.md` |
| Initrd range | `0x51B00000` to `0x51C61B0D` (end address as encoded) | `/chosen/linux,initrd-start` and `linux,initrd-end` |
| UART pinmux / effective baud | Not confirmed | UART nodes have no `pinctrl-0` property in this capture; kernel command line says `console=ttyS0,921600n1`, but this alone does not prove shim-time pin state |
| EL entry level / MMU state | Unknown | Must be measured by the shim on hardware |

## A03s diagnostic capture notes

The uploaded `a03s-diagnostics.zip` contains `root/a03s-dt.tar`, a snapshot of
Device Tree property files. `fdt-path.txt` separately reports `/sys/firmware/fdt`
with size 195626 bytes; the raw binary FDT itself is not present as a standalone
file in this archive. The extracted property tree reports root `#address-cells`
and `#size-cells` as 2 each, model `MT6765V/WB`, and compatible
`mediatek,MT6765`.

Important UART detail: both nodes use compatible strings `mediatek,mt6758-uart`
and `mediatek,mt6577-uart`. The first node is named `serial@11020000`, but its
`reg` property explicitly encodes base `0x11002000` and size `0x1000`. The
shim's old `UART_BASE=0x11020000` disagreed with that hardware property and has
been corrected to `0x11002000`. This confirms the register base from the
captured tree, not that external serial pins are exposed or that UART output
will work at shim entry. The live bootargs include `console=ttyS0,921600n1`
and `mtk_printk_ctrl.disable_uart=1`; these are useful clues, not proof of the
inherited UART configuration.

## MT6765 reference-port values (not A03s settings)

Source fork: https://github.com/wyruzz/edk2-mt6765

| Item | Reference value | Source / interpretation |
|---|---|---|
| UEFI payload base passed to shim | `0x50000000` | `build_bootshim.sh`: `UEFI_BASE=0x50000000` |
| UEFI payload size passed to shim | `0x00200000` | `build_bootshim.sh`: `UEFI_SIZE=0x00200000` |
| Shim payload relocation | Copy to `UEFI_BASE` unless already there | `BootShim/BootShim.S`; reference implementation behavior, not a device memory map |
| UART address | Not adopted | Must verify reference source and Samsung DTB before using |

The reference shim's `UEFI_BASE` is a build-time destination for that port's
UEFI payload. It does not by itself prove that the address is safe or reserved
on the SM-A037F.

## Porting rules

1. Keep observed Samsung values separate from reference constants.
2. Do not hardcode DRAM size, stack, exception-vector, framebuffer, or UEFI
   payload addresses until they are backed by A03s-specific evidence.
3. Prefer runtime FDT parsing for memory and reserved-memory ranges where the
   boot environment supplies a valid FDT.
4. Before copying a payload, validate its destination range against DRAM bounds
   and reserved ranges, and reject overflow or overlap.
5. Record the source file/property and the validation method for every new
   hardware constant.

## Next data to extract

- The exact FDT pointer supplied to the shim and whether it points to the same
  tree represented by the captured sysfs property snapshot.
- Resolve the UART clock phandles and identify board pin routing / inherited
  UART state; the current property snapshot does not establish pinmux state.
- The shim's observed entry EL, `CurrentEL`, `SCTLR_ELx`, `DAIF`, and
  supplied FDT pointer on hardware.
- The existing project's linker script and image packaging assumptions, so
  the payload address can be checked against the actual load/entry contract.
