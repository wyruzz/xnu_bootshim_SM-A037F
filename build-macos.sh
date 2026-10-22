#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# macOS build using Apple/LLVM Clang plus aarch64-elf-binutils from MacPorts.
set -euo pipefail
src=$(cd "$(dirname "$0")" && pwd)
out=${SHIM_OUT:-$src/../out/bootshim-macos}
prefix=${CROSS_COMPILE:-aarch64-elf-}
cc=${CC:-clang}
mkdir -p "$out"
flags=(-O2 --target=aarch64-none-elf -ffreestanding -nostdlib -fno-pic -mgeneral-regs-only -mstrict-align
       -fno-stack-protector -fno-unwind-tables -fno-asynchronous-unwind-tables
       -mcpu=cortex-a53 -Wall -Wextra -Werror)
"$cc" "${flags[@]}" -c "$src/start.S" -o "$out/start.o"
"$cc" "${flags[@]}" -c "$src/shim.c" -o "$out/shim.o"
"$cc" "${flags[@]}" -c "$src/fdt.c" -o "$out/fdt.o"
"$cc" "${flags[@]}" -c "$src/adt.c" -o "$out/adt.o"
"$cc" "${flags[@]}" -c "$src/handoff.c" -o "$out/handoff.o"
"$cc" "${flags[@]}" -c "$src/rng.c" -o "$out/rng.o"
if "${prefix}readelf" -r "$out/shim.o" "$out/fdt.o" "$out/adt.o" "$out/handoff.o" "$out/rng.o" | grep -q 'R_AARCH64_ABS'; then
    echo 'Absolute C relocation is incompatible with a relocated shim' >&2
    exit 1
fi
"${prefix}ld" -static -T "$src/shim.ld" --build-id=none --fatal-warnings \
    "$out/start.o" "$out/shim.o" "$out/fdt.o" "$out/adt.o" "$out/handoff.o" "$out/rng.o" -o "$out/shim.elf"
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
assert b[56:60]==b'ARM\x64' and struct.unpack_from('<Q',b,16)[0]==len(b)
assert syms['_bss_end'] <= syms['_stack_top'] == len(b)
(p/'build.json').write_text(json.dumps({'kind':'diagnostic-shim','cpu':'cortex-a53','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'xnu_boot_verified':False,'hardware_tested':False},indent=2)+'\n')
print(json.dumps({'image':str(image),'bytes':len(b),'hardware_tested':False}))
PY
