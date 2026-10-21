# SPDX-License-Identifier: MIT
"""Host checks for the fail-closed SM-A037F diagnostic milestone."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Range(ctypes.Structure):
    _fields_ = [("base", ctypes.c_uint64), ("size", ctypes.c_uint64)]


class Info(ctypes.Structure):
    _fields_ = [("bytes", ctypes.c_uint32), ("memory_count", ctypes.c_uint),
                ("reserved_count", ctypes.c_uint), ("memory", Range * 8),
                ("reserved", Range * 64), ("initrd_start", ctypes.c_uint64),
                ("initrd_end", ctypes.c_uint64)]


class Plan(ctypes.Structure):
    _fields_ = [("adt_pa", ctypes.c_uint64), ("args_pa", ctypes.c_uint64),
                ("top", ctypes.c_uint64), ("entry_pa", ctypes.c_uint64)]


class Video(ctypes.Structure):
    _fields_ = [("base", ctypes.c_uint64), ("display", ctypes.c_uint64),
                ("rowbytes", ctypes.c_uint64), ("width", ctypes.c_uint64),
                ("height", ctypes.c_uint64), ("depth", ctypes.c_uint64)]


def payload():
    return bytes(1024)


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="sm-a037f-stub-test-")
        lib = Path(cls.temp.name) / "stubs.so"
        subprocess.run([
            "cc", "-shared", "-fPIC", "-O2", "-Wall", "-Wextra", "-Werror",
            str(ROOT / "handoff.c"), str(ROOT / "adt.c"), str(ROOT / "rng.c"),
            "-o", str(lib),
        ], check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.handoff_validate.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64,
            ctypes.POINTER(Info), ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_uint64, ctypes.POINTER(Plan),
        ]
        cls.lib.handoff_validate.restype = ctypes.c_int
        cls.lib.xnu_make_adt.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_uint32,
        ]
        cls.lib.xnu_make_adt.restype = ctypes.c_size_t
        cls.lib.mt8167_random_seed.argtypes = [ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint32]
        cls.lib.mt8167_random_seed.restype = ctypes.c_int
        cls.lib.handoff_video_setup.argtypes = [
            ctypes.POINTER(Video), ctypes.POINTER(Info), ctypes.c_void_p,
        ]
        cls.lib.handoff_video_setup.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_handoff_rejects_payload(self):
        fdt = Info()
        plan = Plan()
        data = ctypes.create_string_buffer(payload())
        self.assertEqual(self.lib.handoff_validate(
            data, len(payload()), 0x47000000, ctypes.byref(fdt),
            0x4e000000, 0x40080000, 0x400a0000, ctypes.byref(plan)), -1)

    def test_adt_is_not_fabricated_for_donor_board(self):
        out = ctypes.create_string_buffer(16384)
        self.assertEqual(self.lib.xnu_make_adt(
            out, len(out), ctypes.create_string_buffer(payload()), 13000000), 0)

    def test_rng_fails_without_mmio_and_clears_output(self):
        seed = (ctypes.c_ubyte * 64)(*([0xA5] * 64))
        self.assertEqual(self.lib.mt8167_random_seed(seed, 13000000), -1)
        self.assertEqual(bytes(seed), bytes(64))

    def test_video_setup_never_writes_hardware(self):
        video = Video(1, 2, 3, 4, 5, 6)
        fdt = Info()
        self.assertEqual(self.lib.handoff_video_setup(
            ctypes.byref(video), ctypes.byref(fdt), None), 0)
        self.assertEqual(bytes(video), bytes(ctypes.sizeof(Video)))


if __name__ == "__main__":
    unittest.main()
