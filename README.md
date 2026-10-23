# Samsung Galaxy A03s SM-A037F diagnostic boot shim

**Status: diagnostic-only; XNU boot is not implemented or hardware-tested.**

This branch targets Samsung Galaxy A03s **SM-A037F** (MediaTek MT6765 /
Helio P35). The current milestone is a diagnostic-only AArch64 image, not an
XNU bootloader.

## Current behavior

- Prints entry registers and CPU/system-register diagnostics over the inherited
  MediaTek UART at `0x11002000` (the `reg` base reported by the captured A03s
  Device Tree for `serial@11020000`; UART output is still unverified on hardware).
- If entered at EL2, reports EL2 state and stops without changing exception
  level or inherited MMU/cache/timer/clock state.
- If entered at EL1, validates and reports the supplied flattened device tree
  (DRAM, reserved ranges and initrd fields), then stops.
- Does not call `handoff_boot()`, load XNU, write storage, or intentionally
  change power/watchdog configuration.

UART output requires a compatible external serial connection; it may not be
visible through Android ADB. The inherited watchdog may reset the device after
the shim stops.

## Build

On Linux with an AArch64 cross-toolchain:

```sh
CROSS_COMPILE=aarch64-linux-gnu- ./build.sh
```

On macOS with Clang and MacPorts `aarch64-elf-binutils`:

```sh
CROSS_COMPILE=aarch64-elf- SHIM_OUT="$PWD/out/bootshim-macos" ./build-macos.sh
```

Both scripts link executable code as RX and writable state as RW, reject
writable-and-executable ELF load segments, validate the AArch64 Image magic
and image-size field, and emit `build.json` with a SHA-256 digest. A GitHub
Actions workflow builds the image on each push and pull request.

Outputs are a raw diagnostic `Image`, `shim.elf`, `symbols.txt`, and
`build.json`. A successful host build only confirms the compile/link and
format checks; it does not prove that the image is safe or functional on the
phone. **The raw `Image` is not a complete Samsung boot image and must not be
flashed directly.**

## Packaging a diagnostic boot image

After building the shim, create a legacy Android boot image v2 with 2048-byte
pages:

```sh
python3 pack_boot_v2.py
```

This reads `out/bootshim/Image` and writes `boot.img`. To retain the first
header page from a stock image (including vendor/MTK metadata stored in that
page), pass it explicitly:

```sh
python3 pack_boot_v2.py --stock stock_boot.img --output boot.img
```

The packer replaces the kernel payload and clears the ramdisk, second-stage,
recovery-DTBO and DTB sizes; it does not copy initrd or DTB data. MTK layouts
are vendor-specific: the script preserves the stock header page byte-for-byte
before updating standard Android header fields, but it cannot reconstruct MTK
metadata located elsewhere in the stock image or guarantee compatibility with
the Samsung boot chain. Without `--stock`, it creates a generic v2 header and
does not invent MTK metadata. This is a packaging utility for host-side
experiments, **not confirmation that the resulting image is flashable or safe
to boot on the phone**.

## Safety boundary in this milestone

The legacy build still compiles the ADT, handoff, and RNG interface modules,
but they are fail-closed stubs: ADT generation returns failure, handoff
validation rejects all payloads, framebuffer setup does nothing, and the RNG
stub performs no register access. This prevents the previous A04BR3/MT8167
addresses and board metadata from being used accidentally.

`start.S` accepts EL1 or EL2 but does not implement an EL2-to-EL1 transition.
Both paths are diagnostic-only. The linker and build scripts enforce
non-RWX ELF load segments; this is a build-safety improvement, not a kernel
handoff implementation.

## Remaining blockers

These are not merely build errors and cannot be responsibly marked fixed without
target-specific implementation and evidence:

- Target-specific XNU handoff ABI, Apple device tree/ADT, payload loading and
  verified memory layout.
- A validated EL2-to-EL1 transition policy, if required by the eventual entry
  contract.
- UART initialization/address mapping and FDT diagnostics tested on physical
  SM-A037F hardware.
- Samsung/MediaTek boot-image packaging and a verified recovery/boot procedure.
- End-to-end kernel execution tests on the actual phone.

Do not treat this image as flash-ready. Keep testing host-side until the device
entry contract, memory map, packaging, and recovery path have been verified.
