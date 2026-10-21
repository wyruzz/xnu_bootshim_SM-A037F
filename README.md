# Samsung Galaxy A03s SM-A037F diagnostic boot shim

**Status: source adaptation in progress; not yet built or tested on hardware.**

This branch targets Samsung Galaxy A03s **SM-A037F** (MediaTek MT6765 /
Helio P35). The current milestone is a diagnostic-only AArch64 image, not an
XNU bootloader.

## Current behavior

- Prints entry registers and CPU/system-register diagnostics over the inherited
  MediaTek UART at `0x11020000`.
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

The existing `build.sh` is intentionally unchanged. Build with a working
AArch64 bare-metal-capable toolchain, for example:

```sh
CROSS_COMPILE=/path/to/aarch64-linux-gnu- ./build.sh
```

Outputs are written to `../out/bootshim` by default. A successful host build
only confirms that the source linked and the image-format assertions passed;
it does not prove that the image is safe or functional on the phone.

## Safety boundary in this milestone

The legacy build still compiles the ADT, handoff, and RNG interface modules,
but they are fail-closed stubs: ADT generation returns failure, handoff
validation rejects all payloads, framebuffer setup does nothing, and the RNG
stub performs no register access. This prevents the previous A04BR3/MT8167
addresses and board metadata from being used accidentally.

`start.S` no longer contains the donor EL2-to-EL1 transition. Both EL1 and
EL2 paths are diagnostic-only. The build script is unchanged.

## Not yet implemented or verified

- Target-specific XNU handoff, Apple device tree/ADT, and memory layout.
- EL2-to-EL1 transition on the SM-A037F.
- UART output and FDT diagnostics on physical hardware.
- Boot-image packaging, flashing, and kernel execution.

Do not treat this image as flash-ready. First build and inspect the output,
then validate the entry behavior with an appropriate recovery path available.

