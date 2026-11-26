"""Cycle-exact model of tt_um_mc14500b_micro, written from docs/ISA.md.

state after reset: pc=0, RR=0, IEN=1, OEN=1, skip=0, RAM=0, out=0, in_q=0,
program slot = 0, published output (shadow) = 0.
step(ui) is one rising clock edge with ui_in = ui.

The teaching programs are written here in assembly (ALL_PROGRAMS). Four of them
(ACTIVE) fit in the micro tile's ROM; the others are ready to swap in. gen_rom.py
turns the ACTIVE ones into the ROM case table in src/project.v, and test.py checks
that the two stay in sync.
"""

NOP0, LD, LDC, AND, ANDC, OR, ORC, XNOR, STO, STOC, IEN, OEN, JMP, RTN, SKZ, NOPF = range(16)
MNEMONIC = {"NOP0": NOP0, "LD": LD, "LDC": LDC, "AND": AND, "ANDC": ANDC, "OR": OR, "ORC": ORC,
            "XNOR": XNOR, "STO": STO, "STOC": STOC, "IEN": IEN, "OEN": OEN, "JMP": JMP,
            "RTN": RTN, "SKZ": SKZ, "NOPF": NOPF}


def ins(op, operand):
    return (op << 4) | operand


# operand addresses
RAM0, IN0, OUT = 0x0, 0x4, 0xC          # ram bit n = RAM0+n, ui_in bit n = IN0+n


def operand_of(text):
    t = text.strip().lower()
    if t in ("", "-"):
        return 0
    if t == "c":
        return OUT
    if t.startswith("ram"):
        return RAM0 + int(t[3:])
    if t.startswith("in"):
        return IN0 + int(t[2:])
    raise ValueError("bad operand " + text)


def asm(lines):
    """['LD in0', 'STO C', ...] -> [(text, byte), ...]"""
    out = []
    for ln in lines:
        parts = ln.split()
        out.append((ln, ins(MNEMONIC[parts[0]], operand_of(parts[1]) if len(parts) > 1 else 0)))
    return out


def _echo():
    p = []
    for n in range(7, -1, -1):
        p += [f"LD in{n}", "STO C"]
    return p


ALL_PROGRAMS = [
    # 0 ECHO: shift in7..in0 into the output register -> uo_out[3:0] = ui_in[3:0]
    #   (in7..in4 read 0 here: they are the program select and the debug switch)
    ("ECHO", _echo()),
    # 1 LOGIC CHAIN: the running value of RR through eight ALU steps (inputs in0..in3)
    ("LOGIC CHAIN", [
        "LD in0",   "STO C",
        "AND in1",  "STO C",
        "OR in2",   "STO C",
        "XNOR in3", "STO C",
        "ANDC in0", "STO C",
        "ORC in1",  "STO C",
        "XNOR in2", "STO C",
        "XNOR in3", "STOC C"]),
    # 2 GATES of A = in0, B = in1, each followed by its complement (STOC)
    #   uo_out = AND NAND OR NOR XOR XNOR (A&~B) ~(A&~B), bit 7 first
    ("GATES", [
        "LD in0",  "AND in1",  "STO C",  "STOC C",
        "LD in0",  "OR in1",   "STO C",  "STOC C",
        "LD in0",  "XNOR in1", "STOC C", "STO C",
        "LD in0",  "ANDC in1", "STO C",  "STOC C"]),
    # 3 SR LATCH in RAM bit 0: Q <= (Q | S) & ~R, S = in0, R = in1 (reset wins).
    #   uo_out = Q Q Q Q ~Q ~Q ~Q ~Q
    ("SR LATCH", [
        "LD ram0", "OR in0", "ANDC in1", "STO ram0",
        "STO C", "STO C", "STO C", "STO C",
        "STOC C", "STOC C", "STOC C", "STOC C",
        "NOP0", "NOP0", "NOP0", "NOP0"]),
    # 4 TOGGLE FLIP-FLOP: Q (ram0) toggles on a rising edge of in0; ram1 = previous in0,
    #   ram2 = snapshot of in0.  uo_out = Q Q Q Q ~Q ~Q ~Q ~Q
    ("TOGGLE FF", [
        "LD in0", "STO ram2",
        "ANDC ram1",              # RR = in0 & ~previous = rising edge
        "XNOR ram0", "STOC ram0", # Q <= Q xor edge
        "LD ram2", "STO ram1",    # previous <= in0
        "LD ram0",
        "STO C", "STO C", "STO C", "STO C",
        "STOC C", "STOC C", "STOC C", "STOC C"]),
    # 5 JOHNSON COUNTER (3-bit twisted ring, ram0..ram2, ram3 = temp), one step per loop
    #   states 000 001 011 111 110 100; uo_out = b2 b2 b2 b1 b1 b1 b0 b0
    ("JOHNSON", [
        "LD ram2", "STO ram3",
        "LD ram1", "STO ram2", "STO C", "STO C", "STO C",
        "LD ram0", "STO ram1", "STO C", "STO C", "STO C",
        "LDC ram3", "STO ram0", "STO C", "STO C"]),
    # 6 MUX with skip: M = in2 ? in0 : in1 using two guarded loads. uo_out = M M M M ~M ~M ~M ~M
    ("SKIP MUX", [
        "LD in2", "RTN", "LD in0", "STO ram0",      # RR = sel; skip next if sel = 0
        "LDC in2", "RTN", "LD in1", "OR ram0",      # RR = ~sel; skip next if sel = 1
        "STO C", "STO C", "STO C", "STO C",
        "STOC C", "STOC C", "STOC C", "STOC C"]),
    # 7 IEN / OEN: this program must sit in slot 2 or 3 (ui_in[7] = 1), so in7 doubles as a constant 1.
    #   H (ram1) is a gated latch: follows in0 only while in2 = 1 (OEN <= in2 blocks the STO)
    #   G = in0 & in1 through IEN <= in1.   uo_out = H H H H G G G G
    ("IEN/OEN", [
        "LD in0", "OEN in2", "STO ram1", "OEN in7", "LD ram1",
        "STO C", "STO C", "STO C", "STO C",
        "IEN in1", "LD in0",
        "STO C", "STO C", "STO C", "STO C",
        "NOP0"]),
]

