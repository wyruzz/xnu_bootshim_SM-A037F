#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
out=${SHIM_OUT:-$src/../out/bootshim}
prefix=${CROSS_COMPILE:-aarch64-linux-gnu-}
mkdir -p "$out"
flags=(-O2 -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align
       -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables
       -mcpu=cortex-a53 -Wall -Wextra -Werror)
"${prefix}gcc" "${flags[@]}" -c "$src/start.S" -o "$out/start.o"
"${prefix}gcc" "${flags[@]}" -c "$src/shim.c" -o "$out/shim.o"
"${prefix}gcc" "${flags[@]}" -c "$src/fdt.c" -o "$out/fdt.o"
"${prefix}gcc" "${flags[@]}" -c "$src/adt.c" -o "$out/adt.o"
"${prefix}gcc" "${flags[@]}" -c "$src/handoff.c" -o "$out/handoff.o"
"${prefix}gcc" "${flags[@]}" -c "$src/rng.c" -o "$out/rng.o"
if "${prefix}readelf" -r "$out/shim.o" "$out/fdt.o" "$out/adt.o" "$out/handoff.o" "$out/rng.o" | grep -q 'R_AARCH64_ABS'; then
    echo 'Absolute C relocation is incompatible with a relocated shim' >&2; exit 1
fi
"${prefix}gcc" "${flags[@]}" -static -T "$src/shim.ld" -Wl,--build-id=none \
    -Wl,--fatal-warnings "$out/start.o" "$out/shim.o" "$out/fdt.o" "$out/adt.o" "$out/handoff.o" "$out/rng.o" -o "$out/shim.elf"
python3 - "${prefix}readelf" "$out/shim.elf" <<'PY_CHECK'
import subprocess, sys
text = subprocess.check_output([sys.argv[1], "-lW", sys.argv[2]], text=True)
for line in text.splitlines():
    fields = line.split()
    if fields and fields[0] == "LOAD":
        flags = "".join(fields[6:-1])
        if "W" in flags and "E" in flags:
            raise SystemExit("Refusing shim ELF with a writable-and-executable LOAD segment")
PY_CHECK
"${prefix}objcopy" -O binary "$out/shim.elf" "$out/Image"
"${prefix}nm" "$out/shim.elf" > "$out/symbols.txt"
python3 - "$out" <<'PY'
from pathlib import Path
import hashlib, json, struct, sys
p=Path(sys.argv[1]); syms={line.split()[2]:int(line.split()[0],16) for line in (p/'symbols.txt').read_text().splitlines() if len(line.split())==3}
image=p/'Image'
with image.open('r+b') as f: f.truncate(syms['_end'])
b=image.read_bytes()
# Validate the AArch64 Image header and prove its first branch lands on _start.
insn=struct.unpack_from('<I', b, 0)[0]
assert insn & 0xfc000000 == 0x14000000, 'Image entry must begin with an AArch64 B instruction'
imm26=insn & 0x03ffffff
if imm26 & 0x02000000:
    imm26 -= 0x04000000
assert imm26 * 4 == syms['_start'], 'Image entry branch does not target _start'
assert struct.unpack_from('<Q', b, 8)[0] == 0, 'unexpected AArch64 Image text_offset'
assert struct.unpack_from('<Q', b, 16)[0] == len(b), 'AArch64 Image image_size mismatch'
assert struct.unpack_from('<Q', b, 24)[0] == 0xa, 'unexpected AArch64 Image flags'
assert b[32:56] == bytes(24), 'AArch64 Image reserved header fields must be zero'
assert b[56:60] == bytes((65, 82, 77, 100))
assert syms['_bss_end'] <= syms['_stack_top'] == len(b)
(p/'build.json').write_text(json.dumps({'kind':'diagnostic-shim','cpu':'cortex-a53','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'xnu_boot_verified':False,'hardware_tested':False},indent=2)+'\n')
print(json.dumps({'image':str(image),'bytes':len(b),'hardware_tested':False}))
PY
