![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# MC14500B 1-bit microcontroller in a Tiny Tapeout micro tile (sky130)

The MC14500B core from [MC14500B_IHP](https://github.com/alexandercoabad/MC14500B_IHP), cut down to fit the experimental sky130
**micro tile** (`tiles: "micro"`: clk, rst_n, 8 inputs, 8 outputs, about 2999 um2 of core).

- [Datasheet](docs/info.md), [instruction set and address map](docs/ISA.md)
- [src/project.v](src/project.v): one file, `tt_um_mc14500b_micro`: 27 flip-flops, 91 cells, about 1110 um2 in yosys with sky130_fd_sc_hd (about 37 % of the tile)
- `src/config.json`, `src/no_synth.cells`: micro-tile hardening settings, as in MaligayangPasko_micro

## What stays, what goes

| | Full SoC (1x2 tiles, IHP) | Micro |
|---|---|---|
| CPU core and all 16 opcodes | yes | **same** |
| Program memory | 64 x 8 writable RAM (512 flops) | 32 x 8 ROM, two programs picked by `ui_in[7]` |
| Scratch RAM | 8 bits | 4 bits |
| Inputs | `ui_in[7:5]` readable, `ui_in[0]` edge flag | all 8 bits readable |
| Output shift latch on `uo_out` | yes | yes |
| Clock divider, edge detector | yes | removed |
| `uio` (programming port, PC, write strobe) | yes | removed (no `uio` on a micro tile) |

Because the program is a ROM, the chip runs the two built-in programs (echo `ui_in` to `uo_out`; a chain of logic ops over the inputs).
To run something else, change the `case` in `src/project.v` (the model in `test/model.py` has the same ROM).

## Tests

```sh
cd test && make -B                 # cocotb: both programs, program select, reset, 6000 random clocks vs test/model.py
python3 test/equiv/run_equiv.py    # 100 random programs, all opcodes, vs the original SoC (needs iverilog)
```
