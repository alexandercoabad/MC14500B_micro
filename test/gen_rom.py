"""Emit (or check) the ROM case table of src/project.v from the assembly in model.py.

  python3 gen_rom.py          print the table
  python3 gen_rom.py --write  replace the block between the BEGIN ROM / END ROM markers
"""
import os, re, sys
from model import PROGRAMS, ASM

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "project.v")


def table():
    out = []
    for p, ((name, _), words) in enumerate(zip(PROGRAMS, ASM)):
        out.append(f"            // ---- program {p}: {name}")
        for pc, (text, byte) in enumerate(words):
            out.append(f"            6'h{p * 16 + pc:02X}: rom_q = 8'h{byte:02X};   // {text}")
    return "\n".join(out) + "\n"


def parse_rom(src_text):
    return {int(a, 16): int(d, 16) for a, d in re.findall(r"6'h([0-9A-Fa-f]{2}): rom_q = 8'h([0-9A-Fa-f]{2});", src_text)}


if __name__ == "__main__":
    if "--write" in sys.argv:
        s = open(SRC).read()
        new = re.sub(r"(// BEGIN ROM\n).*?(            // END ROM)", lambda m: m.group(1) + table() + m.group(2), s, flags=re.S)
        open(SRC, "w").write(new)
    else:
        print(table(), end="")
