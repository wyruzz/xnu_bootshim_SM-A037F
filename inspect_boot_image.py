#!/usr/bin/env python3
"""Read-only inspector for legacy Android boot images (header v0-v2).

This tool reports standard component offsets and an AVB footer, if present.
It does not unpack payloads, modify the image, validate an AVB signature, or
interpret undocumented MediaTek/Samsung fields.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

BOOT_MAGIC = b"ANDROID!"
AVB_FOOTER_MAGIC = b"AVBf"
AVB_FOOTER_SIZE = 64

def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]

def u64(buf: bytes, off: int) -> int:
    return struct.unpack_from("<Q", buf, off)[0]

def align(value: int, boundary: int) -> int:
    if boundary <= 0:
        raise ValueError("alignment must be positive")
    return (value + boundary - 1) // boundary * boundary

def inspect(path: Path) -> dict:
    size = path.stat().st_size
    with path.open("rb") as f:
        header = f.read(2048)
        if len(header) < 44 or header[:8] != BOOT_MAGIC:
            raise ValueError("not an Android boot image (ANDROID! magic missing)")
        page_size = u32(header, 36)
        version = u32(header, 40)
        if version > 2:
            raise ValueError(
                f"header version {version} is not supported by this legacy v0-v2 inspector"
            )
        if page_size < 512 or page_size > 65536 or page_size & (page_size - 1):
            raise ValueError(f"invalid or unsupported page size: {page_size}")
        if size < page_size:
            raise ValueError("file is smaller than its declared header page")

        kernel_size = u32(header, 8)
        ramdisk_size = u32(header, 16)
        second_size = u32(header, 24)
        kernel_off = page_size
        ramdisk_off = kernel_off + align(kernel_size, page_size)
        second_off = ramdisk_off + align(ramdisk_size, page_size)
        cursor = second_off + align(second_size, page_size)
        components = {
            "kernel": {"offset": kernel_off, "size": kernel_size},
            "ramdisk": {"offset": ramdisk_off, "size": ramdisk_size},
            "second": {"offset": second_off, "size": second_size},
        }
        recovery_size = dtb_size = 0
        if version >= 1:
            recovery_size = u32(header, 1632)
            recovery_offset_field = u64(header, 1636)
            # v1+ provides an explicit recovery_dtbo_offset. Report it and
            # use it for bounds reporting instead of assuming the packed cursor.
            if recovery_size:
                recovery_off = recovery_offset_field or cursor
                components["recovery_dtbo"] = {
                    "offset": recovery_off, "size": recovery_size,
                    "header_offset": recovery_offset_field,
                }
                cursor = max(cursor, recovery_off + align(recovery_size, page_size))
        if version >= 2:
            dtb_size = u32(header, 1648)
            components["dtb"] = {"offset": cursor, "size": dtb_size}

        for name, item in components.items():
            end = item["offset"] + item["size"]
            item["end"] = end
            item["within_file"] = end <= size

        result = {
            "file": str(path),
            "file_size": size,
            "format": "Android legacy boot image",
            "header_version": version,
            "page_size": page_size,
            "kernel_addr": f"0x{u32(header, 12):08x}",
            "ramdisk_addr": f"0x{u32(header, 20):08x}",
            "second_addr": f"0x{u32(header, 28):08x}",
            "tags_addr": f"0x{u32(header, 32):08x}",
            "os_version_field": u32(header, 44) if len(header) >= 48 else None,
            "components": components,
            "notes": [
                "Offsets describe standard legacy Android components only.",
                "Unknown vendor/MediaTek fields are not decoded.",
                "An AVB footer is metadata, not proof that the image signature verifies.",
            ],
        }
        f.seek(max(0, size - AVB_FOOTER_SIZE))
        footer = f.read(AVB_FOOTER_SIZE)
        if len(footer) == AVB_FOOTER_SIZE and footer[:4] == AVB_FOOTER_MAGIC:
            major, minor = struct.unpack_from("<II", footer, 4)
            original_size, vbmeta_offset, vbmeta_size = struct.unpack_from("<QQQ", footer, 12)
            result["avb_footer"] = {
                "version": f"{major}.{minor}",
                "original_image_size": original_size,
                "vbmeta_offset": vbmeta_offset,
                "vbmeta_size": vbmeta_size,
                "footer_at": size - AVB_FOOTER_SIZE,
                "vbmeta_within_file": vbmeta_offset <= size and vbmeta_size <= size - vbmeta_offset,
                "note": "Presence and bounds only; use avbtool to inspect descriptors and verify signatures.",
            }
        else:
            result["avb_footer"] = None
        return result

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="boot image to inspect (read-only)")
    parser.add_argument("--compact", action="store_true", help="print compact JSON")
    args = parser.parse_args()
    try:
        result = inspect(args.image)
    except (OSError, ValueError, struct.error) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=None if args.compact else 2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
