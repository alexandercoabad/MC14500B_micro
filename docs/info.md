<!---
This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.
-->

## How it works

An MC14500B-style 1-bit CPU for teaching, in the sky130 *micro* tile (clk, rst_n, 8 inputs, 8 outputs). It runs one
instruction per clock from a 64-word on-chip ROM that holds four 16-instruction lab programs. The instruction set
is the one from the full `tt_um_mc14500b_soc_extended` design (`LD`, `LDC`, `AND`, `ANDC`, `OR`, `ORC`, `XNOR`,
`STO`, `STOC`, `IEN`, `OEN` and a skip-if-zero), with `IEN`/`OEN` loading the raw bit as on the real MC14500B.
The 1-bit data path is `RR` (result), `IEN`/`OEN` (input/output enable) and a skip latch, with 4 scratch RAM bits.

The CPU loops through its 16 instructions forever. Every input bit can be read (addresses 4-B), and `STO C`
shifts a bit into an 8-bit register. That register is copied to `uo_out` once per loop, so the output byte is steady.

**Program select:** `ui_in[7:6]`, read once per loop (so switching never splices two programs):

| `ui_in[7:6]` | Program | `uo_out` shows |
| :-: | :-- | :-- |
| 00 | ECHO | `ui_in` |
| 01 | GATES | AND, NAND, OR, NOR, XOR, XNOR, A&~B and its complement, of `in0`, `in1` (bit 7 first) |
| 10 | IEN/OEN | `HHHH GGGG`: H = in0 latched while in2 = 1 (OEN gates the store); G = in0 & in1 (IEN gates the read) |
| 11 | SKIP MUX | `MMMM ~M~M~M~M` with M = in2 ? in0 : in1, built from skipped instructions |

**Debug view:** `ui_in[4] = 1` makes `uo_out` show `{PC[3:0], RR, IEN, OEN, skip}` instead. With a slow clock the
LEDs show the CPU executing the program instruction by instruction.

Every loop ends by setting IEN = OEN = 1 and clearing skip, so any program starts clean.

Full instruction set and address map: `ISA.md`. Lab write-ups: `labs.md`. Size: about 220 cells with 36
flip-flops, roughly 2100 um2 of the 2999 um2 micro tile (rough yosys + sky130_fd_sc_hd estimate, before placement buffers).

## How to test

Hold `rst_n` low for a few clocks, release it, and drive `ui_in` (use a slow clock, a few Hz, to watch).

1. `ui_in = 0x0A` (slot 00): after at most 32 clocks `uo_out = 0x0A`.
2. `ui_in = 0x43` (slot 01, in0 = in1 = 1): `uo_out = 0xA5`; `0x42` (in1 only) gives `0x69`. `labs.md` has the full table.
3. `ui_in = 0x10 | x`: debug view: `uo_out[7:4]` counts the program counter 1, 2, 3, ... 15, 0.
4. Change `ui_in[7:6]` to change program; the new program starts at the next loop.

`cd test && make -B` runs the cocotb tests (a cycle-exact Python model plus lab-by-lab checks computed independently);
`python3 test/equiv/run_equiv.py` compares the core with the original SoC.

## External hardware

None. Eight switches on `ui_in` and eight LEDs on `uo_out` are enough; use a slow clock to watch the CPU run
(it executes one instruction per clock).