for _name, _lines in ALL_PROGRAMS:
    assert len(_lines) == 16, (_name, len(_lines))

ALL = dict(ALL_PROGRAMS)

# The four programs in the ROM, in slot order: slot n is selected by ui_in[7:6] = n.
# To swap one for a spare, edit this list, run `python3 gen_rom.py --write`, then `make`:
# the lab tests of programs that are not in the ROM are skipped. (Slot order matters a
# little for area; this order was the smallest of the 24 tried.)
ACTIVE = ["ECHO", "GATES", "IEN/OEN", "SKIP MUX"]
SPARE = [n for n in ALL if n not in ACTIVE]
PROGRAMS = [(n, ALL[n]) for n in ACTIVE]
SLOT = {n: i for i, n in enumerate(ACTIVE)}
assert len(ACTIVE) == 4 and len(set(ACTIVE)) == 4
assert "IEN/OEN" not in SLOT or SLOT["IEN/OEN"] >= 2, "IEN/OEN lab reads ui_in[7] as a constant 1"

ASM = [asm(lines) for _, lines in PROGRAMS]
ROM = [b for prog in ASM for _, b in prog]          # 64 words, index = {sel[1:0], pc[3:0]}


class Micro:
    def __init__(self, rom=ROM):
        self.rom = rom
        self.reset()

    def reset(self):
        self.in_q, self.pc, self.rr = 0, 0, 0
        self.ien, self.oen, self.skip = 1, 1, 0
        self.ram, self.out = 0, 0
        self.sel, self.shadow = 0, 0

    def _read_raw(self, operand):
        if operand < 4:
            return (self.ram >> operand) & 1
        if operand < 12:
            return (self.in_q >> (operand - 4)) & 1
        if operand == 0xC:
            return self.out & 1
        return 0

    @property
    def uo(self):
        """what the uo_out pins show right now"""
        if (self.in_q >> 4) & 1:     # debug view
            return (self.pc << 4) | (self.rr << 3) | (self.ien << 2) | (self.oen << 1) | self.skip
        return self.shadow

    def step(self, ui):
        instr = self.rom[(self.sel << 4) | self.pc]
        op, operand = instr >> 4, instr & 0xF
        raw = self._read_raw(operand)
        d = raw & self.ien
        rr, ien, oen, skip, ram, out = self.rr, self.ien, self.oen, self.skip, self.ram, self.out
        wr = (not self.skip) and self.oen and op in (STO, STOC)
        wd = (1 - self.rr) if op == STOC else self.rr
        if self.skip:
            skip = 0
        else:
            if op == LD:     rr = d
            elif op == LDC:  rr = 1 - d
            elif op == AND:  rr = self.rr & d
            elif op == ANDC: rr = self.rr & (1 - d)
            elif op == OR:   rr = self.rr | d
            elif op == ORC:  rr = self.rr | (1 - d)
            elif op == XNOR: rr = 1 - (self.rr ^ d)
            elif op == IEN:  ien = raw          # raw bit: IEN can always be set again
            elif op == OEN:  oen = raw          # raw bit
            elif op == RTN:  skip = 1 - self.rr
        if wr:
            if operand < 4:
                ram = (ram & ~(1 << operand)) | (wd << operand)
            if operand == OUT:
                out = ((out << 1) | wd) & 0xFF
        sel, shadow = self.sel, self.shadow
        if self.pc == 0:                 # publish the finished byte
            shadow = self.out
        if self.pc == 15:                # loop end: clean state, latch the program select
            ien, oen, skip = 1, 1, 0
            sel = (ui >> 6) & 3
        self.rr, self.ien, self.oen, self.skip, self.ram, self.out = rr, ien, oen, skip, ram, out
        self.sel, self.shadow = sel, shadow
        self.in_q = ui & 0xFF
        self.pc = (self.pc + 1) & 0xF
        return self.uo
