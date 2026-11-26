<!---
This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.
-->

## How it works

An MC14500B-style 1-bit CPU in the sky130 *micro* tile (clk, rst_n, 8 inputs, 8 outputs). It runs one
instruction per clock from a 32-word on-chip ROM. The instruction set is the one from the full
`tt_um_mc14500b_soc_extended` design: `LD`, `LDC`, `AND`, `ANDC`, `OR`, `ORC`, `XNOR`, `STO`, `STOC`, `IEN`, `OEN`
and a skip-if-zero. The 1-bit data path is `RR` (result), `IEN`/`OEN` (input/output enable) and a skip latch,
with 4 scratch RAM bits.

Every input bit can be read (addresses 4-B), and `STO C` shifts a bit into the 8-bit output register on `uo_out`.

`ui_in[7]` picks the program:

- **0, ECHO:** copies `ui_in[6:0]` to `uo_out[6:0]` through the CPU (`LD in; STO C` for each bit).
- **1, LOGIC CHAIN:** `uo_out` shows RR after `in0`, `& in1`, `| in2`, `xnor in3`, `& ~in4`, `| ~in5`, `xnor in6`, `xnor in7`
  (the last bit inverted by `STOC`).

`uo_out` is a shift register, so it is only complete once per 16-clock loop.

Full instruction set and address map: `ISA.md`. Size: 91 cells, 27 flip-flops, about 1110 um2 of the 2999 um2 micro tile
(yosys + sky130_fd_sc_hd, before placement buffers).

## How to test

Hold `rst_n` low for a few clocks, release it, and drive `ui_in`.

1. `ui_in = 0x2A` (bit 7 low): after at most 16 clocks `uo_out` holds `0x2A`, rippling through intermediate values while the loop runs.
2. `ui_in = 0x80 | x`: `uo_out` shows the logic-chain values for `x`.
3. Toggle `ui_in[7]` to change program.

`cd test && make -B` runs the cocotb tests against a cycle-exact Python model; `python3 test/equiv/run_equiv.py` compares the core with the original SoC.

## External hardware

None. Eight switches on `ui_in` and eight LEDs on `uo_out` are enough; use a slow clock to see the output shift (it is a 1-bit CPU running one instruction per clock).
