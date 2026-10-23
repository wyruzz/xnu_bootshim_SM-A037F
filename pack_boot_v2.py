#!/usr/bin/env python3
"""Pack a raw AArch64 Image into a legacy Android boot image v2 (2048-byte pages).

Optional --stock boot.img uses the stock image's first 2048-byte page as a
template. This preserves vendor/MTK metadata stored in that page while replacing
the kernel payload and clearing ramdisk, second-stage and DTB sizes. It does not
copy the stock kernel or any initrd/DTB payload.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

PAGE_SIZE = 2048
BOOT_MAGIC = b"ANDROID!"
HEADER_V2_SIZE = 1660
HEADER_V2_VERSION = 2
KERNEL_ADDR_DEFAULT = 0x40080000
TAGS_ADDR_DEFAULT = 0x40000100
# Android boot header v0/v1/v2 field offsets.
OFF_KERNEL_SIZE = 8
OFF_KERNEL_ADDR = 12
OFF_RAMDISK_SIZE = 16
OFF_RAMDISK_ADDR = 20
OFF_SECOND_SIZE = 24
OFF_SECOND_ADDR = 28
OFF_TAGS_ADDR = 32
OFF_PAGE_SIZE = 36
OFF_HEADER_VERSION = 40
OFF_OS_VERSION = 44
OFF_RECOVERY_DTBO_SIZE = 1632
OFF_RECOVERY_DTBO_OFFSET = 1636
OFF_HEADER_SIZE = 1644
OFF_DTB_SIZE = 1648
OFF_DTB_ADDR = 1652


def u32(buf: bytes, offset: int) -> int:
    return struct.unpack_from("<I", buf, offset)[0]


def put_u32(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<I", buf, offset, value)


def put_u64(buf: bytearray, offset: int, value: int) -> None:
    struct.pack_into("<Q", buf, offset, value)


def align(value: int, boundary: int = PAGE_SIZE) -> int:
    return (value + boundary - 1) // boundary * boundary


def stock_header(path: Path) -> bytearray:
    raw = path.read_bytes()
    if len(raw) < PAGE_SIZE or raw[:8] != BOOT_MAGIC:
        raise ValueError(f"{path} is not a legacy Android boot image with a 2048-byte header page")
    page_size = u32(raw, OFF_PAGE_SIZE)
    if page_size != PAGE_SIZE:
        raise ValueError(
            f"stock page_size is {page_size}, expected {PAGE_SIZE}; refusing to "
            "reinterpret vendor header offsets"
        )
    version = u32(raw, OFF_HEADER_VERSION)
    if version > 2:
        raise ValueError(f"stock header version {version} is newer than v2")
    # Preserve the entire stock header page. MTK-specific metadata is not
    # standardized; retaining the page is safer than guessing its layout.
    return bytearray(raw[:PAGE_SIZE])


def make_header(kernel_size: int, stock: Path | None) -> bytearray:
    if stock:
        header = stock_header(stock)
    else:
        header = bytearray(PAGE_SIZE)
        header[:8] = BOOT_MAGIC
        put_u32(header, OFF_KERNEL_ADDR, KERNEL_ADDR_DEFAULT)
        put_u32(header, OFF_TAGS_ADDR, TAGS_ADDR_DEFAULT)
        # Empty board name/cmdline and default OS version are intentional.

    # Standard Android v2 fields. Keep stock load addresses, board name,
    # cmdline and OS version when supplied; replace component sizes/format.
    header[:8] = BOOT_MAGIC
    put_u32(header, OFF_KERNEL_SIZE, kernel_size)
    put_u32(header, OFF_RAMDISK_SIZE, 0)
    put_u32(header, OFF_SECOND_SIZE, 0)
    put_u32(header, OFF_PAGE_SIZE, PAGE_SIZE)
    put_u32(header, OFF_HEADER_VERSION, HEADER_V2_VERSION)
    put_u32(header, OFF_RECOVERY_DTBO_SIZE, 0)
    put_u64(header, OFF_RECOVERY_DTBO_OFFSET, 0)
    put_u32(header, OFF_HEADER_SIZE, HEADER_V2_SIZE)
    put_u32(header, OFF_DTB_SIZE, 0)
    # Do not advertise a DTB address when no DTB is packaged.
    put_u32(header, OFF_DTB_ADDR, 0)
    return header


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack out/bootshim/Image as Android boot image v2 (2048-byte pages)."
    )
    parser.add_argument(
        "--kernel", type=Path, default=Path("out/bootshim/Image"),
        help="raw kernel Image (default: out/bootshim/Image)",
    )
    parser.add_argument(
        "--stock", type=Path,
        help="optional stock boot.img; preserves its first header page including any MTK metadata",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("boot.img"),
        help="output file (default: boot.img)",
    )
    args = parser.parse_args()

    try:
        kernel = args.kernel.read_bytes()
        if not kernel:
            raise ValueError(f"kernel image is empty: {args.kernel}")
        # AArch64 Linux Image magic is little-endian 0x644d5241 ("ARM\x64")
        # at offset 0x38. Warn rather than reject, to permit diagnostic payloads.
        if len(kernel) >= 0x3C and kernel[0x38:0x3C] != b"ARM\x64":
            print("warning: input does not contain the usual AArch64 Image magic at 0x38", file=sys.stderr)
        header = make_header(len(kernel), args.stock)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("wb") as out:
            out.write(header)
            out.write(kernel)
            out.write(b"\0" * (align(len(kernel)) - len(kernel)))
        print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
        print(f"kernel: {len(kernel)} bytes; page size: {PAGE_SIZE}; header version: 2")
        if args.stock:
            print(f"preserved stock header page from {args.stock}; ramdisk and DTB are empty")
        else:
            print("no stock header supplied; emitted a generic v2 header (no MTK metadata)")
        return 0
    except (OSError, ValueError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
