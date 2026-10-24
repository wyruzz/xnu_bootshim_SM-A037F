# SPDX-License-Identifier: MIT
"""Host checks for the fail-closed SM-A037F diagnostic milestone."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def payload():
    """Minimal legacy fixture retained for import compatibility with skipped tests."""
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
        cls.lib.handoff_boot.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
        cls.lib.handoff_boot.restype = ctypes.c_char_p
        cls.lib.xnu_make_adt.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_uint32,
        ]
        cls.lib.xnu_make_adt.restype = ctypes.c_size_t
        cls.lib.mt8167_random_seed.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint32,
        ]
        cls.lib.mt8167_random_seed.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_xnu_handoff_is_explicitly_disabled(self):
        result = self.lib.handoff_boot(None, 0)
        self.assertEqual(
            result,
            b"XNU_HANDOFF_DISABLED_UNTIL_MMU_AND_BOOT_ABI_ARE_DEFINED",
        )

    def test_adt_is_not_fabricated_for_donor_board(self):
        out = ctypes.create_string_buffer(16384)
        payload = ctypes.create_string_buffer(1024)
        self.assertEqual(
            self.lib.xnu_make_adt(out, len(out), payload, 13000000), 0,
        )

    def test_rng_fails_without_mmio_and_clears_output(self):
        seed = (ctypes.c_ubyte * 64)(*([0xA5] * 64))
        self.assertEqual(self.lib.mt8167_random_seed(seed, 13000000), -1)
        self.assertEqual(bytes(seed), bytes(64))


if __name__ == "__main__":
    unittest.main()
