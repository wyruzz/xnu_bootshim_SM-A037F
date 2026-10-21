# Credits

This repository is a diagnostic-stage source adaptation for the Samsung Galaxy
A03s SM-A037F (MediaTek MT6765). It is licensed under MIT; see source headers.

The 64-byte AArch64 Image header framing follows the Linux arm64 boot protocol.
Reference documentation:
https://www.kernel.org/doc/html/latest/arch/arm64/booting.html

The XNU boot argument structure and Apple device-tree ABI research reference
Apple's XNU release `xnu-8796.141.3`:
https://github.com/apple-oss-distributions/xnu/tree/xnu-8796.141.3

The diagnostic code currently does not launch XNU. Donor-board ADT generation,
MT8167 random-number register access, EL2-to-EL1 transition, and framebuffer
writes have been disabled rather than reused on the SM-A037F. A target-specific
handoff requires independent implementation and validation.
