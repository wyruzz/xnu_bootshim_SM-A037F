#!/usr/bin/env python3
"""Pack a raw AArch64 Linux Image into a legacy Android boot image v2.

This is an experimental container writer, not a Samsung/MediaTek boot-image
reconstructor. --stock accepts only a 2048-byte-page v2 image and copies its
first page as a template. It does not copy payloads, vendor data outside that
page, AVB metadata, or signatures.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

PAGE_SIZE = 2048
BOOT_MAGIC = b"ANDROID!"
IMAGE_MAGIC = b"ARM\x64"
HEADER_V2_SIZE = 1660
HEADER_V2_VERSION = 2
KERNEL_ADDR_DEFAULT = 0x40080000
TAGS_ADDR_DEFAULT = 0x40000100
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
        raise ValueError(f"{path} is not an Android boot image with a 2048-byte header page")
    page_size = u32(raw, OFF_PAGE_SIZE)
    if page_size != PAGE_SIZE:
        raise ValueError(
            f"template page_size is {page_size}, expected {PAGE_SIZE}; "
            "refusing to reinterpret vendor header offsets"
        )
    version = u32(raw, OFF_HEADER_VERSION)
    # We write v2-only fields below. Do not reinterpret v0/v1 reserved space
    # or unknown newer header layouts as v2.
    if version != HEADER_V2_VERSION:
        raise ValueError(
            f"template header version is {version}, expected v2; refusing to "
            "overwrite fields whose meaning may differ"
        )
    if u32(raw, OFF_HEADER_SIZE) < HEADER_V2_SIZE:
        raise ValueError("template v2 header_size is smaller than 1660 bytes")
    return bytearray(raw[:PAGE_SIZE])


def make_header(kernel_size: int, stock: Path | None) -> bytearray:
    if kernel_size <= 0 or kernel_size > 0xFFFFFFFF:
        raise ValueError(f"kernel size is outside the v2 header's 32-bit range: {kernel_size}")
    if stock:
        header = stock_header(stock)
    else:
        header = bytearray(PAGE_SIZE)
        header[:8] = BOOT_MAGIC
        put_u32(header, OFF_KERNEL_ADDR, KERNEL_ADDR_DEFAULT)
        put_u32(header, OFF_TAGS_ADDR, TAGS_ADDR_DEFAULT)

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
    put_u32(header, OFF_DTB_ADDR, 0)
    return header


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kernel", type=Path, default=Path("out/bootshim/Image"),
        help="raw AArch64 Image (default: out/bootshim/Image)",
    )
    parser.add_argument(
        "--stock", type=Path,
        help="optional v2 image; copies only its first 2048-byte header page",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("boot.img"),
        help="output file (default: boot.img)",
    )
    args = parser.parse_args()

    try:
        kernel = args.kernel.read_bytes()
        if len(kernel) < 0x3C:
            raise ValueError(f"kernel file is too short to contain the AArch64 Image magic: {args.kernel}")
        if kernel[0x38:0x3C] != IMAGE_MAGIC:
            raise ValueError(
                f"{args.kernel} does not contain the AArch64 Image magic at offset 0x38; "
                "expected ARM\\x64"
            )
        if args.stock and args.output.resolve() == args.stock.resolve():
            raise ValueError("output path must not overwrite the header-template image")

        header = make_header(len(kernel), args.stock)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("wb") as out:
            out.write(header)
            out.write(kernel)
            out.write(b"\0" * (align(len(kernel)) - len(kernel)))
        print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
        print(f"kernel: {len(kernel)} bytes; page size: {PAGE_SIZE}; header version: 2")
        print("ramdisk and DTB are empty; no AVB footer/signature was generated")
        if args.stock:
            print(f"copied header template from {args.stock}; vendor data outside its first page was not copied")
        else:
            print("used a generic header; no MTK metadata was inferred")
        return 0
    except (OSError, ValueError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
