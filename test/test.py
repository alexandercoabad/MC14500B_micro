# SPDX-FileCopyrightText: © 2026 Alexander Co Abad
# SPDX-License-Identifier: Apache-2.0
"""tt_um_mc14500b_micro: every clock against model.py (RTL and gate level), plus
lab-by-lab checks whose expected values are computed independently of the model.

Only clk, rst_n, ui_in and uo_out exist on a micro tile, so everything is
checked from those pins: the ROM programs, program select, debug view, reset.

The ROM holds the four programs in model.ACTIVE (slot n is selected by ui_in[7:6] = n).
Each lab test is skipped when its program is not in the ROM, so after swapping a
spare program in (see model.py) the same suite checks it.

Loop timing used below: a loop is 16 clocks starting at PC = 0. Program select is
sampled at the end of a loop, so after reset loop 0 always runs slot 0. uo_out is
published at the start of the next loop, so the byte made by loop k is visible
during loop k+1.
"""

import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from gen_rom import parse_rom
from model import Micro, ROM, SLOT

# 20 ns clock; sample mid-cycle so RTL and delayed gate-level models both settle
SAMPLE_DELAY_NS = 8


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start())
    dut.ui_in.value = 0
    dut.rst_n.value = 0
    await Timer(65, unit="ns")
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst_n.value = 1


async def run_against_model(dut, model, stimulus, cycles):
    """Drive stimulus(cycle) on ui_in; after every rising edge compare uo_out.
    Returns the list of (model.pc_before, uo_out) pairs for further checks."""
    trace = []
    for c in range(cycles):
        ui = stimulus(c)
        dut.ui_in.value = ui
        pc_before = model.pc
        exp = model.step(ui)
        await RisingEdge(dut.clk)
        # Sample well after the edge: the gate-level sky130 models are built
        # with -DUNIT_DELAY=#1, so a flop output (plus any buffer) settles a
        # few ns after the clock. Sampling at +1 ns races that delay.
        await Timer(SAMPLE_DELAY_NS, unit="ns")
        got = int(dut.uo_out.value)
        assert got == exp, f"cycle {c}: uo_out {got:#04x}, model {exp:#04x} (ui_in {ui:#04x}, pc {pc_before})"
        trace.append((pc_before, got))
    return trace


async def loops(dut, m, ui, n):
    """Hold ui_in = ui for n whole loops; returns the trace."""
    return await run_against_model(dut, m, lambda c: ui, 16 * n)


def made_by(trace, k):
    """byte produced by loop k of this trace (visible during loop k+1)"""
    return trace[16 * (k + 1) + 8][1]


def lab(name):
    """cocotb.test decorator that skips the test when the program is not in the ROM"""
    return cocotb.test(skip=name not in SLOT)


def slot_bits(name):
    """ui_in value that selects the program (ui_in[7:6])"""
    return SLOT[name] << 6


def pair(x):
    """the (X, ~X) display used by the SR latch, toggle FF and mux labs"""
    return 0xF0 if x else 0x0F


# --------------------------------------------------------------------------
@cocotb.test()
async def test_reset(dut):
    await start(dut)
    assert int(dut.uo_out.value) == 0
    # a second reset in mid-run puts everything back (ui_in[4] = 1: debug view is on)
    dut.ui_in.value = 0x55
    for _ in range(11):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    await Timer(SAMPLE_DELAY_NS, unit="ns")
    assert int(dut.uo_out.value) == 0, "async reset must clear uo_out"
    dut.rst_n.value = 1
    await Timer(1, unit="ns")


@cocotb.test()
async def test_rom_source_matches_model(dut):
    """the case table in src/project.v is the one generated from model.py"""
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "project.v")
    rom = parse_rom(open(src).read())
    assert sorted(rom) == list(range(64)), "ROM table must define all 64 words"
    for a in range(64):
        assert rom[a] == ROM[a], f"ROM word {a:#04x}: project.v {rom[a]:#04x}, model {ROM[a]:#04x} (run gen_rom.py --write)"


