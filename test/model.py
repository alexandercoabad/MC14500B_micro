"""Cycle-exact model of tt_um_mc14500b_micro, written from docs/ISA.md.

state after reset: pc=0, RR=0, IEN=1, OEN=1, skip=0, RAM=0, out=0, in_q=0.
step(ui) is one rising clock edge with ui_in = ui.
"""

NOP0, LD, LDC, AND, ANDC, OR, ORC, XNOR, STO, STOC, IEN, OEN, JMP, RTN, SKZ, NOPF = range(16)


def ins(op, operand):
    return (op << 4) | operand


# operand addresses
RAM0, IN0, OUT = 0x0, 0x4, 0xC          # ram bit n = RAM0+n, ui_in bit n = IN0+n


def _chain():
    """program 1: LD in0, then AND in1, OR in2, XNOR in3, ANDC in4, ORC in5,
    XNOR in6, XNOR in7, each followed by STO C (the last one by STOC C)."""
    ops = [LD, AND, OR, XNOR, ANDC, ORC, XNOR, XNOR]
    prog = []
    for n, op in enumerate(ops):
        prog.append(ins(op, IN0 + n))
        prog.append(ins(STOC if n == 7 else STO, OUT))
    return prog


def _echo():
    """program 0: LD in7 .. LD in0, each followed by STO C."""
    prog = []
    for n in range(7, -1, -1):
        prog += [ins(LD, IN0 + n), ins(STO, OUT)]
    return prog


ROM = _echo() + _chain()          # 32 words, index = {in_q[7], pc}


class Micro:
    def __init__(self, rom=ROM):
        self.rom = rom
        self.reset()

    def reset(self):
        self.in_q, self.pc, self.rr = 0, 0, 0
        self.ien, self.oen, self.skip = 1, 1, 0
        self.ram, self.out = 0, 0

    def _read(self, operand):
        if operand < 4:
            b = (self.ram >> operand) & 1
        elif operand < 12:
            b = (self.in_q >> (operand - 4)) & 1
        elif operand == 0xC:
            b = self.out & 1
        else:
            b = 0
        return b & self.ien

    def step(self, ui):
        instr = self.rom[(((self.in_q >> 7) & 1) << 4) | self.pc]
        op, operand = instr >> 4, instr & 0xF
        d = self._read(operand)
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
            elif op == IEN:  ien = d
            elif op == OEN:  oen = d
            elif op == RTN:  skip = 1 - self.rr
        if wr:
            if operand < 4:
                ram = (ram & ~(1 << operand)) | (wd << operand)
            if operand == OUT:
                out = ((out << 1) | wd) & 0xFF
        self.rr, self.ien, self.oen, self.skip, self.ram, self.out = rr, ien, oen, skip, ram, out
        self.in_q = ui & 0xFF
        self.pc = (self.pc + 1) & 0xF
        return self.out
