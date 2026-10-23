#!/usr/bin/env python3
"""Build an experimental Android boot image v2 around the diagnostic AArch64 shim.

This is a research artifact, NOT a verified flashable Samsung/MediaTek image.
It optionally copies the DTB payload from a v2 reference image, but does not
preserve AVB metadata/signatures, Samsung-specific packaging, or vendor data.
"""
from __future__ import annotations

import argparse
import gzip
import struct
import sys
from pathlib import Path

PAGE_SIZE = 2048
BOOT_MAGIC = b"ANDROID!"
IMAGE_MAGIC = b"ARM\\x64"
HEADER_V2_SIZE = 1660
HEADER_V2_VERSION = 2
KERNEL_ADDR = 0x40080000
OFF_KERNEL_SIZE = 8
OFF_KERNEL_ADDR = 12
OFF_RAMDISK_SIZE = 16
OFF_SECOND_SIZE = 24
OFF_TAGS_ADDR = 32
OFF_PAGE_SIZE = 36
OFF_HEADER_VERSION = 40
OFF_RECOVERY_DTBO_SIZE = 1632
OFF_RECOVERY_DTBO_OFFSET = 1636
OFF_HEADER_SIZE = 1644
OFF_DTB_SIZE = 1648
OFF_DTB_ADDR = 1652


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def u64(buf: bytes, off: int) -> int:
    return struct.unpack_from("<Q", buf, off)[0]


def put_u32(buf: bytearray, off: int, value: int) -> None:
    struct.pack_into("<I", buf, off, value)


def align(value: int) -> int:
    return (value + PAGE_SIZE - 1) // PAGE_SIZE * PAGE_SIZE


def parse_stock(path: Path) -> tuple[bytearray, bytes]:
    raw = path.read_bytes()
    if len(raw) < PAGE_SIZE or raw[:8] != BOOT_MAGIC:
        raise ValueError(f"{path} is not an Android boot image")
    if u32(raw, OFF_PAGE_SIZE) != PAGE_SIZE:
        raise ValueError("reference image page size must be 2048")
    if u32(raw, OFF_HEADER_VERSION) != HEADER_V2_VERSION:
        raise ValueError("reference image must use legacy boot header v2")
    if u32(raw, OFF_HEADER_SIZE) < HEADER_V2_SIZE:
        raise ValueError("reference v2 header is too small")

    kernel_size = u32(raw, OFF_KERNEL_SIZE)
    ramdisk_size = u32(raw, OFF_RAMDISK_SIZE)
    second_size = u32(raw, OFF_SECOND_SIZE)
    recovery_size = u32(raw, OFF_RECOVERY_DTBO_SIZE)
    dtb_size = u32(raw, OFF_DTB_SIZE)

    kernel_off = PAGE_SIZE
    ramdisk_off = align(kernel_off + kernel_size)
    second_off = align(ramdisk_off + ramdisk_size)
    if recovery_size:
        recovery_off = u64(raw, OFF_RECOVERY_DTBO_OFFSET)
        if recovery_off < second_off or recovery_off + recovery_size > len(raw):
            raise ValueError("reference recovery_dtbo range is invalid")
        dtb_off = align(recovery_off + recovery_size)
    else:
        dtb_off = align(second_off + second_size)

    dtb = b""
    if dtb_size:
        end = dtb_off + dtb_size
        if dtb_off < PAGE_SIZE or end > len(raw):
            raise ValueError("reference DTB range is outside the image")
        dtb = raw[dtb_off:end]
        if len(dtb) < 8 or dtb[:4] not in (b"\xd0\x0d\xfe\xed", b"\xed\xfe\x0d\xd0"):
            # Samsung DTB tables can wrap entries around FDT blobs, so don't
            # reject non-FDT table headers here; the range is still preserved.
            if not dtb:
                raise ValueError("empty DTB payload")
    return bytearray(raw[:PAGE_SIZE]), dtb


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=Path("out/bootshim/Image"))
    parser.add_argument("--stock", type=Path, help="v2 reference image; its DTB payload is copied if present")
    parser.add_argument("--output", type=Path, default=Path("out/bootshim/boot-shim-experimental.img"))
    args = parser.parse_args()

    try:
        image = args.kernel.read_bytes()
        if len(image) < 0x3C or image[0x38:0x3C] != IMAGE_MAGIC:
            raise ValueError(f"{args.kernel} is not an uncompressed AArch64 Image (magic missing at 0x38)")
        # Deterministic gzip stream. Whether this device's bootloader accepts a
        # gzip-compressed raw Image must be established separately on hardware.
        kernel = gzip.compress(image, compresslevel=9, mtime=0)
        dtb = b""
        if args.stock:
            if args.output.resolve() == args.stock.resolve():
                raise ValueError("output must not overwrite the reference image")
            header, dtb = parse_stock(args.stock)
        else:
            header = bytearray(PAGE_SIZE)
            header[:8] = BOOT_MAGIC
            put_u32(header, OFF_TAGS_ADDR, 0x40000100)
            put_u32(header, OFF_HEADER_SIZE, HEADER_V2_SIZE)

        put_u32(header, OFF_KERNEL_SIZE, len(kernel))
        put_u32(header, OFF_KERNEL_ADDR, KERNEL_ADDR)
        put_u32(header, OFF_RAMDISK_SIZE, 0)  # intentionally empty ramdisk
        put_u32(header, OFF_SECOND_SIZE, 0)
        put_u32(header, OFF_PAGE_SIZE, PAGE_SIZE)
        put_u32(header, OFF_HEADER_VERSION, HEADER_V2_VERSION)
        put_u32(header, OFF_RECOVERY_DTBO_SIZE, 0)
        struct.pack_into("<Q", header, OFF_RECOVERY_DTBO_OFFSET, 0)
        put_u32(header, OFF_HEADER_SIZE, HEADER_V2_SIZE)
        put_u32(header, OFF_DTB_SIZE, len(dtb))
        # Keep the reference DTB load address when a stock template was given.
        if not args.stock:
            put_u32(header, OFF_DTB_ADDR, 0)

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("wb") as out:
            out.write(header)
            out.write(kernel)
            out.write(b"\\0" * (align(len(kernel)) - len(kernel)))
            if dtb:
                out.write(dtb)
                out.write(b"\\0" * (align(len(dtb)) - len(dtb)))

        print(f"wrote experimental image: {args.output} ({args.output.stat().st_size} bytes)")
        print(f"kernel: gzip, {len(kernel)} bytes; load address: 0x{KERNEL_ADDR:08x}")
        print(f"page size: {PAGE_SIZE}; ramdisk: empty; DTB payload: {len(dtb)} bytes")
        print("WARNING: no AVB footer/signature or Samsung-specific metadata was generated.")
        print("WARNING: gzip acceptance, DTB handoff, entry state, and bootability are unverified.")
        return 0
    except (OSError, ValueError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