@lab("ECHO")
async def test_lab_echo(dut):
    """ECHO: uo_out = ui_in (bit 4 reads 0: it is the debug switch) and the byte is steady once published."""
    await start(dut)
    m = Micro()
    for pat in (0x00, 0x0F, 0x0A, 0x05, 0x01, 0x08, 0x2C, 0x25):
        pat |= slot_bits("ECHO")
        tr = await loops(dut, m, pat, 3)
        assert all(uo == pat for _, uo in tr[32:]), f"echo of {pat:#04x}: {[hex(u) for _, u in tr[32:]]}"


@lab("LOGIC CHAIN")
async def test_lab_logic_chain(dut):
    """LOGIC CHAIN: the eight successive values of RR, exhaustive over in0..in3."""
    await start(dut)
    m = Micro()
    for low in range(16):
        tr = await loops(dut, m, slot_bits("LOGIC CHAIN") | low, 4)
        i = [(low >> n) & 1 for n in range(4)]
        r = i[0]; bits = [r]
        r &= i[1]; bits.append(r)
        r |= i[2]; bits.append(r)
        r = 1 - (r ^ i[3]); bits.append(r)
        r &= 1 - i[0]; bits.append(r)
        r |= 1 - i[1]; bits.append(r)
        r = 1 - (r ^ i[2]); bits.append(r)
        r = 1 - (r ^ i[3]); bits.append(1 - r)           # XNOR in3, then STOC
        exp = 0
        for b in bits:                                    # first stored ends up in bit 7
            exp = (exp << 1) | b
        assert made_by(tr, 2) == exp, f"chain for in={low:#x}: {made_by(tr, 2):#04x} vs {exp:#04x}"
        assert all(uo == exp for _, uo in tr[48:]), "output must be steady while a loop runs"


@lab("GATES")
async def test_lab_gates(dut):
    """GATES: AND NAND OR NOR XOR XNOR A&~B ~(A&~B) of in0, in1 (in2, in3 ignored)."""
    await start(dut)
    m = Micro()
    for low in range(16):
        tr = await loops(dut, m, slot_bits("GATES") | low, 4)
        a, b = low & 1, (low >> 1) & 1
        bits = [a & b, 1 - (a & b), a | b, 1 - (a | b), a ^ b, 1 - (a ^ b), a & (1 - b), 1 - (a & (1 - b))]
        exp = 0
        for x in bits:
            exp = (exp << 1) | x
        assert made_by(tr, 2) == exp, f"gates A={a} B={b}: {made_by(tr, 2):#04x} vs {exp:#04x}"


@lab("SR LATCH")
async def test_lab_sr_latch(dut):
    """SR LATCH: Q <= (Q | S) & ~R with S = in0, R = in1; reset wins; Q is held in RAM."""
    await start(dut)
    m = Micro()
    q = 0
    for s, r in [(0, 0), (1, 0), (0, 0), (0, 1), (0, 0), (1, 1), (0, 0), (1, 0), (1, 1), (0, 0)]:
        tr = await loops(dut, m, slot_bits("SR LATCH") | (r << 1) | s, 4)
        q = (q | s) & (1 - r)
        assert made_by(tr, 2) == pair(q), f"S={s} R={r}: {made_by(tr, 2):#04x}, Q should be {q}"


@lab("TOGGLE FF")
async def test_lab_toggle_ff(dut):
    """TOGGLE FF: Q toggles on each rising edge of in0 and ignores a held level."""
    await start(dut)
    m = Micro()
    q, prev = 0, 0
    for level in [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 1]:
        tr = await loops(dut, m, slot_bits("TOGGLE FF") | level, 4)
        if level and not prev:
            q ^= 1
        prev = level
        assert made_by(tr, 2) == pair(q), f"in0={level}: {made_by(tr, 2):#04x}, Q should be {q}"


@lab("JOHNSON")
async def test_lab_johnson_counter(dut):
    """JOHNSON: 3-bit twisted-ring counter, one step per loop, 6 states."""
    await start(dut)
    m = Micro()
    tr = await loops(dut, m, slot_bits("JOHNSON"), 16)   # loop 0 is still slot 0
    b2 = b1 = b0 = 0
    seen = []
    for k in range(1, 14):                       # loop k >= 1 is the counter's step k
        b2, b1, b0 = b1, b0, 1 - b2
        exp = 0
        for bit, n in ((b2, 3), (b1, 3), (b0, 2)):
            exp = (exp << n) | (((1 << n) - 1) if bit else 0)
        seen.append(exp)
        assert made_by(tr, k) == exp, f"step {k}: {made_by(tr, k):#04x} vs {exp:#04x}"
    assert seen[:6] == [0x03, 0x1F, 0xFF, 0xFC, 0xE0, 0x00] and seen[6:12] == seen[:6]


