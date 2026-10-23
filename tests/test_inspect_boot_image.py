import struct
import tempfile
import unittest
from pathlib import Path

import inspect_boot_image


def put32(buf: bytearray, off: int, value: int) -> None:
    struct.pack_into("<I", buf, off, value)


class InspectBootImageTests(unittest.TestCase):
    def make_image(self, with_footer: bool = False) -> bytes:
        page = 2048
        header = bytearray(page)
        header[:8] = b"ANDROID!"
        put32(header, 8, 3)       # kernel size
        put32(header, 12, 0x40080000)
        put32(header, 16, 2)     # ramdisk size
        put32(header, 20, 0x51B00000)
        put32(header, 24, 0)      # second size
        put32(header, 36, page)
        put32(header, 40, 2)     # header v2
        put32(header, 1648, 0)   # DTB size
        image = bytes(header) + b"KER" + bytes(page - 3) + b"RD" + bytes(page - 2)
        if with_footer:
            footer = bytearray(64)
            footer[:4] = b"AVBf"
            struct.pack_into("<IIQQQ", footer, 4, 1, 0, len(image), len(image), 0)
            image += bytes(128) + bytes(64)  # placeholder vbmeta region and footer
            image = image[:-64] + bytes(64)
            image = image[:-64] + bytes(64)
            # Put the footer at the end of the full file.
            image = image[:-64] + footer
        return image

    def test_reports_v2_component_offsets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "boot.img"
            path.write_bytes(self.make_image())
            report = inspect_boot_image.inspect(path)
        self.assertEqual(report["header_version"], 2)
        self.assertEqual(report["components"]["kernel"]["offset"], 2048)
        self.assertEqual(report["components"]["ramdisk"]["offset"], 4096)
        self.assertEqual(report["components"]["ramdisk"]["size"], 2)
        self.assertIsNone(report["avb_footer"])

    def test_detects_avb_footer_magic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "boot.img"
            path.write_bytes(self.make_image(with_footer=True))
            report = inspect_boot_image.inspect(path)
        self.assertIsNotNone(report["avb_footer"])
        self.assertEqual(report["avb_footer"]["version"], "1.0")


if __name__ == "__main__":
    unittest.main()
