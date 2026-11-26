# SPDX-FileCopyrightText: © 2026 Alexander Co Abad
# SPDX-License-Identifier: Apache-2.0
"""tt_um_mc14500b_micro: every clock against model.py (RTL and gate level).

Only clk, rst_n, ui_in and uo_out exist on a micro tile, so everything is
checked from those pins: the two ROM programs, program select, reset.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from model import Micro

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


@cocotb.test()
async def test_reset(dut):
    await start(dut)
    assert int(dut.uo_out.value) == 0
    # a second reset in mid-run puts everything back
    dut.ui_in.value = 0x55
    for _ in range(11):
        await RisingEdge(dut.clk)
    dut.rst_n.value = 0
    await Timer(SAMPLE_DELAY_NS, unit="ns")
    assert int(dut.uo_out.value) == 0, "async reset must clear uo_out"
    dut.rst_n.value = 1
    await Timer(1, unit="ns")


@cocotb.test()
async def test_echo_program(dut):
    """ui_in[7] = 0 selects program 0: after each 16-word loop uo_out == ui_in."""
    await start(dut)
    m = Micro()
    for pat in (0x00, 0x7F, 0x2A, 0x55, 0x01, 0x40, 0x3C):
        tr = await run_against_model(dut, m, lambda c, p=pat: p, 48)
        # the cycle in which pc == 15 is the final STO C: output is complete
        done = [uo for pc, uo in tr[16:] if pc == 15]
        assert done and all(uo == pat for uo in done), f"echo of {pat:#04x}: {[hex(u) for u in done]}"


@cocotb.test()
async def test_logic_chain_program(dut):
    """ui_in[7] = 1 selects program 1: the chain of RR values, exhaustively over
    all 128 settings of ui_in[6:0] with ui_in[7] held high."""
    await start(dut)
    m = Micro()
    for low in range(128):
        pat = 0x80 | low
        tr = await run_against_model(dut, m, lambda c, p=pat: p, 34)
        done = [uo for pc, uo in tr[17:] if pc == 15]
        # hand-computed expectation for the chain (in7 = 1)
        i = [(low >> n) & 1 for n in range(7)] + [1]
        r = i[0]; bits = [r]
        r &= i[1]; bits.append(r)
        r |= i[2]; bits.append(r)
        r = 1 - (r ^ i[3]); bits.append(r)
        r &= 1 - i[4]; bits.append(r)
        r |= 1 - i[5]; bits.append(r)
        r = 1 - (r ^ i[6]); bits.append(r)
        r = 1 - (r ^ i[7]); bits.append(1 - r)            # XNOR in7, then STOC
        exp = 0
        for b in bits:                                    # first stored ends up in bit 7
            exp = (exp << 1) | b
        assert done and all(uo == exp for uo in done), f"chain for ui_in {pat:#04x}: {done} vs {exp:#04x}"


@cocotb.test()
async def test_random_inputs_and_select(dut):
    """Random ui_in every clock (so the program select flips mid-loop too)."""
    await start(dut)
    m = Micro()
    rng = random.Random(14500)
    await run_against_model(dut, m, lambda c: rng.randrange(256), 6000)


@cocotb.test()
async def test_select_switch_with_busy_inputs(dut):
    """Toggle ui_in[7] every few clocks over a fixed low pattern."""
    await start(dut)
    m = Micro()
    await run_against_model(dut, m, lambda c: 0xA5 ^ (0x80 if (c // 5) % 2 else 0), 400)
    await run_against_model(dut, m, lambda c: 0x5A ^ (0x80 if (c // 7) % 2 else 0), 400)