@lab("SKIP MUX")
async def test_lab_skip_mux(dut):
    """SKIP MUX: M = in2 ? in0 : in1, built from two skipped loads."""
    await start(dut)
    m = Micro()
    for low in range(8):
        tr = await loops(dut, m, slot_bits("SKIP MUX") | low, 4)
        a, b, s = low & 1, (low >> 1) & 1, (low >> 2) & 1
        assert made_by(tr, 2) == pair(a if s else b), f"in0={a} in1={b} in2={s}: {made_by(tr, 2):#04x}"


@lab("IEN/OEN")
async def test_lab_ien_oen(dut):
    """IEN/OEN: H = latch of in0 that follows it only while in2 = 1 (OEN <= in2 blocks the
    store); G = in0 & in1 through IEN <= in1. uo_out = HHHH GGGG."""
    await start(dut)
    m = Micro()
    h = 0
    seq = [(0, 0, 0), (1, 0, 1), (0, 0, 0), (0, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1), (0, 1, 0),
           (0, 1, 1), (1, 1, 0), (1, 0, 1), (0, 0, 0)]       # (in0, in1, in2)
    for a, b, c in seq:
        tr = await loops(dut, m, slot_bits("IEN/OEN") | (c << 2) | (b << 1) | a, 4)
        if c:
            h = a
        exp = (0xF0 if h else 0) | (0x0F if (a & b) else 0)
        assert made_by(tr, 2) == exp, f"in0={a} in1={b} in2={c}: {made_by(tr, 2):#04x} vs {exp:#04x}"


@cocotb.test()
async def test_debug_view(dut):
    """ui_in[4] = 1: uo_out = {PC, RR, IEN, OEN, skip}. In the echo program IEN = OEN = 1, skip = 0."""
    await start(dut)
    m = Micro()
    tr = await run_against_model(dut, m, lambda c: 0x10 | 0x07, 64)
    for pc_before, got in tr[2:]:
        assert got >> 4 == (pc_before + 1) & 0xF, f"pc nibble {got >> 4:#x} after pc {pc_before}"
        assert got & 0x7 == 0b110, f"IEN/OEN/skip bits {got & 7:#05b}"


@lab("GATES")
async def test_select_latched_at_loop_end(dut):
    """Changing ui_in[7:6] in the middle of a loop must not change the program until the next loop."""
    await start(dut)
    m = Micro()
    g = slot_bits("GATES")
    # loop 0 (ECHO, slot 0): echo of 0x05, switch the select to GATES at pc 6
    assert SLOT["ECHO"] == 0, "this test starts in slot 0"
    tr = await run_against_model(dut, m, lambda c: 0x05 if c < 6 else g | 0x05, 16)
    tr += await run_against_model(dut, m, lambda c: g | 0x05, 48)
    assert made_by(tr, 0) == 0x05, f"loop 0 must finish as echo: {made_by(tr, 0):#04x}"
    # loops 1.. : GATES with A = 1, B = 0 -> AND 0, NAND 1, OR 1, NOR 0, XOR 1, XNOR 0, A&~B 1, ~ 0
    assert made_by(tr, 2) == 0b01101010, f"gates: {made_by(tr, 2):#04x}"


@cocotb.test()
async def test_random_inputs_and_select(dut):
    """Random ui_in every clock (select, debug switch and data all change mid-loop)."""
    await start(dut)
    m = Micro()
    rng = random.Random(14500)
    await run_against_model(dut, m, lambda c: rng.randrange(256), 6000)


@cocotb.test()
async def test_select_switch_with_busy_inputs(dut):
    """Step the program select (ui_in[7:6]) every few clocks over fixed low patterns."""
    await start(dut)
    m = Micro()
    await run_against_model(dut, m, lambda c: ((c // 5) % 4) << 6 | 0x0A, 800)
    await run_against_model(dut, m, lambda c: ((c // 7) % 4) << 6 | 0x05, 800)
    await run_against_model(dut, m, lambda c: ((c // 21) % 4) << 6 | (0x10 if (c // 3) % 2 else 0) | 0x0F, 800)
