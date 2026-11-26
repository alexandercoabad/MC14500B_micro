![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# MC14500B 1-bit microcontroller in a Tiny Tapeout micro tile (sky130)

The MC14500B core from [MC14500B_IHP](https://github.com/alexandercoabad/MC14500B_IHP), cut down to fit the experimental sky130
**micro tile** (`tiles: "micro"`: clk, rst_n, 8 inputs, 8 outputs, about 2999 um2 of core).

- [Datasheet](docs/info.md), [instruction set and address map](docs/ISA.md), [lab handout](docs/labs.md)
- [src/project.v](src/project.v): one file, `tt_um_mc14500b_micro`: 36 flip-flops, about 220 cells, roughly 2100 um2 in a rough yosys + sky130_fd_sc_hd estimate (about 70 % of the tile; the first micro version was 1114 um2 and 37 % utilisation in the real flow)
- `src/config.json`, `src/no_synth.cells`: micro-tile hardening settings, as in MaligayangPasko_micro

## Made for teaching

- **Debug view:** `ui_in[4] = 1` shows PC, RR, IEN, OEN and skip on the LEDs, so a slow clock lets students watch each instruction run.
- **Steady output:** the 8-bit output shift register is published to `uo_out` once per 16-instruction loop (no more rippling bits).
- **Clean program switching:** `ui_in[7:6]` picks one of four lab programs, sampled once per loop.
- **Real MC14500B semantics:** `IEN`/`OEN` load the raw bit, and every loop restarts with IEN = OEN = 1 and no pending skip. The full SoC has an IEN lock-up bug that this version fixes (see docs/ISA.md).
- **Programs (ROM):** ECHO, GATES, IEN/OEN (gated latch and input gate), SKIP MUX. Four more (LOGIC CHAIN, SR LATCH, TOGGLE FF, JOHNSON) are written and tested, ready to swap in. All eight did not fit: eight programs came to about 2900 um2 in the same estimate.

## What stays, what goes

| | Full SoC (1x2 tiles, IHP) | Micro |
|---|---|---|
| CPU core and all 16 opcodes | yes | same, with raw IEN/OEN and loop-end clean-up |
| Program memory | 64 x 8 writable RAM (512 flops) | 64 x 8 ROM, four programs picked by `ui_in[7:6]` |
| Scratch RAM | 8 bits | 4 bits |
| Inputs | `ui_in[7:5]` readable, `ui_in[0]` edge flag | all 8 bits readable |
| Output shift latch on `uo_out` | yes | yes, published once per loop; debug view on `ui_in[4]` |
| Clock divider, edge detector | yes | removed |
| `uio` (programming port, PC, write strobe) | yes | removed (no `uio` on a micro tile) |

To change the programs, edit them in assembly in `test/model.py` (`ALL_PROGRAMS`, and `ACTIVE` for the four that go in the ROM), run `python3 test/gen_rom.py --write` to regenerate the ROM table in `src/project.v`, then `make -B` in `test/`. The tests check the ROM table against the model, and each lab test is skipped when its program is not in the ROM.

## Tests

```sh
cd test && make -B                 # cocotb: every lab, program select, debug view, reset, 6000 random clocks vs test/model.py
python3 test/equiv/run_equiv.py    # 100 random programs, all opcodes, vs the original SoC with the two deliberate changes applied (needs iverilog)
```

## If it does not fit

Place-and-route was not run for this version. If global placement or routing fails, the two cheapest cuts are the debug view (about 90 um2: replace the `uo_out` mux in `project.v` by `shadow`) and the shadow output register (about 280 um2: drive `uo_out` from `out_q`). Dropping one program (3 slots) saves about 100 to 200 um2.
