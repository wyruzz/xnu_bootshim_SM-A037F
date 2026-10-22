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
| DTB serial node candidate 1 | `serial@11020000` | Found in A03s DTB; active UART and pin routing not yet confirmed |
| DTB serial node candidate 2 | `serial@11030000` | Found in A03s DTB; active UART and pin routing not yet confirmed |
| Serial node clock names | `baud`, `bus` | DTB properties; clock phandles need full resolution |
| DRAM base and size | Unknown | Read from a validated live FDT or device-specific memory map |
| Reserved memory ranges | Unknown | Read from the A03s FDT and cross-check against runtime |
| UART pinmux / baud rate | Unknown | Must be verified for this board |
| EL entry level / MMU state | Unknown | Must be measured by the shim on hardware |

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

- The exact A03s FDT `/memory` reg values and all `reserved-memory` children.
- The full `serial@11020000` and `serial@11030000` properties, including
  resolved clock phandles and pinctrl references.
- The shim's observed entry EL, `CurrentEL`, `SCTLR_ELx`, `DAIF`, and
  supplied FDT pointer on hardware.
- The existing project's linker script and image packaging assumptions, so
  the payload address can be checked against the actual load/entry contract.
