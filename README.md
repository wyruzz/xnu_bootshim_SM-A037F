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

### Optional physical-RAM diagnostic log

`shim.c` contains an opt-in fixed-address log buffer. It records event IDs for
shim entry, exception-vector entry, FDT validation and the diagnostic stop.
The default build leaves this feature disabled. To enable it, pass
`SHIM_RAM_LOG_PHYS_ADDR=0x...` to `build-macos.sh`; **only do this after
validating and reserving that physical range for the shim on the exact device
and firmware**. An arbitrary address can corrupt live memory. The current code
does not verify that a watchdog was disabled, so it deliberately does not log a
`watchdog_disabled` success event.

This log is ordinary DRAM, not persistent storage. A reset, bootloader, or
recovery kernel may clear or overwrite it. TWRP's file manager and ordinary
`dd` commands do not inherently read physical RAM; a separate, trusted
physical-memory read mechanism is required. No RAM address is configured by
default, and this feature has not been validated on hardware.


Outputs are a raw diagnostic `Image`, `shim.elf`, `symbols.txt`, and
`build.json`. A successful host build only confirms the compile/link and
format checks; it does not prove that the image is safe or functional on the
phone. **The raw `Image` is not a complete Samsung boot image and must not be
flashed directly.**

## Read-only boot image inspection

Use `inspect_boot_image.py` to report standard component offsets for legacy
Android boot image header versions 0–2 and detect a footer at the end of the
file. It does not modify the input:

```sh
python3 inspect_boot_image.py boot.img
python3 inspect_boot_image.py boot.img --compact
```

The report is a structural inventory, not an AVB signature verification.
Unknown Samsung/MediaTek fields are deliberately not interpreted. Use
`avbtool.py info_image --image boot.img` to inspect AVB descriptors; that
command also does not by itself prove the device will accept a modified image.

## Packaging a diagnostic boot image

After building the shim, the experimental `pack_boot_v2.py` can create a
legacy Android boot image v2 with 2048-byte pages:

```sh
python3 pack_boot_v2.py
```

This reads `out/bootshim/Image` and writes `boot.img`. The packer now rejects
inputs without the AArch64 Linux Image magic at offset `0x38`. The optional
`--stock` argument accepts only a legacy v2 image with 2048-byte pages and a
valid minimum v2 header size; it copies the first page as a template, but does
not copy the original kernel, ramdisk, DTB, or arbitrary vendor data stored
elsewhere in the image. It then clears the standard ramdisk, second-stage,
recovery-DTBO and DTB size fields. The output path may not overwrite the
template image.

This is **not** a generic Samsung image reconstruction method. MTK layouts
are vendor-specific, and preserving a header page does not preserve or
regenerate AVB metadata/signatures. The packer must be treated as experimental
until its output layout is compared with a known-good image for the exact
firmware and the device's boot-chain requirements are understood. Do not
treat the output as flash-ready.

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
